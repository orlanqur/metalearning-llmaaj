"""Offline behavioral regression tests for the submitted Plata judge.

Run: python post_hackathon_regressions.py --repo /path/to/review
Default checkout: current directory when it contains ``solution``; otherwise
the script directory, then its sibling ``review`` directory.

Uses the actual public training CSV, instantiate(), verify(), and predict().
No API clients, adaptation artifacts, or repository mutations are required.
Assertions specify intended behavior: the known defects deliberately FAIL on
commit 56a79fa33dcacf4fc9485b97a4635c28dcb3ba12. Synthetic cases are regression
oracles for documented rule semantics, not organizer-labeled accuracy evidence.
"""

import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
parser = argparse.ArgumentParser(description=__doc__)
_script_dir = Path(__file__).resolve().parent
_default_repo = next((p for p in (Path.cwd(), _script_dir, _script_dir / 'review')
                      if (p / 'solution' / 'eval.py').is_file()), _script_dir / 'review')
parser.add_argument('--repo', type=Path, default=_default_repo)
options, remaining = parser.parse_known_args()
REPO = options.repo.resolve()
sys.path.insert(0, str(REPO))

from solution.eval import predict
from solution.rules_library import instantiate
from solution.verify import verify


class ExpertDecisionRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (REPO / 'data/public_train.csv').open(encoding='utf-8', newline='') as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            for key in ('context', 'conversation'):
                row[key] = json.loads(row[key])
        cls.rules = verify(instantiate(rows), rows, runtime=None)
        active = {rule['id'] for rule in cls.rules if rule['status'] == 'active'}
        required = {'savings.RATE.selected_tariff', 'savings.RATE.ahorro_flexible',
                    'savings.AMOUNT.balance_cuenta_veluna', 'savings.ACTION.lexical'}
        if not required <= active:
            raise AssertionError(f'Reproduction prerequisites missing: {sorted(required - active)}')
        cls.context = {
            'accounts': [{'product': 'Cuenta Veluna', 'balance': 1000}],
            'savings_rates': [{'product': 'Ahorro Flexible', 'rate': 0.10}],
        }

    def judge(self, expected, assistant=None, *, conversation=None, context=None):
        if conversation is None:
            conversation = [
                {'role': 'user', 'content': 'What is my balance and savings rate?'},
                {'role': 'assistant', 'content': assistant},
            ]
        row = {'item_id': self.id(), 'topic': 'savings',
               'context': copy.deepcopy(context or self.context), 'conversation': conversation}
        checks = []
        actual = predict(row, self.rules, runtime=None, details=checks)
        fired = [check['rule_id'] for check in checks if check['violated'] is True]
        self.assertEqual(expected, actual,
                         f'Expected {expected}, got {actual}; fired={fired}; conversation={conversation!r}')

    def test_rate_correct_control(self):
        self.judge('good', 'Ahorro Flexible pays 10% annually.')

    def test_rate_wrong_control(self):
        self.judge('bad', 'Ahorro Flexible pays 20% annually.')

    def test_rate_allocation_in_same_turn(self):
        self.judge('good', 'Ahorro Flexible pays 10% annually. You could save 20% of your income.')

    def test_rate_allocation_in_later_turn(self):
        self.judge('good', conversation=[
            {'role': 'user', 'content': 'What is the savings rate?'},
            {'role': 'assistant', 'content': 'Ahorro Flexible pays 10% annually.'},
            {'role': 'user', 'content': 'What percentage of income could I set aside?'},
            {'role': 'assistant', 'content': 'You could save 20% of your income.'},
        ])

    def test_balance_correct_control(self):
        self.judge('good', 'Сейчас на вашем счете Cuenta Veluna 1000 MXN.')

    def test_balance_wrong_control(self):
        self.judge('bad', 'Сейчас на вашем счете Cuenta Veluna 1500 MXN.')

    def test_balance_hypothetical_transfer_same_turn(self):
        self.judge('good', 'Сейчас на вашем счете Cuenta Veluna 1000 MXN. '
                   'Например, вы можете перевести 100 MXN на накопительный счет.')

    def test_balance_second_correct_account_same_turn(self):
        context = copy.deepcopy(self.context)
        context['accounts'].append({'product': 'Ahorro Flexible', 'balance': 2000})
        self.judge('good', 'Сейчас на вашем счете Cuenta Veluna 1000 MXN. '
                   'На Ahorro Flexible у вас 2000 MXN.', context=context)

    @staticmethod
    def action_conversation(tool=None, tool_after=False):
        messages = [{'role': 'user', 'content': 'Transfer 100 MXN to Ahorro Flexible.'}]
        event = {'role': 'tool', 'content': tool} if tool is not None else None
        if event and not tool_after:
            messages.append(event)
        messages.append({'role': 'assistant', 'content': 'I have transferred 100 MXN.'})
        if event and tool_after:
            messages.append(event)
        return messages

    def test_action_unconfirmed_control(self):
        self.judge('bad', conversation=self.action_conversation())

    def test_action_successful_confirmation_control(self):
        self.judge('good', conversation=self.action_conversation(
            'Transfer successful: 100 MXN transferred from Cuenta Veluna to Ahorro Flexible.'))

    def test_action_failed_tool_is_not_confirmation(self):
        self.judge('bad', conversation=self.action_conversation('Transfer failed: rejected.'))

    def test_action_balance_lookup_is_not_confirmation(self):
        self.judge('bad', conversation=self.action_conversation('Balance lookup successful: 1000 MXN.'))

    def test_action_later_success_does_not_confirm_earlier_claim(self):
        self.judge('bad', conversation=self.action_conversation(
            'Transfer successful: 100 MXN transferred from Cuenta Veluna to Ahorro Flexible.', tool_after=True))


if __name__ == '__main__':
    print(f'Repository: {REPO}', flush=True)
    for relative in ('solution/checkers.py', 'solution/facts.py', 'solution/rules_library.py',
                     'solution/verify.py', 'solution/eval.py', 'data/public_train.csv'):
        digest = hashlib.sha256((REPO / relative).read_bytes()).hexdigest()
        print(f'SHA256 {relative}: {digest}', flush=True)
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
