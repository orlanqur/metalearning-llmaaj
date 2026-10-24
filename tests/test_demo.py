"""One offline integration test of the jury CLI and its evidence contract."""

import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from solution.adapt import adapt
from solution.eval import predict
from solution.facts import FactSheet
from solution.semantic import SemanticRuntime

ROOT = Path(__file__).resolve().parents[1]


class DemoTests(unittest.TestCase):
    def test_cli_verdict_evidence_retrieval_and_inputs(self):
        def rows(name):
            with (ROOT / "data" / name).open(encoding="utf-8", newline="") as stream:
                return [dict(item_id=r["item_id"], topic=r["topic"], label=r["label"],
                             context=json.loads(r["context"]), conversation=json.loads(r["conversation"]))
                        for r in csv.DictReader(stream)]

        train, public = rows("public_train.csv"), rows("public_test.csv")
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "train.jsonl"
            source.write_text("".join(json.dumps(r) + "\n" for r in train), encoding="utf-8")
            artifacts = base / "artifacts"
            adapt(source, artifacts, no_model=True)
            manifest = json.loads((artifacts / "rules_spec.json").read_text())
            index = json.loads((artifacts / "fewshot_index.json").read_text())

            def run(*args):
                return subprocess.run([sys.executable, "-S", str(ROOT / "demo/judge_demo.py"),
                                       "--artifacts", str(artifacts), *args],
                                      cwd=base, capture_output=True, text=True, timeout=20)

            before = {p.relative_to(artifacts): p.read_bytes() for p in artifacts.rglob("*") if p.is_file()}
            selected = [next(r for r in public if predict(r, manifest["rules"]) == label)
                        for label in ("bad", "good")]
            selected += [next(r for r in train if predict(r, manifest["rules"]) == "bad")]
            for row in selected:
                with self.subTest(item_id=row["item_id"]):
                    checks = []
                    expected = predict(row, manifest["rules"], details=checks)
                    result = run("--id", row["item_id"])
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(f"Verdict: {expected}\n", result.stdout)
                    hit = next((c for c in checks if c["violated"]), None)
                    if hit:
                        rule = next(r for r in manifest["rules"] if r["id"] == hit["rule_id"])
                        self.assertIn(f"Rule: {rule['id']} ", result.stdout)
                        self.assertIn(f"Condition: {rule['violation']}", result.stdout)
                        for quote in hit["evidence"]["quotes"]:
                            self.assertTrue(any(quote["text"] in m["content"] for m in row["conversation"]))
                            self.assertIn("> " + quote["text"].replace("\n", "\n> "), result.stdout)
                    else:
                        self.assertIn("Rule: none fired", result.stdout)
                    neighbors = SemanticRuntime(None, index).fewshot(FactSheet.from_row(row), row["item_id"])
                    self.assertEqual(len(neighbors), 3)
                    self.assertEqual(result.stdout.count("| label="), 3)
                    for neighbor in neighbors:
                        self.assertNotEqual(neighbor["item_id"], row["item_id"])
                        original = next(r for r in train if r["item_id"] == neighbor["item_id"])
                        self.assertEqual(neighbor["label"], original["label"])
                        self.assertIn(f"- {neighbor['item_id']} | label={original['label']}", result.stdout)

            row = selected[0]
            dialog, context = base / "dialog.json", base / "context.json"
            dialog.write_text(json.dumps(row["conversation"]), encoding="utf-8")
            context.write_text(json.dumps(dict(topic=row["topic"], context=row["context"])), encoding="utf-8")
            result = run("--dialog-file", str(dialog), "--context-file", str(context))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Verdict: bad", result.stdout)
            context.write_text(json.dumps(row["context"]), encoding="utf-8")
            result = run("--dialog-file", str(dialog), "--context-file", str(context), "--topic", row["topic"])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Verdict: bad", result.stdout)
            for args in [("--id", "missing-id"), ("--dialog-file", str(dialog)),
                         ("--dialog-file", str(dialog), "--context-file", str(context))]:
                result = run(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn("demo failed:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(before, {p.relative_to(artifacts): p.read_bytes()
                                     for p in artifacts.rglob("*") if p.is_file()})

            # An unavailable semantic rule can produce bad via majority, not a hit.
            manifest["rules"] = [dict(id="unknown", topic=row["topic"], status="active", priority=1,
                                      checker="llm_predicate", applicability={}, params=dict(text="Test rule"),
                                      violation="Test rule")]
            manifest["topic_majority"] = {row["topic"]: "bad"}
            (artifacts / "rules_spec.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = run("--id", row["item_id"])
            self.assertEqual(result.returncode, 0, result.stderr)
            for expected in ("Verdict: bad", "Rule: none fired", "manifest topic_majority", "Unchecked/unknown rules: unknown"):
                self.assertIn(expected, result.stdout)


if __name__ == "__main__":
    unittest.main()
