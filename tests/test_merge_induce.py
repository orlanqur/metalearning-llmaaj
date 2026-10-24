"""Merged parallel discovery/round transitions and shared HTTP budget."""

import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from solution.induce import induce
from solution.llm import ChatClient, Request, pmap
from solution.semantic import SemanticRuntime, VERDICT_SCHEMA, build_index
from test_induction_loop import FakeClient, proposal, row


class MergeInduceTests(unittest.TestCase):
    @patch.dict("os.environ", {"INDUCTION_MAX_ROUNDS": "6", "INDUCTION_PAIRS_PER_ROUND": "2"}, clear=True)
    def test_parallel_discovery_preserves_round_order_history_and_results(self):
        rows = [row("b1"), row("b2"), row("b3"), row("g", "good")]
        results = []
        for workers in ("1", "2"):
            barrier = threading.Barrier(2, timeout=5)

            def reply(system, user):
                if workers == "2" and user["round"] == 1:
                    barrier.wait()  # Proves two discovery requests overlap.
                return {"rules": [proposal(user["pair"][0]["item_id"])]}

            client = FakeClient(reply)
            with tempfile.TemporaryDirectory() as temp, patch.dict("os.environ", {"LLM_WORKERS": workers}):
                rules, log = induce(rows, [], SemanticRuntime(client, build_index(rows)), Path(temp))
                self.assertEqual(log, json.loads((Path(temp) / "induction_log.json").read_text()))
            self.assertEqual([r["residual_after"] for r in log["rounds"]], [["b3"], []])
            self.assertEqual(log["stop_reason"], "no_residuals")
            self.assertEqual([d["pair"]["residual_id"] for d in log["decisions"]], ["b1", "b2", "b3"])
            for _, user in client.requests:
                self.assertEqual(len(user["search_history"]), 0 if user["round"] == 1 else 2)
            results.append((rules, log))
        self.assertEqual(results[0], results[1])

    @patch.dict("os.environ", {"LLM_WORKERS": "2"}, clear=True)
    def test_parallel_transport_cannot_overspend_last_http_attempt(self):
        barrier = threading.Barrier(2, timeout=5)
        value = dict(verdict="no", quote="", reason="fixture")

        def prepare(*args, **kwargs):
            barrier.wait()  # Both callers passed the early budget check.
            return Request(*args, **kwargs)

        def respond(*args, **kwargs):
            return io.BytesIO(json.dumps(dict(choices=[dict(message=dict(content=json.dumps(value)))])).encode())

        with tempfile.TemporaryDirectory() as temp:
            client = ChatClient(temp, api_key="fixture", dotenv=Path(temp) / "none", max_calls=1, pause=0)
            with patch("solution.llm.Request", side_effect=prepare), patch("solution.llm.urlopen", side_effect=respond) as http:
                results = pmap(lambda user: client.request("system", user, VERDICT_SCHEMA), ["one", "two"])
            self.assertEqual(http.call_count, 1)
            self.assertEqual(client.network_calls, 1)
            self.assertEqual(client.stats()["network_calls"], 1)
            self.assertEqual(results.count(value), 1)
            self.assertEqual(results.count(None), 1)


if __name__ == "__main__":
    unittest.main()
