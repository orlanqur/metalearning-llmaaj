"""Post-hackathon: numbers must be bound to the claim they belong to (P2-01, P2-02).

Rules are learned the normal way: instantiate(public_train) -> verify -> predict.
Synthetic conversations are contracts for the rules' meaning, not accuracy evidence.
"""

import copy
import csv
import json
from pathlib import Path
import unittest

from solution.checkers import rate_claims, run_check
from solution.eval import predict
from solution.facts import FactSheet
from solution.rules_library import instantiate
from solution.verify import verify

ROOT = Path(__file__).resolve().parents[1]

SAVINGS = {
    "accounts": [{"product": "Cuenta Veluna", "balance": 75400},
                 {"product": "Ahorro Flexible", "balance": 2000},
                 {"product": "Ahorro Fijo", "balance": 5000}],
    "savings_rates": [{"product": "Ahorro Flexible", "rate": 0.10},
                      {"product": "Ahorro Fijo", "term_months": 12, "rate": 0.12}],
}
SPENDING = {
    "today": "2026-10-15",
    "monthly_summary": [{"month": "2026-09", "purchases": 16980, "refunds": 0,
                         "transfers_to_others": 0, "transfers_own": 0}],
}


def conversation(*answers):
    messages = []
    for answer in answers:
        messages += [{"role": "user", "content": "Question"}, {"role": "assistant", "content": answer}]
    return messages


class RateClaimKinds(unittest.TestCase):
    def kinds(self, answer):
        row = {"topic": "savings", "context": SAVINGS, "conversation": conversation(answer)}
        return [c["kind"] for c in rate_claims(FactSheet.from_row(row))]

    def test_shares_rates_and_other_metrics(self):
        cases = {
            "Ahorro Flexible paga 10% anual. Puedes ahorrar el 25% de tus ingresos.": ["rate", "share"],
            "Отложите 30% дохода на Ahorro Flexible под 10% годовых.": ["share", "rate"],
            "Move 50% to Ahorro Flexible, which earns 10% a year.": ["share", "rate"],
            "Ставка Ahorro Flexible — 10% годовых, а инфляция около 4%.": ["rate", "other"],
            "The inflation rate is 4%.": ["other"],
            "Fijo gives you 2% more than Flexible.": ["relative"],
            "| Ahorro Flexible | 10% | 200 MXN |": ["rate"],
            "Flexible (10%) or Fijo (12%).": ["rate", "rate"],
            "Te da 12% de interés anual.": ["rate"],
            "That is roughly 15%.": ["unbound"],
        }
        for answer, expected in cases.items():
            with self.subTest(answer=answer):
                self.assertEqual(expected, self.kinds(answer))


class LearnedRuleDecisions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT / "data/public_train.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            for key in ("context", "conversation"):
                row[key] = json.loads(row[key])
        cls.rules = verify(instantiate(rows), rows, runtime=None)
        active = {rule["id"] for rule in cls.rules if rule["status"] == "active"}
        required = {"savings.RATE.selected_tariff", "savings.RATE.ahorro_flexible",
                    "savings.AMOUNT.balance_cuenta_veluna", "spending.AMOUNT.confirmed_purchases"}
        missing = required - active
        if missing:
            raise AssertionError(f"Rules expected to be learned as active: {sorted(missing)}")

    def judge(self, expected, *answers, topic="savings", context=SAVINGS):
        row = {"item_id": self.id(), "topic": topic, "context": copy.deepcopy(context),
               "conversation": conversation(*answers)}
        checks = []
        actual = predict(row, self.rules, runtime=None, details=checks)
        fired = [c["rule_id"] for c in checks if c["violated"] is True]
        self.assertEqual(expected, actual, f"fired={fired}; answers={answers!r}")
        return checks

    # P2-01: percentages that are not a rate claim
    def test_share_of_salary_in_a_later_turn_ru(self):
        self.judge("good", "Ставка Ahorro Flexible — 10% годовых.", "Обычно советуют откладывать 15% от зарплаты.")

    def test_share_of_income_in_the_same_turn_es(self):
        self.judge("good", "Ahorro Flexible paga 10% anual. Puedes ahorrar el 25% de tus ingresos cada mes.")

    def test_inflation_in_the_same_sentence(self):
        self.judge("good", "Ahorro Flexible rinde 10% anual, mientras la inflación ronda el 4%.")

    def test_two_products_with_their_own_correct_rates(self):
        self.judge("good", "Ahorro Flexible paga 10% anual y Ahorro Fijo a 12 meses paga 12% anual.")

    # P2-01: wrong rates must still be bad
    def test_wrong_second_product_among_a_share_and_a_correct_rate(self):
        self.judge("bad", "Ahorro Flexible earns 10% a year and you could set aside 20% of your income; "
                          "Ahorro Fijo pays 13% annually.")

    def test_wrong_rate_after_a_share_turn(self):
        self.judge("bad", "Save 20% of your income.", "Ahorro Flexible pays 14% annually.")

    def test_other_products_rate_attributed_to_flexible(self):
        self.judge("bad", "Ahorro Flexible te da 12% de interés anual.")

    def test_allocation_verb_with_a_rate_is_still_a_rate(self):
        self.judge("bad", "Откладывайте деньги под 14% годовых.")

    def test_unbound_percentage_is_never_unknown(self):
        checks = self.judge("good", "Ahorro Flexible pays 10% annually. That is roughly 15%.")
        rate = [c for c in checks if c["rule_id"].startswith("savings.RATE.")]
        self.assertTrue(rate and all(c["violated"] is False for c in rate))

    # P2-02: other amounts in a balance message
    def test_three_accounts_all_correct(self):
        self.judge("good", "Сейчас на вашем счете Cuenta Veluna 75 400 MXN, на Ahorro Flexible — 2 000 MXN, "
                           "в Ahorro Fijo — 5 000 MXN.")

    def test_wrong_balance_next_to_correct_other_accounts(self):
        self.judge("bad", "Сейчас на вашем счете Cuenta Veluna 74 000 MXN, на Ahorro Flexible — 2 000 MXN.")

    def test_payment_after_the_balance(self):
        self.judge("good", "Сейчас на вашем счете Cuenta Veluna 75 400 MXN. Платёж по кредиту — 350 MXN до 5 ноября.")

    def test_hypothetical_operation_between_claim_and_amount(self):
        self.judge("good", "Сейчас на вашем счете Cuenta Veluna после перевода 400 MXN останется 75 000 MXN.")

    def test_decimal_format_and_rounding_tolerance(self):
        self.judge("good", "Сейчас на вашем счете Cuenta Veluna 75 400,00 MXN.")
        self.judge("good", "Сейчас на вашем счете Cuenta Veluna 75 380 MXN.")

    def test_wrong_balance_with_a_suggested_transfer_is_still_bad(self):
        self.judge("bad", "Сейчас на вашем счете Cuenta Veluna 80 000 MXN. Можно перевести 5 000 MXN на Ahorro Flexible.")

    def test_later_turn_contradiction_is_still_bad(self):
        self.judge("bad", "У вас на Cuenta Veluna 75 400 MXN.", "Сейчас на вашем счете Cuenta Veluna 72 000 MXN.")

    # The same binding applies to the confirmed-spending claim
    def test_confirmed_spending_with_a_savings_suggestion(self):
        self.judge("good", "Confirmado: en septiembre gastaste 16,980 MXN en compras. Te sugiero ahorrar 2,000 MXN al mes.",
                   topic="spending", context=SPENDING)

    def test_wrong_confirmed_spending_next_to_another_amount(self):
        self.judge("bad", "Confirmado: en septiembre gastaste 15,000 MXN en compras. Te sugiero ahorrar 2,000 MXN al mes.",
                   topic="spending", context=SPENDING)


class ChangedBalancePoison(unittest.TestCase):
    def poison(self, answer):
        row = {"topic": "savings", "context": SAVINGS, "conversation": conversation(answer)}
        return FactSheet.from_row(row).poison["changed_balances"]

    def test_only_the_amount_bound_to_a_product_counts(self):
        self.assertEqual([], self.poison("Сейчас на вашем счете Cuenta Veluna 75 400 MXN, на Ahorro Flexible — 2 000 MXN."))
        self.assertEqual([1500.0], self.poison("Сейчас на вашем счете Cuenta Veluna 75 400 MXN, на Ahorro Flexible — 1 500 MXN."))


if __name__ == "__main__":
    unittest.main()
