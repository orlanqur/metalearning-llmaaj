"""P2-03: a completed-action claim is confirmed only by a PRECEDING successful tool result.

Unit tests call the checker directly with the library's own ACTION parameters; the
end-to-end class verifies the rule on public_train and judges synthetic dialogs
through predict(), so the rule's activation (TP > 0, FP = 0, nothing unchecked)
is asserted rather than assumed. Phrases are deliberately different from the
external regression suite.
"""

import copy
import csv
import json
from pathlib import Path
import unittest

from solution.checkers import classify_tool_event, lexical_predicate, run_check
from solution.eval import predict
from solution.facts import FactSheet
from solution.rules_library import instantiate
from solution.verify import verify

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = dict(today="2026-01-10",
               accounts=[dict(product="Cuenta Veluna", balance=10000), dict(product="Ahorro Flexible", balance=500),
                         dict(product="Ahorro Fijo", balance=3000, maturity_date="2026-06-01")],
               savings_rates=[dict(product="Ahorro Flexible", rate=0.09)])
ASK_EN, CLAIM_EN = "Please move 2 500 MXN to Ahorro Flexible.", "I have transferred 2 500 MXN to Ahorro Flexible."
ASK_ES, CLAIM_ES = "Pasa 2 500 MXN a Ahorro Flexible, por favor.", "Hecho — ahora en Ahorro Flexible tienes 3 000 MXN."
ASK_RU, CLAIM_RU = "Переведи 2 500 MXN на Ahorro Flexible.", "Перевод выполнен, 2 500 MXN отправлены на Ahorro Flexible."


def action_params():
    rows = [dict(item_id="seed", topic="savings", label="bad", context=copy.deepcopy(CONTEXT),
                 conversation=[dict(role="user", content=ASK_EN), dict(role="assistant", content=CLAIM_EN)])]
    return next(c for c in instantiate(rows) if c["id"] == "savings.ACTION.lexical")["params"]


def dialog(*messages, tool_after=None):
    conversation = [dict(role=role, content=content) for role, content in messages]
    if tool_after is not None:
        conversation.append(dict(role="tool", content=tool_after))
    return conversation


class ToolEventClassificationTests(unittest.TestCase):
    def test_status_and_operation_vocabulary(self):
        cases = {
            "Transfer of 2 500 MXN completed.": ("success", "movement"),
            "Transferencia realizada con éxito: 2 500 MXN.": ("success", "movement"),
            "Перевод 2 500 MXN на Ahorro Flexible выполнен успешно.": ("success", "movement"),
            "Transfer declined: insufficient funds.": ("failure", "movement"),
            "Transfer could not be completed.": ("failure", "movement"),
            "No se pudo realizar la transferencia.": ("failure", "movement"),
            "Перевод не выполнен: ошибка.": ("failure", "movement"),
            "Transfer is being processed.": ("pending", "movement"),
            "Transferencia en proceso.": ("pending", "movement"),
            "Transferencia programada para mañana.": ("pending", "movement"),
            "Перевод в обработке.": ("pending", "movement"),
            "Перевод будет выполнен завтра.": ("pending", "movement"),
            "Balance inquiry successful: 10 000 MXN.": ("success", "readonly"),
            "Consulta de saldo exitosa: 10 000 MXN.": ("success", "readonly"),
            "Запрос баланса выполнен: 10 000 MXN.": ("success", "readonly"),
            "OK": ("success", "unspecified"),
            "Request received.": ("unknown", "unspecified"),
        }
        for content, expected in cases.items():
            event = classify_tool_event(content)
            self.assertEqual((event["status"], event["operation"]), expected, content)

    def test_amounts_products_and_json_results(self):
        event = classify_tool_event("Transfer successful: 2,500.00 MXN from Cuenta Veluna to Ahorro Flexible.",
                                    ["Cuenta Veluna", "Ahorro Flexible", "Ahorro Fijo"])
        self.assertEqual(event["amounts"], [2500])
        self.assertEqual(event["products"], ["Cuenta Veluna", "Ahorro Flexible"])
        event = classify_tool_event('{"status": "completed", "operation": "transfer", "amount": "2,500", "currency": "MXN"}')
        self.assertEqual((event["status"], event["operation"], event["amounts"]), ("success", "movement", [2500]))
        event = classify_tool_event({"status": "failed", "reason": "insufficient funds"})
        self.assertEqual(event["status"], "failure")
        # Null, empty and false fields are absent cues, not failure words.
        event = classify_tool_event('{"status": "success", "operation": "transfer", "amount": 2500, "error": null, "failed": false, "message": ""}')
        self.assertEqual((event["status"], event["operation"], event["amounts"]), ("success", "movement", [2500]))
        self.assertEqual(classify_tool_event('{"ok": true}')["status"], "success")
        self.assertEqual(classify_tool_event('{"success": false}')["status"], "unknown")
        self.assertEqual(classify_tool_event(None)["status"], "unknown")


class ActionClaimCheckerTests(unittest.TestCase):
    def setUp(self):
        self.params = action_params()

    def violated(self, conversation, context=CONTEXT):
        facts = FactSheet.from_context(copy.deepcopy(context), "savings", conversation)
        return lexical_predicate(facts, self.params, "savings.ACTION.lexical")["violated"]

    def test_no_tool_message_is_a_violation_in_every_language(self):
        for ask, claim in ((ASK_EN, CLAIM_EN), (ASK_ES, CLAIM_ES), (ASK_RU, CLAIM_RU)):
            self.assertTrue(self.violated(dialog(("user", ask), ("assistant", claim))), claim)

    def test_preceding_matching_success_confirms_in_every_language(self):
        confirmations = {
            CLAIM_EN: "Transfer completed: 2 500 MXN from Cuenta Veluna to Ahorro Flexible.",
            CLAIM_ES: "Transferencia realizada con éxito: 2 500 MXN de Cuenta Veluna a Ahorro Flexible.",
            CLAIM_RU: "Перевод 2 500 MXN на Ahorro Flexible выполнен успешно.",
        }
        for (ask, claim), tool in zip(((ASK_EN, CLAIM_EN), (ASK_ES, CLAIM_ES), (ASK_RU, CLAIM_RU)), confirmations.values()):
            self.assertFalse(self.violated(dialog(("user", ask), ("tool", tool), ("assistant", claim))), claim)

    def test_failed_pending_and_readonly_results_do_not_confirm(self):
        for tool in ("Transfer declined: insufficient funds.", "No se pudo realizar la transferencia.",
                     "Перевод отклонен: недостаточно средств.", "Transfer of 2 500 MXN is being processed.",
                     "Transferencia en proceso.", "Перевод в обработке.", "Transferencia programada para mañana.",
                     "Balance inquiry successful: 10 000 MXN.", "Consulta de saldo exitosa: 10 000 MXN.",
                     "Rate lookup done: Ahorro Flexible 9%."):
            self.assertTrue(self.violated(dialog(("user", ASK_EN), ("tool", tool), ("assistant", CLAIM_EN))), tool)

    def test_success_after_the_claim_does_not_confirm_it(self):
        tool = "Transfer completed: 2 500 MXN from Cuenta Veluna to Ahorro Flexible."
        self.assertTrue(self.violated(dialog(("user", ASK_EN), ("assistant", CLAIM_EN), tool_after=tool)))
        self.assertTrue(self.violated(dialog(("user", ASK_RU), ("assistant", CLAIM_RU), tool_after=tool)))

    def test_success_for_a_different_amount_or_recipient_does_not_confirm(self):
        self.assertTrue(self.violated(dialog(("user", ASK_EN), ("tool", "Transfer completed: 250 MXN to Ahorro Flexible."),
                                             ("assistant", CLAIM_EN))))
        self.assertTrue(self.violated(dialog(("user", ASK_RU), ("tool", "Перевод 1 000 MXN выполнен успешно."),
                                             ("assistant", CLAIM_RU))))
        self.assertTrue(self.violated(dialog(("user", ASK_EN), ("tool", "Transfer completed: 2 500 MXN from Cuenta Veluna to Ahorro Fijo."),
                                             ("assistant", CLAIM_EN))))
        # Rounding within the shared tolerance and a success without any amount still confirm.
        self.assertFalse(self.violated(dialog(("user", ASK_EN), ("tool", "Transfer completed: 2,500.00 MXN to Ahorro Flexible."),
                                              ("assistant", CLAIM_EN))))
        self.assertFalse(self.violated(dialog(("user", ASK_EN), ("tool", "Transfer completed."), ("assistant", CLAIM_EN))))

    def test_indeterminate_or_unlinked_results_are_not_confirmation(self):
        for tool in ("OK", "Request received.", '{"ok": true}', "", "Card blocked successfully."):
            self.assertTrue(self.violated(dialog(("user", ASK_EN), ("tool", tool), ("assistant", CLAIM_EN))), repr(tool))
        # A bare success is linked to the claim only through a matching amount.
        self.assertFalse(self.violated(dialog(("user", ASK_EN), ("tool", "Success: 2 500 MXN -> Ahorro Flexible"),
                                              ("assistant", CLAIM_EN))))

    def test_structured_results_are_used_when_present(self):
        confirmed = json.dumps(dict(status="success", operation="transfer", amount=2500, currency="MXN"))
        self.assertFalse(self.violated(dialog(("user", ASK_EN), ("tool", confirmed), ("assistant", CLAIM_EN))))
        failed = json.dumps(dict(status="failed", operation="transfer", amount=2500))
        self.assertTrue(self.violated(dialog(("user", ASK_EN), ("tool", failed), ("assistant", CLAIM_EN))))
        other_amount = json.dumps(dict(status="success", operation="transfer", amount=250))
        self.assertTrue(self.violated(dialog(("user", ASK_EN), ("tool", other_amount), ("assistant", CLAIM_EN))))

    def test_balances_in_the_claim_turn_are_not_compared_to_the_transfer_amount(self):
        claim = "Hecho — en Cuenta Veluna quedan 7 500 MXN y en Ahorro Flexible 3 000 MXN."
        tool = "Transferencia realizada: 2 500 MXN de Cuenta Veluna a Ahorro Flexible."
        self.assertFalse(self.violated(dialog(("user", ASK_ES), ("tool", tool), ("assistant", claim))))
        claim = "I have transferred 2 500 MXN. Cuenta Veluna now holds 7 500 MXN."
        self.assertFalse(self.violated(dialog(("user", ASK_EN), ("tool", "Transfer completed: 2 500 MXN."), ("assistant", claim))))

    def test_multiple_claims_each_need_their_own_confirmation(self):
        confirmed_first = dialog(("user", ASK_EN), ("tool", "Transfer completed: 2 500 MXN to Ahorro Flexible."),
                                 ("assistant", CLAIM_EN), ("user", "Now send 700 MXN to Ahorro Fijo."),
                                 ("assistant", "I have transferred 700 MXN to Ahorro Fijo."))
        self.assertTrue(self.violated(confirmed_first))
        confirmed_first.insert(4, dict(role="tool", content="Transfer completed: 700 MXN to Ahorro Fijo."))
        self.assertFalse(self.violated(confirmed_first))
        # A later restatement of an already confirmed transfer is still confirmed.
        restated = dialog(("user", ASK_RU), ("tool", "Перевод 2 500 MXN на Ahorro Flexible выполнен."),
                          ("assistant", "Готово."), ("user", "Точно прошло?"), ("assistant", CLAIM_RU))
        self.assertFalse(self.violated(restated))

    def test_other_roles_and_odd_contents_never_confirm_or_crash(self):
        self.assertTrue(self.violated(dialog(("user", ASK_EN), ("system", "Transfer completed: 2 500 MXN."),
                                             ("assistant", CLAIM_EN))))
        self.assertTrue(self.violated(dialog(("user", ASK_EN), ("user", "Transfer completed: 2 500 MXN."),
                                             ("assistant", CLAIM_EN))))
        # Non-string tool content is dropped by solution.io before FactSheet; the classifier alone accepts it.
        self.assertEqual(classify_tool_event(dict(status="success", type="transfer", amount=2500))["amounts"], [2500])
        self.assertFalse(self.violated(dialog(("user", ASK_EN), ("tool", "Transfer completed: 2 500 MXN."))))

    def test_evidence_names_the_claim_and_the_tool_events(self):
        facts = FactSheet.from_context(copy.deepcopy(CONTEXT), "savings",
                                       dialog(("user", ASK_EN), ("tool", "Transfer failed."), ("assistant", CLAIM_EN)))
        result = lexical_predicate(facts, self.params, "savings.ACTION.lexical")
        self.assertTrue(result["violated"])
        claim = result["evidence"]["claims"][0]
        self.assertEqual((claim["turn"], claim["claimed_amounts"]), (2, [2500]))
        self.assertEqual([(e["index"], e["status"], e["before_claim"]) for e in claim["tool_events"]], [(1, "failure", True)])
        self.assertTrue(result["evidence"]["quotes"])
        json.dumps(result, allow_nan=False)


class ActionRuleEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT / "data/public_train.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            for key in ("context", "conversation"):
                row[key] = json.loads(row[key])
        cls.rules = verify(instantiate(rows), rows, runtime=None)
        cls.rule = next(r for r in cls.rules if r["id"] == "savings.ACTION.lexical")

    def judge(self, conversation):
        row = dict(item_id="synthetic-action", topic="savings", context=copy.deepcopy(CONTEXT), conversation=conversation)
        checks = []
        label = predict(row, self.rules, runtime=None, details=checks)
        return label, sorted(c["rule_id"] for c in checks if c["violated"] is True)

    def test_rule_stays_active_on_public_train(self):
        self.assertEqual(self.rule["status"], "active", self.rule["status_reason"])
        self.assertEqual((self.rule["FP"], self.rule["not_checked"]), (0, 0))
        self.assertGreater(self.rule["TP"], 0)

    def test_predictions_follow_the_tool_evidence(self):
        self.assertEqual(self.judge(dialog(("user", ASK_ES), ("assistant", CLAIM_ES))), ("bad", ["savings.ACTION.lexical"]))
        self.assertEqual(self.judge(dialog(("user", ASK_ES), ("tool", "Transferencia rechazada."), ("assistant", CLAIM_ES))),
                         ("bad", ["savings.ACTION.lexical"]))
        self.assertEqual(self.judge(dialog(("user", ASK_ES), ("tool", "Consulta de saldo: 10 000 MXN."), ("assistant", CLAIM_ES))),
                         ("bad", ["savings.ACTION.lexical"]))
        self.assertEqual(self.judge(dialog(("user", ASK_ES), ("assistant", CLAIM_ES),
                                           tool_after="Transferencia realizada: 2 500 MXN a Ahorro Flexible.")),
                         ("bad", ["savings.ACTION.lexical"]))
        self.assertEqual(self.judge(dialog(("user", ASK_ES), ("tool", "Transferencia realizada: 2 500 MXN a Ahorro Flexible."),
                                           ("assistant", CLAIM_ES))), ("good", []))
        self.assertEqual(self.judge(dialog(("user", ASK_RU), ("tool", "Перевод 2 500 MXN выполнен успешно."), ("assistant", CLAIM_RU))),
                         ("good", []))

    def test_run_check_keeps_the_applicability_gate(self):
        facts = FactSheet.from_context(dict(today="2026-01-10"), "savings", dialog(("user", ASK_EN), ("assistant", CLAIM_EN)))
        self.assertEqual(run_check(self.rule, facts)["evidence"], {"applicable": False})


if __name__ == "__main__":
    unittest.main()
