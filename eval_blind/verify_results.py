"""Independent arithmetic and artifact checks of saved audit results (stdlib)."""
import collections
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    primary = ROOT / 'eval_blind/out/audit-03'
    followup = ROOT / 'eval_blind/out/followup-01'
    results = json.loads((primary / 'results.json').read_text())
    train = read_jsonl(primary / 'full_adapt/adapt_input/train.jsonl')
    all_ids = {r['item_id'] for r in train}
    fold_ids = []
    for number in range(1, 6):
        fit = read_jsonl(primary / f'cv_{number}_adapt/adapt_input/train.jsonl')
        hold = read_jsonl(primary / f'cv_{number}/gold.jsonl')
        fit_ids, hold_ids = {r['item_id'] for r in fit}, {r['item_id'] for r in hold}
        assert fit_ids | hold_ids == all_ids and not fit_ids & hold_ids
        key = lambda r: json.dumps(r['context'], sort_keys=True, separators=(',', ':'))
        assert not {key(r) for r in fit} & {key(r) for r in hold}
        assert len(fit) == 120 and len(hold) == 30
        fold_ids.extend(hold_ids)
    assert collections.Counter(fold_ids) == collections.Counter(all_ids)
    checked_scores = []
    for name, result in results.items():
        case = primary / name
        if 'eval' in result:
            test = read_jsonl(case / 'eval_input/test.jsonl')
            assert all(set(r) == {'item_id', 'topic', 'context', 'conversation'} for r in test)
            assert result['readonly_probe']['exit_code'] == 0
            assert result['artifacts_unchanged']
        if 'score' not in result:
            continue
        gold = read_jsonl(case / 'gold.jsonl')
        with (case / 'output/predictions.csv').open(newline='') as f:
            predictions = list(csv.DictReader(f))
        assert len(predictions) == len(gold)
        lookup = {r['item_id']: r['label'] for r in predictions}
        counts = collections.defaultdict(lambda: [0, 0])
        for row in gold:
            counts[row['topic']][0] += lookup[row['item_id']] == row['label']
            counts[row['topic']][1] += 1
        ratios = []
        for topic, (correct, n) in counts.items():
            official = result['score']['by_topic'][topic]
            assert (correct, n) == (official['correct'], official['n'])
            ratios.append(correct / n)
        assert len(ratios) == 4
        assert math.isclose(sum(ratios) / 4, result['score']['macro_topic_accuracy'], abs_tol=1e-12)
        checked_scores.append(name)
    freeze = json.loads((primary / 'blind_freeze.json').read_text())['hashes']
    source_unchanged = {}
    archived_tests = {}
    for name, expected in freeze.items():
        path = ROOT / name
        if name.startswith('eval_blind/'):
            path = primary / 'frozen_tests' / Path(name).name
            archived_tests[name] = hashlib.sha256(path.read_bytes()).hexdigest() == expected
        else:
            source_unchanged[name] = hashlib.sha256(path.read_bytes()).hexdigest() == expected
    assert all(source_unchanged.values()) and all(archived_tests.values())
    follow_results = json.loads((followup / 'results.json').read_text())
    for result in follow_results.values():
        assert result['contract_pass']
    injected = results['injection_prepend']['invariance']['changes']
    neutral = follow_results['neutral_prepend']['invariance']['changes']
    assert injected == neutral
    lint = json.loads((followup / 'explanation/full_adapt.json').read_text())
    means = statistics.mean(results[f'cv_{i}']['score']['score'] for i in range(1, 6))
    data = {'verified': True, 'cv_folds': 5, 'oof_ids_exactly_once': len(fold_ids), 'context_leaks': 0,
        'scorer_reports_independently_recomputed': checked_scores,
        'cv_mean': means, 'resubstitution': results['resubstitution']['score']['score'],
        'resubstitution_minus_cv_percentage_points': 100 * (results['resubstitution']['score']['score'] - means),
        'per_topic_cv_mean': {topic: statistics.mean(results[f'cv_{i}']['score']['by_topic'][topic]['accuracy'] for i in range(1, 6))
                              for topic in results['cv_1']['score']['by_topic']},
        'contract_successes': sum(r.get('contract_pass') is True for r in results.values()),
        'contract_failures': [n for n, r in results.items() if r.get('contract_pass') is False],
        'adapt_successes': sum(r.get('adapt', {}).get('exit_code') == 0 for r in results.values()),
        'source_inputs_unchanged': source_unchanged, 'archived_frozen_test_hashes_match': archived_tests,
        'prefix_injection_and_neutral_changes_identical': True,
        'explanation_train_ids': len(lint['criteria']['links_to_training_examples']['references']),
        'explanation_spec_rule_ids': len(lint['criteria']['consistency_with_implementation']['spec_rule_ids']),
        'explanation_unmatched_rule_ids': lint['criteria']['consistency_with_implementation']['unmatched_rule_like_ids']}
    (followup / 'verification.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
