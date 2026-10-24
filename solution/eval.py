"""Prediction uses only the supplied input and persisted active rules."""

import csv
import hashlib
import json
from pathlib import Path
import sys

from .checkers import run_check
from .facts import FactSheet
from .io import load_rows, write_json
from .llm import ChatClient, pmap
from .semantic import SemanticRuntime


def predict(row, rules, runtime=None, default_label="good", topic_majority=None, details=None):
    facts = FactSheet.from_row(row)
    unknown = False
    for rule in sorted(rules, key=lambda r: (r["priority"], r["id"])):
        if rule["status"] == "active" and rule["topic"] in (facts.topic, "all"):
            result = run_check(rule, facts, runtime, row.get("item_id"))
            if details is not None:
                details.append(result)
            unknown |= result["violated"] is None
            if result["violated"] is True:
                return "bad"
    if unknown and topic_majority:
        return topic_majority.get(facts.topic, default_label)
    return default_label


def evaluate(input_path="/input/test.jsonl", artifacts="/artifacts", output="/output/predictions.csv", no_model=False):
    path = Path(output)
    manifest_path = Path(artifacts) / "rules_spec.json"
    if path.resolve() in (Path(input_path).resolve(), manifest_path.resolve()):
        raise ValueError("Output must not overwrite input or rule manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported rules_spec schema_version")
    rows = load_rows(input_path)
    index_path = Path(artifacts) / "fewshot_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    cache_dir = path.parent / "cache"
    if cache_dir.resolve() == (Path(artifacts) / "cache").resolve():
        cache_dir = path.parent / "eval_cache"
    client = ChatClient(cache_dir, [Path(artifacts) / "cache"], disabled=no_model)
    runtime = SemanticRuntime(client, index)
    if not client.available:
        print("[eval] model calls skipped: no enabled API key; cached responses may be reused", file=sys.stderr)
    def judge(row):
        checks = []
        return predict(row, manifest["rules"], runtime, manifest.get("default_label", "good"),
                       manifest.get("topic_majority"), checks), checks

    predictions, decisions = [], []
    for row, (label, checks) in zip(rows, pmap(judge, rows) if client.available else map(judge, rows)):
        predictions.append(dict(item_id=row["item_id"], label=label))
        decisions.append(dict(item_id=row["item_id"], label=label, checks=checks,
                              fallback=any(c["violated"] is None for c in checks) and not any(c["violated"] is True for c in checks)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["item_id", "label"])
        writer.writeheader()
        writer.writerows(predictions)
    stats = client.stats()
    log_path = path.with_suffix(".log.json")
    write_json(log_path, dict(model_status="enabled" if client.available else "skipped_no_key_or_disabled",
                             manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                             input_sha256=hashlib.sha256(Path(input_path).read_bytes()).hexdigest(),
                             predictions_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                             stats=stats, model_events=client.events, semantic_events=runtime.events, decisions=decisions))
    return dict(predictions=len(predictions), output=str(path), model_calls=stats["model_calls"],
                network_calls=stats["network_calls"], log=str(log_path))
