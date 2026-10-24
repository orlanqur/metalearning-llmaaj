"""Hand-calculated invariants and train-only selection/serving contracts."""

import copy
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from solution.adapt import adapt, explain
from solution.checkers import asks_known_field, llm_predicate, run_check, turn_contradiction
from solution.eval import evaluate, predict
from solution.facts import FactSheet, close, dates_in, money, number, numbers
from solution.io import load_rows
from solution.verify import verify


def row(topic="financial_position", answer="You have 100 MXN.", context=None, label="good"):
    return dict(item_id="synthetic", topic=topic, label=label,
                context=context or dict(today="2026-01-10", accounts=[dict(product="Cash", balance=100, current_debt=20)]),
                conversation=[dict(role="user", content="How much money?"), dict(role="assistant", content=answer)])


class FactsTests(unittest.TestCase):
    def test_formats_and_tolerances(self):
        for text in ("21,617", "21 617", "21617.00", "21\u00a0617", "21\u202f617", "21.617,00", "21,617.00"):
            self.assertEqual(number(text), 21617)
            self.assertEqual(money(f"**{text} MXN**"), [21617])
        self.assertEqual(numbers("21.6k"), [])
        self.assertEqual(money("21.6k MXN"), [])
        self.assertTrue(close(101, 100))
        self.assertFalse(close(101.01, 100))
        self.assertTrue(close(10050, 10000))
        self.assertFalse(close(10050.01, 10000))

    def test_calendar_window_crosses_year_and_refunds(self):
        c = dict(today="2026-01-10", monthly_summary=[
            dict(month="2025-10", purchases=100, refunds=10, transfers_to_others=20, transfers_own=30),
            dict(month="2025-11", purchases=200, refunds=20, transfers_to_others=30, transfers_own=40),
            dict(month="2025-12", purchases=300, refunds=30, transfers_to_others=40, transfers_own=50),
            dict(month="2026-01", purchases=999, refunds=0)])
        f = FactSheet.from_context(c, "spending")
        self.assertEqual(f.expected["previous_month"], "2025-12")
        self.assertEqual(f.expected["averages"]["net_purchases"], 180)
        self.assertEqual(f.expected["averages"]["combined"], 210)
        self.assertEqual(f.poison["own_transfers"], [250, 750])
        del c["monthly_summary"][1]
        self.assertEqual(FactSheet.from_context(c, "spending").expected["averages"], {})

    def test_hold_debt_locked_and_credit_remain_distinct(self):
        c = dict(today="2026-01-10", accounts=[dict(product="Cash", balance=100, on_hold=10),
            dict(product="Ahorro Fijo", balance=200, maturity_date="2026-02-01"),
            dict(product="Credit", current_debt=30, available_credit=500, credit_limit=600)])
        f = FactSheet.from_context(c, "financial_position")
        self.assertEqual([f.expected[k] for k in ("own_gross", "available_now", "liquid", "net_after_debt")], [300, 290, 90, 270])
        self.assertIn(800, f.poison["credit_as_money"])
        self.assertIn(900, f.poison["credit_as_money"])

    def test_transaction_scope_refund_and_status(self):
        c = dict(transactions=[dict(merchant="Shop", category="food", date="2026-01-01", type="purchase", status="completed", amount=-100),
                               dict(merchant="Shop", category="food", date="2026-01-02", type="refund", status="completed", amount=20),
                               dict(merchant="Shop", category="food", date="2026-01-03", type="purchase", status="pending", amount=-999)])
        f = FactSheet.from_context(c, "spending")
        self.assertEqual(f.transactions["merchant|shop|2026-01"], dict(count=2, gross=100, refunds=20, net=80))
        self.assertEqual(f.transactions["category|food|2026-01"]["net"], 80)

    def test_tariff_is_taken_from_current_context(self):
        c = dict(user=dict(plus_subscription=True), savings_rates=[dict(product="Ahorro Flexible", rate=.09, rate_with_plus=.12)])
        f = FactSheet.from_context(c, "savings")
        self.assertEqual(f.rates[0]["rate"], .12)
        self.assertEqual(f.poison["opposite_rates"], [9])
        c["user"]["plus_subscription"] = False
        self.assertEqual(FactSheet.from_context(c, "savings").rates[0]["rate"], .09)

    def test_dates_preserve_explicit_year(self):
        self.assertEqual(dates_in("11 сентября 2027, 2027-09-11, 11.09.2027"), {(2027, 9, 11)})
        f = FactSheet.from_context(dict(today="2026-01-01", due_date="2026-01-20"), "credit", [dict(role="assistant", content="Pay on 2027-01-20.")])
        rule = dict(id="date", topic="credit", checker="date_mismatch", params={}, applicability={})
        self.assertTrue(run_check(rule, f)["violated"])


class CheckerTests(unittest.TestCase):
    def test_known_field_must_exist_and_false_is_known(self):
        params = dict(field="user.plus_subscription", patterns=["confirm subscription"])
        r = row(answer="Please confirm subscription.", context=dict(user=dict(plus_subscription=False)))
        self.assertTrue(asks_known_field(FactSheet.from_row(r), params, "ask")["violated"])
        r["context"] = {}
        self.assertFalse(asks_known_field(FactSheet.from_row(r), params, "ask")["violated"])

    def test_later_turn_contradiction_and_rounding(self):
        r = row(answer="Balance now: 100 MXN.")
        r["conversation"] += [dict(role="user", content="Confirm?"), dict(role="assistant", content="Balance now: 120 MXN.")]
        p = dict(kind="account_balance", product="Cash", claim_pattern="balance now")
        # Product scope prevents confusing a debt or other account with this balance.
        p["product"] = "Cash"
        r["conversation"][-1]["content"] = "Cash balance now: 120 MXN."
        self.assertTrue(turn_contradiction(FactSheet.from_row(r), p)["violated"])
        r["conversation"][-1]["content"] = "Cash balance now: 101 MXN."
        self.assertFalse(turn_contradiction(FactSheet.from_row(r), p)["violated"])

    def test_llm_is_not_checked(self):
        f = FactSheet.from_row(row())
        self.assertIsNone(llm_predicate(f, dict(text="semantic question")))
        rule = dict(id="llm", topic=f.topic, applicability={}, checker="llm_predicate", params={})
        self.assertIsNone(run_check(rule, f)["violated"])

    def test_verify_demotes_false_positive_and_retains_evidence(self):
        rule = dict(id="synthetic_rule", topic="financial_position", applicability={},
                    checker="lexical_predicate", params=dict(patterns=["unsupported"], meaning="fixture"), priority=1)
        rows = [row(answer="unsupported", label="bad"), row(answer="unsupported", label="good")]
        rows[1]["item_id"] = "counterexample"
        result = verify([rule], rows)[0]
        self.assertEqual((result["TP"], result["FP"], result["precision"], result["coverage"]), (1, 1, .5, 1))
        self.assertEqual(result["status"], "boundary")
        self.assertEqual(result["counterexample_item_ids"], ["counterexample"])
        rows[1]["conversation"][-1]["content"] = "supported"
        self.assertEqual(verify([rule], rows)[0]["status"], "active")


class PipelineTests(unittest.TestCase):
    def test_artifacts_explanation_eval_and_no_label_leak(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            rows = [row(answer="100 MXN", label="bad"), row(answer="80 MXN", label="good")]
            rows[1]["item_id"] = "second"
            train = base / "train.jsonl"
            train.write_text("".join(json.dumps(r)+"\n" for r in rows))
            adapt(train, base / "artifacts", no_model=True)
            manifest = json.loads((base / "artifacts/rules_spec.json").read_text())
            self.assertEqual((base / "artifacts/explanation.md").read_text(), explain(manifest))
            evaluate(train, base / "artifacts", base / "pred.csv", no_model=True)
            with (base / "pred.csv").open() as stream:
                reader = csv.DictReader(stream)
                self.assertEqual(reader.fieldnames, ["item_id", "label"])
                self.assertEqual([r["label"] for r in reader], ["bad", "good"])
            loaded = load_rows(train)
            self.assertNotIn("label", loaded[0])
            changed = copy.deepcopy(loaded[0]); changed["item_id"] = "opaque-new-id"; changed["label"] = "good"
            self.assertEqual(predict(loaded[0], manifest["rules"]), predict(changed, manifest["rules"]))
            changed["context"]["accounts"][0]["current_debt"] = 0
            self.assertEqual(predict(changed, manifest["rules"]), "good")

    def test_empty_active_rules_default_good(self):
        self.assertEqual(predict(row(answer="anything"), []), "good")

    def test_duplicate_ids_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.jsonl"
            path.write_text((json.dumps(row())+"\n")*2)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_rows(path)

    def test_cli_defaults_visible_without_site_packages(self):
        result = subprocess.run([sys.executable, "-S", "-m", "solution", "eval", "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--artifacts", result.stdout)


if __name__ == "__main__":
    unittest.main()
