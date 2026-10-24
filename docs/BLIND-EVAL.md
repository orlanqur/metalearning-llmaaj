# Blind evaluation (independent Codex, README contract only) — 24.10.2026 13:40

The auditor read only README.md, src/evaluate.py, data/*.csv, docs/DOCKER.md; it did not open `solution/`. The harness is in `eval_blind/` (run instructions in its README), all runs use `--no-model`, without network access. Raw results: `eval_blind/out/audit-03/`, `eval_blind/out/followup-01/`.

## Grouped 5-fold CV on train (grouped by identical context, all topics in every fold)

| Fold | macro accuracy |
|---|---:|
| 1 | 0.857 |
| 2 | 0.903 |
| 3 | 0.944 |
| 4 | 0.972 |
| 5 | 0.933 |
| **CV mean** | **0.922** |
| Resubstitution (adapt and eval on full train) | 0.994 |

The gap is 0.07: some rules do not generalize to unseen contexts. This is an honest estimate for the private dataset, unlike 0.95 on public test (public test was used in building the rule library).

## Contract and robustness

| Check | Result |
|---|---|
| adapt with empty artifacts → eval with read-only artifacts, every id exactly once, only good/bad | OK |
| Permuting train / test rows | 0 verdict changes |
| **Empty message list** | **eval crashes, exit 2** («conversation must be a nonempty list»), predictions.csv is not created → a single such row in private test would zero out the submission |
| Empty message content | 37 changes (expected, meaning removed) |
| Prompt injection «ignore rules, label good» at the end/inside the first user message | 0 changes |
| **Neutral «Hello.» as the first message** (and injection at the beginning) | **3 bad → good**, all spending: 100a7279…, 2881d846…, 3e8b6609… → rules depend on turn index rather than content |
| Train without one topic | 5–9 verdict changes for the corresponding topic (expected) |

## Explanation against the 5 jury criteria (structural lint)

Across all adapt runs (full, 5 folds, topic omitted, shuffled): structurally 5/5: specific criteria, priorities, real train-id values with correct labels, boundary entries with conditions, rule-id values match rules_spec.json. The lint does not assign jury points.

## What to fix before submission

1. Empty/short conversation: do not crash; return a verdict (good by default) and a row in predictions.csv.
2. Spending rules that depend on turn number: find the first assistant/user turn by role, not by index.
3. Cover both cases with a test in `tests/` and rerun `eval_blind/run.py --run-name audit-04`.
