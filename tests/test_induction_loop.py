"""Loop, transport-budget and empty-start regressions; all model responses mocked."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from solution.adapt import adapt, explain
from solution.induce import acceptance, induce
from solution.llm import ChatClient
from solution.semantic import SemanticRuntime, VERDICT_SCHEMA, build_index


def row(i, label="bad", answer=None, topic="financial_position"):
    return dict(item_id=i, topic=topic, label=label, context={"accounts": [{"balance": 100, "product": "Cash"}]},
                conversation=[{"role": "user", "content": "Balance?"},
                              {"role": "assistant", "content": answer or i}])


def proposal(text, kind="dsl"):
    return dict(name=text, topic="financial_position", criterion=text, kind=kind,
                impl=json.dumps({"op": "text_contains", "text": text}) if kind == "dsl" else text,
                expected_bad_ids=[])


class FakeClient:
    available, disabled, circuit_open = True, False, False
    induction_model = eval_model = "fixture"

    def __init__(self, reply, max_calls=400):
        self.reply, self.max_calls = reply, max_calls
        self.network_calls = 0
        self.requests = []

    def request(self, system, user, schema, **kwargs):
        if self.network_calls >= self.max_calls:
            return None
        self.network_calls += 1
        self.requests.append((system, json.loads(user)))
        return self.reply(system, json.loads(user))


@patch.dict("os.environ", {"INDUCTION_MAX_ROUNDS": "6", "INDUCTION_PAIRS_PER_ROUND": "1"}, clear=True)
class LoopTests(unittest.TestCase):
    def run_loop(self, rows, reply, max_calls=400):
        client = FakeClient(reply, max_calls)
        with tempfile.TemporaryDirectory() as temp:
            rules, log = induce(rows, [], SemanticRuntime(client, build_index(rows)), Path(temp))
            self.assertEqual(log, json.loads((Path(temp) / "induction_log.json").read_text()))
        return rules, log, client

    def test_stops_without_new_active(self):
        _, log, c = self.run_loop([row("bad"), row("good", "good")], lambda s, u: {"rules": []})
        self.assertEqual(len(log["rounds"]), 1)
        self.assertEqual(log["stop_reason"], "no_new_active")
        self.assertEqual(c.network_calls, 1)
        self.assertEqual(log["remaining_residual_item_ids"], ["bad"])

    def test_recomputes_residuals_and_uses_new_pair_each_round(self):
        rows = [row("b1"), row("b2"), row("g", "good")]
        rules, log, c = self.run_loop(rows, lambda s, u: {"rules": [proposal(u["pair"][0]["item_id"])]})
        self.assertEqual(len(rules), 2)
        self.assertEqual([r["residual_before"] for r in log["rounds"]], [["b1", "b2"], ["b2"]])
        self.assertEqual([r["residual_after"] for r in log["rounds"]], [["b2"], []])
        self.assertEqual(log["stop_reason"], "no_residuals")
        self.assertEqual([u["pair"][0]["label"] for _, u in c.requests], ["bad", "bad"])
        self.assertTrue(all(u["pair"][1]["label"] == "good" for _, u in c.requests))

    def test_call_budget_stops_after_first_progress_round(self):
        rules, log, c = self.run_loop([row("b1"), row("b2"), row("g", "good")],
                                     lambda s, u: {"rules": [proposal("b1")]}, max_calls=1)
        self.assertEqual(c.network_calls, 1)
        self.assertEqual(log["stop_reason"], "call_budget")
        self.assertEqual(log["remaining_residual_item_ids"], ["b2"])
        self.assertEqual(rules[0]["status"], "active")

    def test_semantic_verification_cannot_activate_after_budget_exhaustion(self):
        def reply(system, user):
            if system.startswith("You check"):
                return dict(verdict="yes", quote="b1", reason="fixture")
            return {"rules": [proposal("unsupported", "semantic")]}
        rules, log, c = self.run_loop([row("b1"), row("b2"), row("g", "good")], reply, max_calls=2)
        self.assertEqual(c.network_calls, 2)
        self.assertEqual(rules[0]["status"], "boundary")
        self.assertGreater(rules[0]["not_checked"], 0)
        self.assertEqual(log["stop_reason"], "call_budget")

    def test_six_round_hard_ceiling(self):
        with patch.dict("os.environ", {"INDUCTION_MAX_ROUNDS": "99"}):
            _, log, c = self.run_loop([row("b"+str(i)) for i in range(7)] + [row("g", "good")],
                lambda s, u: {"rules": [proposal(u["pair"][0]["item_id"])]})
        self.assertEqual(len(log["rounds"]), 6)
        self.assertEqual(c.network_calls, 6)
        self.assertEqual(log["stop_reason"], "round_budget")

    def test_one_fp_rejects_even_with_high_precision_and_only_one_narrowing(self):
        rows = [row("b"+str(i), answer="claim") for i in range(20)] + [row("g", "good", "claim")]
        rules, log, c = self.run_loop(rows, lambda s, u: {"rules": [proposal("claim")]})
        self.assertEqual(rules[0]["status"], "boundary")
        self.assertEqual((rules[0]["TP"], rules[0]["FP"]), (20, 1))
        self.assertIn("false_positives", log["decisions"][0]["reasons"])
        self.assertEqual(sum(s.startswith("Narrow") for s, _ in c.requests), 1)
        self.assertEqual(log["rounds"][0]["narrowed"], 1)
        self.assertEqual(log["rounds"][0]["rejected"], 1)
        self.assertEqual(acceptance(dict(TP=20, FP=1, not_checked=0)), ["false_positives"])

    def test_no_same_topic_good_makes_no_request(self):
        _, log, c = self.run_loop([row("b"), row("g", "good", topic="credit")], lambda s, u: {})
        self.assertEqual(c.network_calls, 0)
        self.assertEqual(log["pairs"][0]["status"], "no_good_twin")


class TransportBudgetTests(unittest.TestCase):
    @patch.dict("os.environ", {"LLM_MAX_TOKENS": "4096"}, clear=True)
    def test_optional_completion_limit_is_sent_without_changing_default(self):
        with tempfile.TemporaryDirectory() as temp:
            client = ChatClient(temp, api_key="fixture", dotenv=Path(temp)/"none", pause=0)
            value = dict(verdict="no", quote="", reason="fixture")
            response = io.BytesIO(json.dumps(dict(choices=[dict(message=dict(content=json.dumps(value)))])).encode())
            with patch("solution.llm.urlopen", return_value=response) as request:
                self.assertEqual(client.request("s", "u", VERDICT_SCHEMA), value)
                self.assertEqual(json.loads(request.call_args.args[0].data).get("max_tokens"), 4096)
            with patch.dict("os.environ", {}, clear=True):
                other = ChatClient(temp, api_key="fixture", dotenv=Path(temp)/"none")
                self.assertIsNone(other.max_tokens)

    @patch.dict("os.environ", {}, clear=True)
    def test_nonobject_response_is_a_logged_failure_and_budget_bounds_retries(self):
        with tempfile.TemporaryDirectory() as temp:
            client = ChatClient(temp, api_key="fixture", dotenv=Path(temp)/"none", max_calls=1, pause=0)
            with patch("solution.llm.urlopen", return_value=io.BytesIO(b"[]")) as request:
                self.assertIsNone(client.request("s", "u", VERDICT_SCHEMA))
                self.assertEqual(request.call_count, 1)
            self.assertEqual(client.stats()["network_calls"], 1)
            self.assertEqual(client.events[0]["status"], "request_failed")

    @patch.dict("os.environ", {}, clear=True)
    def test_retries_spend_budget_and_cache_remains_usable(self):
        with tempfile.TemporaryDirectory() as temp:
            client = ChatClient(temp, api_key="fixture", dotenv=Path(temp)/"none", max_calls=2, pause=0)
            value = dict(verdict="no", quote="", reason="fixture")
            response = io.BytesIO(json.dumps(dict(choices=[dict(message=dict(content=json.dumps(value)))])).encode())
            with patch("solution.llm.urlopen", side_effect=[URLError("fixture"), response]) as request:
                self.assertEqual(client.request("system", "one", VERDICT_SCHEMA), value)
                self.assertEqual(client.request("system", "one", VERDICT_SCHEMA), value)
                self.assertIsNone(client.request("system", "two", VERDICT_SCHEMA))
                self.assertEqual(request.call_count, 2)
            self.assertEqual(client.stats()["network_calls"], 2)
            self.assertTrue(client.budget_exhausted)


@patch.dict("os.environ", {}, clear=True)
class EmptyStartTests(unittest.TestCase):
    def test_explanation_preserves_rejected_version_and_accepted_witnesses(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            train = base / "train.jsonl"
            train.write_text("\n".join(json.dumps(r) for r in [row("b", answer="wrong balance"), row("g", "good", "balance")])+"\n")
            def reply(client, system, user, schema, **kwargs):
                return {"rules": [proposal("wrong" if system.startswith("Narrow") else "balance")]}
            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "fixture"}), patch.object(ChatClient, "request", reply):
                adapt(train, base / "artifacts", from_scratch=True)
            manifest = json.loads((base / "artifacts/rules_spec.json").read_text())
            text = (base / "artifacts/explanation.md").read_text()
            self.assertEqual(text, explain(manifest))
            self.assertIn("Rejected version: false positives on good", text)
            self.assertIn("[b](#example-b) (expert label bad)", text)
            self.assertIn("[g](#example-g) (expert label good)", text)
            round_log = manifest["induction"]["rounds"][0]
            self.assertEqual([round_log[k] for k in ("proposed", "accepted", "narrowed", "rejected")], [1, 1, 1, 0])

    def test_flag_and_env_do_not_instantiate_and_trail_matches_manifest(self):
        for flag in (True, False):
            with tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                train = base/"train.jsonl"
                train.write_text("\n".join(json.dumps(r) for r in [row("b"), row("g", "good")])+"\n")
                env = {} if flag else {"ADAPT_MODE": "from_scratch"}
                with patch.dict("os.environ", env), patch("solution.adapt.instantiate", side_effect=AssertionError("library used")):
                    adapt(train, base/"artifacts", no_model=True, from_scratch=flag)
                manifest = json.loads((base/"artifacts/rules_spec.json").read_text())
                self.assertEqual(manifest["rules"], [])
                self.assertEqual(manifest["adapt_mode"], "from_scratch")
                text = (base/"artifacts/explanation.md").read_text()
                self.assertEqual(text, explain(manifest))
                self.assertIn("## Induction trail", text)


if __name__ == "__main__":
    unittest.main()
