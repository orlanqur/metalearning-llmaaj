"""Tests of audit oracles; no solution imports or source reads."""
import json
from pathlib import Path
import tempfile
import unittest

from explanation_check import check
from run import TOPICS, grouped_folds, context_key, validate_predictions


class PredictionContract(unittest.TestCase):
    def check_csv(self, content):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "predictions.csv"
            path.write_text(content)
            return validate_predictions(path, ["a", "b"])[1]

    def test_accepts_exact_ids_in_any_row_order(self):
        self.assertEqual(self.check_csv("item_id,label\nb,bad\na,good\n"), [])

    def test_rejects_invalid_outputs(self):
        for content in (
            "item_id,label\na,good\na,bad\nb,bad\n",
            "item_id,label\na,good\n",
            "item_id,label\na,good\nb,bad\nc,good\n",
            "item_id,label\na,GOOD\nb,bad\n",
            "item_id,label,confidence\na,good,1\nb,bad,1\n",
            "item_id,label\na,good,extra\nb,bad\n",
        ):
            with self.subTest(content=content):
                self.assertTrue(self.check_csv(content))


class GroupContract(unittest.TestCase):
    def test_context_groups_do_not_leak_and_input_order_does_not_matter(self):
        rows = []
        for topic in TOPICS:
            for index in range(12):
                for copy in range(2):
                    context = {"topic_source": topic, "n": index}
                    if copy:
                        context = dict(reversed(list(context.items())))
                    rows.append({"item_id": f"{topic}-{index}-{copy}", "topic": topic,
                                 "context": context, "label": "good" if copy else "bad"})
        folds = grouped_folds(rows)
        reverse = grouped_folds(list(reversed(rows)))
        self.assertEqual([{r["item_id"] for r in b} for b in folds],
                         [{r["item_id"] for r in b} for b in reverse])
        for i, bucket in enumerate(folds):
            for other in folds[i + 1:]:
                self.assertFalse({context_key(r) for r in bucket} & {context_key(r) for r in other})
        self.assertEqual(sum(map(len, folds)), len(rows))


class ExplanationOracle(unittest.TestCase):
    def test_evidence_and_negative_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            train, spec, explanation = [root / n for n in ("train.jsonl", "rules_spec.json", "explanation.md")]
            iid = "a" * 32
            quote = "This financial claim is unsupported by the available records."
            train.write_text(json.dumps({"item_id": iid, "label": "bad", "conversation": [{"content": quote}]}) + "\n")
            spec.write_text(json.dumps({"rules": [{"id": "R1"}]}))
            text = ("# Criteria\nRule `R1`: if a factual claim is unsupported, label bad; otherwise good.\n"
                    "# Priorities\nAny violation overrides completeness.\n"
                    "# Boundaries\nWhen records are missing, rule `R1` has limited evidence.\n"
                    + iid + " label bad: " + quote + " This illustrates rule `R1`.\n")
            explanation.write_text(text)
            result = check(explanation, train, spec)
            self.assertTrue(result["all_structural_checks_pass"])
            linked = text.replace(iid + ' label bad: ' + quote + ' This illustrates rule `R1`.',
                'Rule `R1`: [' + iid + '](#example-' + iid + ') (bad).\n\n'
                '## Appendix\n<a id="example-' + iid + '"></a>\n**' + iid + ' expert label `bad`**\n\n> ' + quote)
            explanation.write_text(linked + '\nStatus: `skipped_no_key_or_disabled`.\n')
            self.assertTrue(check(explanation, train, spec)['all_structural_checks_pass'])
            explanation.write_text(linked.replace('(bad).', '(good).'))
            self.assertFalse(check(explanation, train, spec)['criteria']['links_to_training_examples']['structural_pass'])
            explanation.write_text(text.replace("label bad:", "label good:"))
            self.assertFalse(check(explanation, train, spec)["criteria"]["links_to_training_examples"]["structural_pass"])
            explanation.write_text(text.replace(iid, "b" * 32))
            self.assertFalse(check(explanation, train, spec)["criteria"]["links_to_training_examples"]["structural_pass"])
            explanation.write_text(text.replace("`R1`", "`R2`"))
            self.assertFalse(check(explanation, train, spec)["criteria"]["consistency_with_implementation"]["structural_pass"])


if __name__ == "__main__":
    unittest.main()
