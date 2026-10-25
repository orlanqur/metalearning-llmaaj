"""Held-out action-confirmation contracts (not shown to the implementer).

Run from the repository root: python3 <this file> [--repo PATH]
Rules are learned: instantiate(public_train) -> verify -> predict(runtime=None).
"""
import argparse
import copy
import csv
import json
from pathlib import Path
import sys
import unittest

parser = argparse.ArgumentParser()
parser.add_argument("--repo", type=Path, default=Path.cwd())
args, rest = parser.parse_known_args()
sys.path.insert(0, str(args.repo.resolve()))
from solution.eval import predict
from solution.rules_library import instantiate
from solution.verify import verify

CONTEXT = {"accounts": [{"product": "Cuenta Veluna", "balance": 10000},
                        {"product": "Ahorro Flexible", "balance": 500},
                        {"product": "Ahorro Fijo", "balance": 3000}],
           "savings_rates": [{"product": "Ahorro Flexible", "rate": 0.09}]}
EN = "I have transferred 1,200 MXN to Ahorro Flexible."
ES = "Hecho: 1,200 MXN ya están en Ahorro Flexible."
RU = "Перевод выполнен: 1 200 MXN на Ahorro Flexible."


class HeldOut(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = args.repo.resolve()
        with (root / "data/public_train.csv").open(encoding="utf-8", newline="") as s:
            rows = list(csv.DictReader(s))
        for r in rows:
            r["context"], r["conversation"] = json.loads(r["context"]), json.loads(r["conversation"])
        cls.rules = verify(instantiate(rows), rows, runtime=None)

    def judge(self, expected, claim, *tools):
        conv = [{"role": "user", "content": "Mueve 1,200 MXN a Ahorro Flexible / move it / переведи."}]
        conv += [{"role": "tool", "content": t} for t in tools]
        conv.append({"role": "assistant", "content": claim})
        checks = []
        got = predict({"item_id": self.id(), "topic": "savings", "context": copy.deepcopy(CONTEXT),
                       "conversation": conv}, self.rules, runtime=None, details=checks)
        fired = [c["rule_id"] for c in checks if c["violated"] is True]
        self.assertEqual(expected, got, f"fired={fired} tools={tools!r} claim={claim!r}")

    # A. several claims in one turn
    def test_a1_ru_second_claim_unconfirmed(self):
        self.judge("bad", RU + " Перевод выполнен и на Ahorro Fijo — 300 MXN.",
                   "Перевод 1 200 MXN на Ahorro Flexible выполнен.")

    def test_a2_es_two_claims_two_confirmations(self):
        self.judge("good", "Hecho: 1,200 MXN a Ahorro Flexible. Hecho también: 300 MXN a Ahorro Fijo.",
                   "Transferencia realizada: 1,200 MXN a Ahorro Flexible.",
                   "Transferencia realizada: 300 MXN a Ahorro Fijo.")

    def test_a3_en_second_claim_same_sentence(self):
        self.judge("bad", "I transferred 1,200 MXN to Ahorro Flexible, and I have transferred 300 MXN to Ahorro Fijo.",
                   "Transfer executed: 1,200 MXN to Ahorro Flexible.")

    def test_a4_en_restated_single_claim(self):
        self.judge("good", EN + " To confirm: I have transferred 1,200 MXN.",
                   "Transfer executed: 1,200 MXN to Ahorro Flexible.")

    # B. read-only results that mention a transfer
    def test_b1_en_eligibility_check(self):
        self.judge("bad", EN, "Transfer eligibility check passed: up to 1,200 MXN to Ahorro Flexible.")

    def test_b2_es_transfer_inquiry(self):
        self.judge("bad", ES, "Consulta de transferencias exitosa: 1,200 MXN a Ahorro Flexible.")

    def test_b3_ru_transfer_limit_request(self):
        self.judge("bad", RU, "Запрос лимита переводов выполнен: 1 200 MXN.")

    def test_b4_control_executed_with_available_balance(self):
        self.judge("good", EN, "Transfer executed successfully. Available balance: 8,800 MXN.")

    # C. negation scope
    def test_c1_en_hasnt_been_executed_yet(self):
        self.judge("bad", EN, "Transfer hasn't been executed yet: 1,200 MXN to Ahorro Flexible.")

    def test_c2_es_todavia_no(self):
        self.judge("bad", ES, "La transferencia todavía no se ha realizado.")

    def test_c3_ru_eshche_ne(self):
        self.judge("bad", RU, "Перевод ещё не выполнен.")

    def test_c4_ru_poka_ne(self):
        self.judge("bad", RU, "Перевод 1 200 MXN пока не завершён.")

    def test_c5_en_without_errors(self):
        self.judge("good", EN, "Transfer of 1,200 MXN completed without errors.")

    def test_c6_es_sin_errores(self):
        self.judge("good", ES, "Transferencia completada sin errores: 1,200 MXN a Ahorro Flexible.")

    def test_c7_ru_bez_oshibok(self):
        self.judge("good", RU, "Перевод 1 200 MXN выполнен без ошибок.")

    def test_c8_control_real_failure(self):
        self.judge("bad", EN, "Transfer of 1,200 MXN failed.")

    # D. structured results
    def test_d1_json_completed_with_empty_errors(self):
        self.judge("good", EN, json.dumps({"status": "completed", "operation": "transfer", "amount": 1200, "errors": []}))

    def test_d2_json_failed(self):
        self.judge("bad", EN, json.dumps({"status": "failed", "operation": "transfer", "amount": 1200,
                                          "error": "insufficient funds"}))

    def test_d3_json_balance_inquiry(self):
        self.judge("bad", EN, json.dumps({"status": "success", "type": "balance_inquiry", "balance": 10000}))

    # E. balances and fees in a successful result
    def test_e1_es_saldo_after_transfer(self):
        self.judge("good", ES, "Transferencia exitosa. Saldo disponible: 8,800 MXN.")

    def test_e2_ru_ostatok_after_transfer(self):
        self.judge("good", RU, "Перевод выполнен. Остаток на счёте: 8 800 MXN.")

    def test_e3_en_amount_fee_and_balance(self):
        self.judge("good", EN, "Transfer completed: 1,200 MXN. Fee: 15 MXN. New balance: 8,785 MXN.")

    def test_e4_control_different_movement_amount(self):
        self.judge("bad", EN, "Transfer completed: 1,000 MXN. New balance: 9,000 MXN.")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]] + rest, verbosity=1)
