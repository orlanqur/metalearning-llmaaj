"""BLIND-EVAL regressions and the concurrent model path."""

import json
import os
from pathlib import Path
import tempfile
import unittest

from solution.checkers import opening_request
from solution.facts import FactSheet
from solution.io import load_rows
from solution.verify import verify


def write_rows(rows):
    path = Path(tempfile.mkdtemp()) / "rows.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


class FakeClient:
    available = True


class FakeRuntime:
    """Answers 'yes' for dialogs whose assistant text contains 'done'; no network."""
    client = FakeClient()

    def check(self, facts, params, item_id=None):
        hit = any("done" in t["text"] for t in facts.assistant_turns)
        return dict(verdict="yes" if hit else "no", quote="done" if hit else "", reason="fake")


class RobustnessTests(unittest.TestCase):
    def test_empty_and_malformed_conversations_do_not_abort_loading(self):
        base = dict(topic="savings", context=dict(today="2026-01-10"))
        rows = load_rows(write_rows([
            dict(base, item_id="empty", conversation=[]),
            dict(base, item_id="extra", conversation=[dict(role="user", content="hi", name="x"), 7,
                                                      dict(role="robot", content="?")])]))
        self.assertEqual([r["conversation"] for r in rows], [[], [dict(role="user", content="hi")]])

    def test_greeting_turn_does_not_hide_the_request(self):
        convo = [dict(role="user", content="Hello."), dict(role="user", content="How much did I spend?"),
                 dict(role="assistant", content="You spent 10 MXN.")]
        facts = FactSheet.from_row(dict(item_id="x", topic="spending", context=dict(today="2026-01-10"), conversation=convo))
        self.assertIn("spend", opening_request(facts))

    def test_concurrent_verify_matches_sequential(self):
        rows = [dict(item_id=f"r{i}", topic="savings", label="bad" if i % 2 else "good", context=dict(today="2026-01-10"),
                     conversation=[dict(role="user", content="move it"),
                                   dict(role="assistant", content="done" if i % 2 else "not yet")]) for i in range(12)]
        rule = dict(id="savings.ACTION.semantic", topic="savings", checker="llm_predicate", params=dict(text="claims done"),
                    applicability={}, priority=10, criterion="claims done")
        results = []
        for workers in ("1", "6"):
            os.environ["LLM_WORKERS"] = workers
            results.append(verify([rule], rows, FakeRuntime())[0])
        os.environ.pop("LLM_WORKERS")
        self.assertEqual(results[0]["example_item_ids"], results[1]["example_item_ids"])
        self.assertEqual((results[1]["TP"], results[1]["FP"]), (6, 0))


if __name__ == "__main__":
    unittest.main()
