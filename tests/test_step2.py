"""Offline contract tests: no API keys, dependencies, or live network required."""

import io
from http.client import IncompleteRead
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from solution import dsl
from solution.adapt import adapt, explain, manifest_hash
from solution.checkers import run_check
from solution.eval import evaluate, predict
from solution.facts import FactSheet
from solution.induce import acceptance, induce
from solution.llm import ChatClient, cache_key, load_dotenv, parse_json, validate_json
from solution.semantic import SemanticRuntime, VERDICT_SCHEMA, build_index
from solution.validate import zero_shot


def row(i="one", label="bad", answer="unsupported claim", balance=100, topic="financial_position"):
    return dict(item_id=i, topic=topic, label=label, context=dict(accounts=[dict(product="Cash", balance=balance)]),
                conversation=[dict(role="user", content="What is my balance?"), dict(role="assistant", content=answer)])


def response(value):
    return io.BytesIO(json.dumps(dict(choices=[dict(message=dict(content=value))],
                                    usage=dict(prompt_tokens=10, completion_tokens=5, total_tokens=15, cost=.001))).encode())


class DSLTests(unittest.TestCase):
    def setUp(self):
        self.f = FactSheet.from_row(row(answer="Balance: 100.5 MXN. Rate 9%"))

    def test_numbers_kinds_scope_and_tolerance(self):
        present = dict(op="number_present", value={"ref": "expected.own_gross"}, kind="money")
        self.assertTrue(dsl.evaluate(present, self.f))
        self.assertFalse(dsl.evaluate(dict(present, absolute=0, relative=0), self.f))
        self.assertTrue(dsl.evaluate(dict(op="number_present", value=9, kind="percent", absolute=0, relative=0), self.f))
        self.assertTrue(dsl.evaluate(dict(op="number_absent", value=300), self.f))

    def test_comparison_boolean_arithmetic_and_known_false(self):
        f = FactSheet.from_row(row())
        f.flags["synthetic"] = False
        f.known_fields["user.plus"] = False
        expr = dict(op="and", args=[dict(op="field_present", field="user.plus"),
                    dict(op="not", arg=dict(op="flag", name="synthetic")),
                    dict(op="compare", cmp="eq", left=dict(op="sub", left={"ref":"expected.own_gross"}, right=20), right=80)])
        self.assertTrue(dsl.evaluate(expr, f))
        self.assertTrue(dsl.evaluate(dict(op="field_present", field="accounts.*.balance"), f))
        self.assertFalse(dsl.evaluate(dict(op="field_present", field="missing"), f))

    def test_missing_and_division_zero_stay_unknown_under_not(self):
        missing = dict(op="number_absent", value={"ref":"expected.missing"})
        self.assertIsNone(dsl.evaluate(missing, self.f))
        self.assertIsNone(dsl.evaluate(dict(op="not", arg=missing), self.f))
        self.assertFalse(dsl.evaluate(dict(op="and", args=[missing, dict(op="flag", name="has_hold")]), self.f))
        self.assertIsNone(dsl.evaluate(dict(op="compare", cmp="eq", left=dict(op="div", left=1, right=0), right=0), self.f))

    def test_code_and_complexity_are_rejected(self):
        for expr in ["__import__('os').system('anything')", {"op":"exec","code":"pass"},
                     {"op":"number_present","value":{"ref":"__class__.__dict__"}},
                     {"op":"number_present","value":100,"relative":-1}]:
            with self.assertRaises((ValueError, TypeError)):
                dsl.evaluate(expr, self.f)
        expr = dict(op="flag", name="has_hold")
        for _ in range(20):
            expr = dict(op="not", arg=expr)
        with self.assertRaises(ValueError):
            dsl.evaluate(expr, self.f)


class ClientTests(unittest.TestCase):
    def test_parse_json_and_validate(self):
        value = dict(verdict="unknown", quote="", reason="No evidence")
        for source in [json.dumps(value), "```json\n"+json.dumps(value)+"\n```", "Result: "+json.dumps(value)+" done"]:
            self.assertEqual(validate_json(parse_json(source), VERDICT_SCHEMA), value)
        with self.assertRaises(ValueError):
            parse_json("No valid answer")
        with self.assertRaises(ValueError):
            validate_json(dict(value, verdict="maybe"), VERDICT_SCHEMA)

    def test_dotenv_is_literal_and_environment_wins(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/".env"
            path.write_text("# comment\nOPENROUTER_API_KEY='fixture-value'\nexport EVAL_MODEL=chosen # comment\nX=$(touch nope)\n")
            env = {"EVAL_MODEL":"existing"}
            load_dotenv(path, env)
            self.assertEqual(env, dict(OPENROUTER_API_KEY="fixture-value", EVAL_MODEL="existing", X="$(touch nope)"))
            self.assertFalse((Path(temp)/"nope").exists())

    @patch.dict("os.environ", {"GEMINI_API_KEY": "gemini-fixture", "GEMINI_MODEL": "gemini-4-argon"}, clear=True)
    def test_gemini_key_selects_google_endpoint_without_openrouter(self):
        with tempfile.TemporaryDirectory() as temp:
            client = ChatClient(temp, dotenv=Path(temp) / "absent")
            self.assertTrue(client.available)
            self.assertEqual(client.base_url, "https://generativelanguage.googleapis.com/v1beta/openai")
            self.assertEqual(client.eval_model, "gemini-4-argon")
            self.assertNotIn("gemini-fixture", json.dumps(client.events))

    @patch.dict("os.environ", {
        "OPENROUTER_API_KEY": "router-fixture", "GEMINI_API_KEY": "gemini-fixture",
        "GEMINI_MODEL": "gemini-4-argon"}, clear=True)
    def test_openrouter_key_keeps_the_openrouter_endpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            client = ChatClient(temp, dotenv=Path(temp) / "absent")
            self.assertEqual(client.base_url, "https://openrouter.ai/api/v1")
            self.assertEqual(client.induction_model, "openai/gpt-oss-120b")

    @patch.dict("os.environ", {}, clear=True)
    def test_cache_survives_separate_client_without_key(self):
        value = dict(verdict="yes", quote="unsupported", reason="fixture")
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            client = ChatClient(base/"adapt_cache", api_key="fixture-secret", dotenv=base/"absent")
            with patch("solution.llm.urlopen", return_value=response(json.dumps(value))) as request:
                self.assertEqual(client.request("s", "u", VERDICT_SCHEMA), value)
                payload = json.loads(request.call_args.args[0].data)
                self.assertEqual(payload["temperature"], 0)
                self.assertEqual(payload["response_format"]["type"], "json_schema")
            before = {p.name:p.read_bytes() for p in (base/"adapt_cache").glob("*")}
            other = ChatClient(base/"eval_cache", [base/"adapt_cache"], api_key="", dotenv=base/"absent")
            with patch("solution.llm.urlopen", side_effect=AssertionError("network forbidden")):
                self.assertEqual(other.request("s", "u", VERDICT_SCHEMA), value)
            self.assertEqual(other.stats()["network_calls"], 0)
            self.assertEqual(before, {p.name:p.read_bytes() for p in (base/"adapt_cache").glob("*")})
            self.assertNotIn("fixture-secret", json.dumps(client.events)+"".join(v.decode() for v in before.values()))
            self.assertNotEqual(cache_key("a", "s", "u", VERDICT_SCHEMA), cache_key("b", "s", "u", VERDICT_SCHEMA))

    @patch.dict("os.environ", {}, clear=True)
    def test_structured_fallback_retries_and_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            c = ChatClient(temp, api_key="fixture", dotenv=Path(temp)/"none", pause=0)
            failure = HTTPError("https://example.invalid", 400, "unsupported format", {}, None)
            with patch("solution.llm.urlopen", side_effect=[failure, response('```json\n{"verdict":"no","quote":"","reason":"ok"}\n```')]) as request:
                self.assertEqual(c.request("s", "u", VERDICT_SCHEMA)["verdict"], "no")
                self.assertNotIn("response_format", json.loads(request.call_args.args[0].data))
            c2 = ChatClient(temp, api_key="fixture", dotenv=Path(temp)/"none", pause=0)
            with patch("solution.llm.urlopen", side_effect=URLError("secret must never be logged")) as request:
                self.assertIsNone(c2.request("different", "u", VERDICT_SCHEMA))
                self.assertEqual(request.call_count, 3)
                self.assertIsNone(c2.request("next", "u", VERDICT_SCHEMA))
                self.assertEqual(request.call_count, 3)  # circuit breaker
            self.assertNotIn("secret must never", json.dumps(c2.events))

    @patch.dict("os.environ", {}, clear=True)
    def test_no_key_and_corrupt_cache_are_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            client = ChatClient(temp, api_key="", dotenv=Path(temp)/"missing")
            (Path(temp)/(cache_key(client.eval_model, "s", "u", VERDICT_SCHEMA)+".json")).write_text("broken")
            with patch("solution.llm.urlopen", side_effect=AssertionError("network forbidden")):
                self.assertIsNone(client.request("s", "u", VERDICT_SCHEMA))
            self.assertEqual(client.events[-1]["status"], "no_key")
            client = ChatClient(temp, api_key="", dotenv=Path(temp)/"missing")
            (Path(temp)/(cache_key(client.eval_model, "s", "u", VERDICT_SCHEMA)+".json")).write_text("[]")
            self.assertIsNone(client.request("s", "u", VERDICT_SCHEMA))

    @patch.dict("os.environ", {}, clear=True)
    def test_malformed_usage_and_incomplete_http_do_not_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            c = ChatClient(temp, api_key="fixture", dotenv=Path(temp)/"none", pause=0)
            malformed = io.BytesIO(json.dumps(dict(choices=[dict(message=dict(content='{"verdict":"no","quote":"","reason":"ok"}'))], usage="unavailable")).encode())
            with patch("solution.llm.urlopen", side_effect=[IncompleteRead(b"partial"), malformed]):
                self.assertEqual(c.request("s", "u", VERDICT_SCHEMA)["verdict"], "no")
            self.assertFalse(c.stats()["cost_complete"])


class SemanticTests(unittest.TestCase):
    def test_retrieval_excludes_self_and_other_topics(self):
        rows = [row(str(i), answer="balance " + "savings "*i) for i in range(5)]
        rows.append(row("other", topic="credit"))
        runtime = SemanticRuntime(None, build_index(rows))
        hits = runtime.fewshot(FactSheet.from_row(rows[0]), rows[0]["item_id"])
        self.assertEqual(len(hits), 3)
        self.assertNotIn("0", [x["item_id"] for x in hits])
        self.assertTrue(all(x["topic"] == "financial_position" for x in hits))

    def test_ungrounded_quote_unknown_and_majority_fallback(self):
        class Client:
            eval_model = "fixture"
            def request(self, *args, **kwargs):
                return dict(verdict="yes", quote="not in dialogue", reason="fixture")
        runtime = SemanticRuntime(Client())
        rule = dict(id="semantic", topic="financial_position", status="active", priority=1,
                    applicability={}, checker="llm_predicate", params=dict(text="A violation"))
        result = run_check(rule, FactSheet.from_row(row()), runtime)
        self.assertIsNone(result["violated"])
        self.assertEqual(result["evidence"]["status"], "unknown")
        self.assertEqual(predict(row(), [rule], runtime, topic_majority={"financial_position":"bad"}), "bad")
        self.assertEqual(predict(row(), [rule], runtime), "good")


class InductionTests(unittest.TestCase):
    def run_induction(self, rows, broad=False, duplicate_refinement=False):
        narrow = dict(name="Unsupported", topic="financial_position", criterion="Claims unsupported", kind="dsl",
                      impl=json.dumps(dict(op="text_contains", text="unsupported")), expected_bad_ids=["b0","b1","b2"])
        initial = dict(narrow, impl=json.dumps(dict(op="field_present", field="accounts.*.balance"))) if broad else narrow
        class Client:
            available = True
            disabled = False
            circuit_open = False
            induction_model = "fixture"
            eval_model = "fixture"
            def request(self, system, user, schema, **kwargs):
                if system.startswith("Merge") and duplicate_refinement:
                    return {"rules": [initial, dict(initial, criterion="Different broad candidate")]}
                return {"rules": [narrow if system.startswith("Narrow") else initial]}
        with tempfile.TemporaryDirectory() as temp:
            rules, log = induce(rows, [], SemanticRuntime(Client(), build_index(rows)), Path(temp))
            self.assertEqual(log, json.loads((Path(temp)/"induction_log.json").read_text()))
        return rules, log

    def test_residual_pair_full_verification_and_narrowing(self):
        rows = [row("b"+str(i), balance=100+i) for i in range(3)] + [row("g", "good", "supported", 400)]
        rules, log = self.run_induction(rows, broad=True)
        active = [r for r in rules if r["status"] == "active"]
        self.assertEqual(len(active), 1)
        self.assertEqual((active[0]["TP"], active[0]["FP"], active[0]["distinct_contexts"]), (3,0,3))
        self.assertEqual(active[0]["evaluated_rows"], 4)
        self.assertEqual(active[0]["origin"], "induced")
        self.assertEqual(len(log["pairs"]), 3)
        self.assertIsNotNone(log["decisions"][0]["narrowing"])

    def test_single_distinct_context_is_enough_with_zero_fp(self):
        rows = [row("b"+str(i)) for i in range(3)] + [row("g", "good", "supported", 400)]
        rules, log = self.run_induction(rows)
        self.assertEqual(rules[0]["status"], "active")
        self.assertEqual(rules[0]["distinct_contexts"], 1)

    def test_duplicate_refinement_cannot_duplicate_manifest_ids(self):
        rows = [row("b"+str(i), balance=100+i) for i in range(3)] + [row("g", "good", "supported", 400)]
        rules, log = self.run_induction(rows, broad=True, duplicate_refinement=True)
        self.assertEqual(len(rules), 1)
        self.assertEqual(log["decisions"][1]["reasons"], ["duplicate_candidate"])

    def test_any_topic_regression_blocks_even_high_precision(self):
        before = dict(by_topic=dict(a=dict(correct=10), b=dict(correct=9)))
        after = dict(by_topic=dict(a=dict(correct=9), b=dict(correct=10)))
        reasons = acceptance(dict(TP=5, FP=0, not_checked=0), before, after)
        self.assertEqual(reasons, ["topic_accuracy_regression"])

    def test_induced_semantic_rule_is_verified_and_usable(self):
        rows = [row("b"+str(i), balance=100+i) for i in range(3)] + [row("g", "good", "supported", 400)]
        proposal = dict(name="Semantic fixture", topic="financial_position", criterion="Unsupported claim", kind="semantic",
                        impl="The assistant makes an unsupported claim.", expected_bad_ids=["b0","b1","b2"])
        class Client:
            available = True
            disabled = False
            circuit_open = False
            induction_model = "fixture"
            eval_model = "fixture"
            def request(self, system, user, schema, **kwargs):
                if system.startswith("You check"):
                    bad = "unsupported" in json.loads(user)["conversation"][-1]["content"]
                    return dict(verdict="yes" if bad else "no", quote="unsupported" if bad else "", reason="fixture")
                return dict(rules=[proposal])
        runtime = SemanticRuntime(Client(), build_index(rows))
        with tempfile.TemporaryDirectory() as temp:
            rules, log = induce(rows, [], runtime, Path(temp))
        self.assertEqual(rules[0]["status"], "active")
        self.assertEqual((rules[0]["TP"], rules[0]["FP"], rules[0]["not_checked"]), (3,0,0))
        self.assertEqual(predict(row("novel"), rules, runtime), "bad")


@patch.dict("os.environ", {}, clear=True)
class NoKeyPipelineTests(unittest.TestCase):
    def test_model_failure_still_produces_every_prediction(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            train = base/"train.jsonl"
            train.write_text("".join(json.dumps(r)+"\n" for r in [row("one"), row("two", answer="another answer")]))
            adapt(train, base/"artifacts", no_model=True)
            manifest_path = base/"artifacts/rules_spec.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["rules"] = [dict(id="semantic", topic="financial_position", status="active", priority=1,
                                     applicability={}, checker="llm_predicate", params=dict(text="Unsupported assertion"))]
            manifest_path.write_text(json.dumps(manifest))
            with patch.dict("os.environ", {"OPENROUTER_API_KEY":"fixture-secret"}), \
                 patch("solution.llm.urlopen", side_effect=TimeoutError("provider failure")), \
                 patch("solution.llm.time.sleep"):
                result = evaluate(train, base/"artifacts", base/"out/pred.csv")
            self.assertEqual(result["predictions"], 2)
            self.assertEqual(result["network_calls"], 3)
            log = json.loads((base/"out/pred.log.json").read_text())
            self.assertTrue(all(d["fallback"] for d in log["decisions"]))
            self.assertNotIn("fixture-secret", json.dumps(log))

    def test_adapt_eval_and_baseline_without_key(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            train = base/"train.jsonl"
            rows = [row("bad"), row("good", "good", "100 MXN", 200)]
            train.write_text("".join(json.dumps(r)+"\n" for r in rows))
            with patch("solution.llm.urlopen", side_effect=AssertionError("network forbidden")):
                adapt(train, base/"artifacts", no_model=True)
                saved = {p.name:p.read_bytes() for p in (base/"artifacts").glob("*") if p.is_file()}
                evaluate(train, base/"artifacts", base/"out/predictions.csv", no_model=True)
                baseline = zero_shot(train, base/"artifacts", base/"out/baseline.csv", no_model=True)
            self.assertFalse(baseline["model_baseline_valid"])
            self.assertIsNone(baseline["model_macro_topic_accuracy"])
            self.assertEqual(baseline["stats"]["network_calls"], 0)
            manifest = json.loads(saved["rules_spec.json"])
            self.assertEqual(saved["explanation.md"].decode(), explain(manifest))
            self.assertIn(manifest_hash(manifest), saved["explanation.md"].decode())
            self.assertEqual(saved, {p.name:p.read_bytes() for p in (base/"artifacts").glob("*") if p.is_file()})


if __name__ == "__main__":
    unittest.main()
