"""Small, fail-soft OpenAI-compatible chat client; standard library only."""

from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_MODEL = "openai/gpt-oss-120b"
GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_GEMINI_MODEL = "gemini-4-argon"


def load_dotenv(path=".env", environ=None):
    """Read literal KEY=VALUE only. Never execute, interpolate, or print values."""
    env = os.environ if environ is None else environ
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].strip()
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not key or key.startswith("#") or not key.replace("_", "a").isalnum():
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()
        env.setdefault(key, value)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def cache_key(model, system, user, schema):
    return hashlib.sha256(canonical([model, system, user, schema]).encode()).hexdigest()


def parse_json(text):
    """Accept plain JSON, fenced JSON, or one object/array inside prose."""
    if isinstance(text, (dict, list)):
        return text
    if not isinstance(text, str):
        raise ValueError("No textual JSON content")
    decoder = json.JSONDecoder()
    try:
        return json.loads(text)
    except ValueError:
        for i, char in enumerate(text):
            if char in "{[":
                try:
                    return decoder.raw_decode(text[i:])[0]
                except ValueError:
                    pass
    raise ValueError("No JSON object or array")


def validate_json(value, schema):
    """Validate the JSON-schema subset used by this project, including enums."""
    kind = schema.get("type")
    valid = {"object": isinstance(value, dict), "array": isinstance(value, list),
             "string": isinstance(value, str), "boolean": isinstance(value, bool),
             "integer": type(value) is int,
             "number": finite_number(value),
             "null": value is None}
    if kind and not valid.get(kind, False):
        raise ValueError("JSON schema type mismatch")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("JSON schema enum mismatch")
    if isinstance(value, dict):
        if not set(schema.get("required", [])) <= value.keys():
            raise ValueError("JSON schema required field missing")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - properties.keys():
            raise ValueError("Unexpected JSON field")
        for key, item in value.items():
            if key in properties:
                validate_json(item, properties[key])
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            raise ValueError("JSON array size mismatch")
        for item in value:
            validate_json(item, schema.get("items", {}))
    return value


def finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


class ChatClient:
    def __init__(self, cache_dir, read_cache_dirs=(), *, api_key=None, base_url=None,
                 timeout=45, attempts=3, pause=1, dotenv=".env", disabled=False, max_calls=None):
        load_dotenv(dotenv)
        self.disabled = disabled or os.getenv("SOLUTION_DISABLE_LLM") == "1"
        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        # An explicit constructor key is a fixture or a caller override. Gemini is
        # selected only from the environment, and only when OpenRouter is unset,
        # so a teammate's OpenRouter run keeps its current endpoint.
        use_gemini = api_key is None and bool(gemini_key) and not openrouter_key
        if api_key is None:
            self.api_key = (gemini_key if use_gemini else openrouter_key).strip()
        else:
            self.api_key = api_key.strip()
        if base_url:
            self.base_url = base_url.rstrip("/")
        elif use_gemini:
            self.base_url = (os.getenv("GEMINI_BASE_URL") or GEMINI_OPENAI_BASE).rstrip("/")
        else:
            self.base_url = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").rstrip("/")
        if use_gemini:
            self.induction_model = os.getenv("INDUCTION_MODEL") or os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
        else:
            self.induction_model = os.getenv("INDUCTION_MODEL") or DEFAULT_MODEL
        self.eval_model = os.getenv("EVAL_MODEL") or self.induction_model
        self.cache_dir = Path(cache_dir)
        self.read_cache_dirs = [self.cache_dir] + [Path(p) for p in read_cache_dirs]
        self.timeout, self.attempts, self.pause = timeout, max(1, attempts), pause
        self.events, self._memo = [], {}
        self.circuit_open = False
        # Count HTTP attempts, including retries; cache reads never spend budget.
        self.max_calls = max_calls
        self.network_calls = 0
        limit = os.getenv("LLM_MAX_TOKENS", "").strip()
        self.max_tokens = int(limit) if limit else None
        if self.max_tokens is not None and self.max_tokens < 1:
            raise ValueError("LLM_MAX_TOKENS must be a positive integer")

    @property
    def budget_exhausted(self):
        return self.max_calls is not None and self.network_calls >= self.max_calls

    @property
    def available(self):
        return bool(self.api_key) and not self.disabled

    def record(self, status, **details):
        self.events.append(dict(status=status, **details))

    def request(self, system, user, schema, *, model=None):
        model = model or self.eval_model
        key = cache_key(model, system, user, schema)
        if key in self._memo:
            self.record("memory_hit", model=model, cache_key=key)
            return self._memo[key]
        for directory in self.read_cache_dirs:
            try:
                cached = json.loads((directory / (key + ".json")).read_text(encoding="utf-8"))
                if not isinstance(cached, dict) or cached.get("key") != key or cached.get("model") != model:
                    continue
                result = validate_json(cached["response"], schema)
                self._memo[key] = result
                self.record("cache_hit", model=model, cache_key=key)
                return result
            except (OSError, ValueError, KeyError, TypeError, RecursionError):
                continue
        if not self.available or self.circuit_open:
            reason = "disabled" if self.disabled else ("no_key" if not self.api_key else "circuit_open")
            self.record(reason, model=model, cache_key=key)
            self._memo[key] = None
            return None
        structured = True
        for attempt in range(1, self.attempts + 1):
            if self.budget_exhausted:
                self.record("budget_exhausted", model=model, cache_key=key)
                return None
            start = time.monotonic()
            usage = {}
            payload = dict(model=model, temperature=0, messages=[
                dict(role="system", content=system + "\nReturn only JSON matching this schema: " + canonical(schema)),
                dict(role="user", content=user)])
            if self.max_tokens is not None:
                payload["max_tokens"] = self.max_tokens
            if structured:
                payload["response_format"] = dict(type="json_schema", json_schema=dict(name="result", strict=True, schema=schema))
            try:
                req = Request(self.base_url + "/chat/completions", data=canonical(payload).encode(),
                              headers={"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"})
                self.network_calls += 1
                with urlopen(req, timeout=self.timeout) as response:
                    body = json.load(response)
                raw_usage = body.get("usage") if isinstance(body, dict) else None
                if isinstance(raw_usage, dict):
                    usage = {k: v for k, v in raw_usage.items() if k in
                             ("prompt_tokens", "completion_tokens", "total_tokens", "cost") and finite_number(v)}
                content = body["choices"][0]["message"]["content"]
                if isinstance(content, list):
                    content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
                result = validate_json(parse_json(content), schema)
                self.record("success", model=model, cache_key=key, attempt=attempt,
                            elapsed_seconds=time.monotonic()-start, structured=structured,
                            usage=usage)
                self._memo[key] = result
                try:
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    target = self.cache_dir / (key + ".json")
                    temp = target.with_suffix(f".{os.getpid()}.tmp")
                    temp.write_text(canonical(dict(key=key, model=model, response=result)), encoding="utf-8")
                    temp.replace(target)
                except OSError:
                    self.record("cache_write_failed", cache_key=key)
                return result
            except (HTTPError, URLError, HTTPException, TimeoutError, OSError, ValueError, KeyError, IndexError, TypeError, RecursionError, OverflowError) as error:
                # Neither the exception text, request, nor response body is logged:
                # provider messages can echo Authorization or other private content.
                code = error.code if isinstance(error, HTTPError) else None
                self.record("request_failed", model=model, cache_key=key, attempt=attempt,
                            error_type=type(error).__name__, http_status=code,
                            elapsed_seconds=time.monotonic()-start, structured=structured, usage=usage)
                if structured and (code in (400, 422) or isinstance(error, (ValueError, KeyError, TypeError))):
                    structured = False
                if attempt < self.attempts:
                    time.sleep(self.pause * attempt)
        self.circuit_open = True
        self._memo[key] = None
        print("[llm] API unavailable after retries; using deterministic/topic fallback", file=sys.stderr)
        return None

    def stats(self):
        completed = [e for e in self.events if e["status"] == "success"]
        requests = [e for e in self.events if e["status"] in ("success", "request_failed")]
        costs = [e["usage"]["cost"] for e in requests if "cost" in e["usage"]]
        return dict(key_present=bool(self.api_key), enabled=self.available,
                    max_tokens=self.max_tokens,
                    induction_model=self.induction_model, eval_model=self.eval_model,
                    network_calls=len(requests), model_calls=len(completed),
                    elapsed_seconds=sum(e.get("elapsed_seconds", 0) for e in requests),
                    reported_cost=sum(costs) if costs else (0 if not requests else None),
                    cost_complete=not requests or len(costs) == len(requests),
                    usage={k: sum(e["usage"].get(k, 0) for e in requests) for k in ("prompt_tokens", "completion_tokens", "total_tokens")},
                    event_statuses=dict(Counter(e["status"] for e in self.events)))
