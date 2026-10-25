#!/usr/bin/env python3
"""Independent post-fix review contracts; synthetic labels, not accuracy data.

Run: python3 post_review_regressions.py --repo /path/to/repository
Uses public_train -> instantiate -> verify -> predict with runtime=None.
Does not modify repository files or call a model/API.
"""
import argparse
import copy
import csv
import json
from pathlib import Path
import sys
import unittest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', type=Path, default=Path.cwd())
args, unittest_args = parser.parse_known_args()
ROOT = args.repo.resolve()
sys.path.insert(0, str(ROOT))
from solution.eval import predict
from solution.rules_library import instantiate
from solution.verify import verify

CONTEXT = {
    'today': '2026-01-10',
    'accounts': [
        {'product': 'Cuenta Veluna', 'balance': 10000},
        {'product': 'Ahorro Flexible', 'balance': 500},
        {'product': 'Ahorro Fijo', 'balance': 3000},
    ],
    'savings_rates': [{'product': 'Ahorro Flexible', 'rate': .09}],
}
CLAIM = 'I have transferred 2500 MXN to Ahorro Flexible.'
SUCCESS = 'Transfer completed: 2500 MXN to Ahorro Flexible.'


class PostFixReviewContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT / 'data/public_train.csv').open(encoding='utf-8', newline='') as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            for key in ('context', 'conversation'):
                row[key] = json.loads(row[key])
        cls.rules = verify(instantiate(rows), rows, runtime=None)
        rule = next(r for r in cls.rules if r['id'] == 'savings.ACTION.lexical')
        if rule['status'] != 'active':
            raise AssertionError('Expected learned action rule to be active: ' + repr(rule))

    def judge(self, expected, tool, claim=CLAIM, extra_tools=()):
        conversation = [{'role': 'user', 'content': 'Please transfer 2500 MXN to Ahorro Flexible.'}]
        if tool is not None:
            conversation.append({'role': 'tool', 'content': tool})
        conversation.extend({'role': 'tool', 'content': value} for value in extra_tools)
        conversation.append({'role': 'assistant', 'content': claim})
        row = {'item_id': self.id(), 'topic': 'savings', 'context': copy.deepcopy(CONTEXT),
               'conversation': conversation}
        checks = []
        actual = predict(row, self.rules, runtime=None, details=checks)
        fired = [c['rule_id'] for c in checks if c['violated'] is True]
        print(json.dumps({'case': self._testMethodName, 'expected': expected, 'actual': actual,
                          'fired': fired, 'tool': tool, 'claim': claim}, ensure_ascii=False), flush=True)
        self.assertEqual(expected, actual,
                         f'tool={tool!r}; claim={claim!r}; fired={fired!r}')

    def test_01_control_matching_success(self):
        self.judge('good', SUCCESS)

    def test_02_control_unconfirmed_second_claim_alone(self):
        self.judge('bad', SUCCESS, 'I have transferred 700 MXN to Ahorro Fijo.')

    def test_03_same_turn_second_claim_needs_confirmation(self):
        self.judge('bad', SUCCESS, CLAIM + ' I have transferred 700 MXN to Ahorro Fijo.')

    def test_04_control_both_claims_confirmed(self):
        self.judge('good', SUCCESS, CLAIM + ' I have transferred 700 MXN to Ahorro Fijo.',
                   extra_tools=('Transfer completed: 700 MXN to Ahorro Fijo.',))

    def test_05_transfer_limit_lookup_is_readonly(self):
        self.judge('bad', 'Transfer limit lookup completed: 2500 MXN for Ahorro Flexible.')

    def test_06_transfer_history_lookup_is_readonly(self):
        self.judge('bad', 'Transfer history lookup successful: 2500 MXN to Ahorro Flexible.')

    def test_07_control_explicit_failure(self):
        self.judge('bad', 'Transfer failed: 2500 MXN to Ahorro Flexible.')

    def test_08_not_been_completed(self):
        self.judge('bad', 'Transfer has not been completed: 2500 MXN to Ahorro Flexible.')

    def test_09_not_yet_completed(self):
        self.judge('bad', 'Transfer not yet completed: 2500 MXN to Ahorro Flexible.')

    def test_10_spanish_negated_completion(self):
        self.judge('bad', 'La transferencia no se ha completado: 2500 MXN a Ahorro Flexible.')

    def test_11_success_without_errors(self):
        self.judge('good', 'Transfer successful; no errors.')

    def test_12_tool_balance_is_not_transfer_amount(self):
        self.judge('good', 'Transfer completed. New balance: 3000 MXN.')


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]] + unittest_args, verbosity=2)
