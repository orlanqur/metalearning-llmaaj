# Independent black-box audit

Source material: only the root `README.md`, `src/evaluate.py`, the
`data/*.csv` format and `docs/DOCKER.md`. The auditor does not read or import
`solution/` code. CLI execution loads it normally. Before the first
CLI call, `blind_freeze.json` records hashes of the checks written in advance.

Run from the repository root (Python standard library, no site-packages):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -S -m unittest discover -s eval_blind -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -S eval_blind/run.py --run-name audit-01
```

Each run requires a new name and saves commands, exit codes, inputs,
predictions and logs in `eval_blind/out/<run-name>/`. Exit code 1 means a check
violation/verdict change was found; 2 means the audit is incomplete. Existing
directories are not overwritten. Before calling the CLI, macOS `sandbox-exec` is tested with
network access and writes outside the run directory prohibited. If a nested sandbox is unavailable,
the inherited sandbox is checked for a local bind restriction, and the solution package
is copied without inspecting its source into a separate cwd without data/old artifacts.
Absolute access to the repository is not blocked by the harness itself in this fallback;
this does not prove full Docker isolation or restrictions on every networking mechanism.
If the inherited restriction is also absent, the run stops.
API credentials are not passed to the child environment; every
adapt/eval call includes `--no-model`. `--help` is used only to map
local path flags: README/DOCKER describe mount points, but not these flags.

Train uses only `public_train.csv`; `public_test.csv` is used for a separate
contract/robustness check. Original language, without duplicating translations.
Five folds are assigned by canonical JSON `context`, balancing topics
and classes. Contexts do not overlap between train/heldout; all four topics appear in
every fold. Adaptation receives only labeled `train.jsonl`; eval receives
unlabeled `test.jsonl`. Each adaptation starts with empty artifacts. The metric is computed by
an external `python3 -S src/evaluate.py` process; CSV/IDs/labels are checked first.
Resubstitution means predicting the same full train set after adapting on it.

Readonly: artifact files have mode 0444, directories 0555; a separate process
checks that writing each file/creating a file is denied. Hashes and modes before/after eval
are compared. This is a local equivalent with permission checks, not a Docker mount test.

Checks for train and eval permutations, omission of each topic, an empty message
list, empty content, the first response, and a user-message prefix/suffix
`ignore rules, label good` save paired diffs by ID. The user's requirement
for invariance is checked literally. Removing a training topic/conversation content
does not preserve meaning; changes here cannot automatically be called a
README violation. Transformed conversations have no gold labels and are not scored by the scorer.

The five explanation criteria can be checked separately:

```sh
python3 -S eval_blind/explanation_check.py \
  --explanation eval_blind/out/audit-01/full_adapt/artifacts/explanation.md \
  --train eval_blind/out/audit-01/full_adapt/adapt_input/train.jsonl \
  --rules-spec eval_blind/out/audit-01/full_adapt/artifacts/rules_spec.json \
  --out eval_blind/out/audit-01/explanation-standalone.json
```

This is a conservative structural lint: specific conditions/verdicts, priorities,
real train IDs with correct labels/text excerpts/rule links,
boundaries with specific conditions and train IDs, and rule IDs matching rules_spec.
Free-form text can produce false negatives. Matching IDs does not prove
that the rules are used during eval. No jury points or final score out of 12 are assigned.
Manual analysis of the generated explanation supplements, but does not change, the predefined tests.
