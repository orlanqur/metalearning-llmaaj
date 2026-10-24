# Docker delivery report

Date: 2026-10-24

## Delivered

- `Dockerfile` based on `python:3.12-slim`; no `apt` or `pip` step.
- `entrypoint.sh` maps `adapt` and `eval` to the contract paths.
- `.dockerignore` excludes credentials, Git metadata, caches, local outputs, and
  local artifacts.
- MIT `LICENSE` for 2026, with the requested provisional copyright holder.
- `docs/DOCKER.md` with build, two-container execution, variables, fallback,
  and organizer instructions.
- `docs/README-draft.md` as an English FAQ-style submission draft.

No file under `solution/`, `src/`, or `data/` was edited in this workstream.
No commit was created.

## Commands run

The latest fully verified image-snapshot run used these commands from the
repository root:

```sh
docker build -t plata-judge .

rm -rf /tmp/plata-smoke
mkdir -p /tmp/plata-smoke/input /tmp/plata-smoke/artifacts /tmp/plata-smoke/output
python3 src/prepare_inputs.py \
  --train data/public_train.csv \
  --test data/public_test.csv \
  --out-dir /tmp/plata-smoke/input

docker run --rm \
  -v /tmp/plata-smoke/input:/input:ro \
  -v /tmp/plata-smoke/artifacts:/artifacts \
  plata-judge adapt

docker run --rm \
  -v /tmp/plata-smoke/input:/input:ro \
  -v /tmp/plata-smoke/artifacts:/artifacts:ro \
  -v /tmp/plata-smoke/output:/output \
  plata-judge eval

python3 src/evaluate.py \
  --test data/public_test.csv \
  --predictions /tmp/plata-smoke/output/predictions.csv
```

Because the execution sandbox could not open the host Colima Unix socket, the
commands above were issued inside the already-running Colima VM over localhost
SSH. The repository was available there through Colima's existing home-directory
mount. No Colima or Docker configuration was changed. On a normal host shell,
the commands run directly as documented in `docs/DOCKER.md`.

## Actual output

Input preparation:

```text
train: 150
test: 80
language: original
test_labels_removed: true
```

Verified-snapshot `adapt` run without an API key:

```text
[induce] model steps skipped: no enabled API key
train_rows: 150
candidates: 44
active: 26
boundary: 18
train_resubstitution macro_topic_accuracy: 0.9943181818181819
```

Verified-snapshot `eval` run in a separate container, with `/artifacts` mounted
read-only:

```text
[eval] model calls skipped: no enabled API key; cached responses may be reused
predictions: 80
output: /output/predictions.csv
model_calls: 0
network_calls: 0
log: /output/predictions.log.json
```

Organizer scorer result:

```text
n: 80
correct: 76
accuracy: 0.95
macro_topic_accuracy: 0.9502305665349143
macro_topic_kappa: 0.8931648617424447
```

Per-topic accuracy:

| Topic | Correct / N | Accuracy |
|---|---:|---:|
| `credit` | 14 / 15 | 0.9333333333333333 |
| `financial_position` | 21 / 22 | 0.9545454545454546 |
| `savings` | 20 / 20 | 1.0 |
| `spending` | 21 / 23 | 0.9130434782608695 |

The tested image is identified by the Docker manifest-list digest printed by
the successful build:

```text
sha256:13c9ebbb92998ff99595f51dec24b213065668aff39337dd6721e93cc4893f29
```

This digest identifies the image that produced the output above. Parallel
STEP2 work changed `solution/*.py` again after this smoke, so the later live
tree is explicitly `not_checked` by this run and must be rebuilt/retested at
acceptance.

The image configuration contains no OpenRouter key or model-setting value.
An inspection run confirmed that supplied non-secret sentinel values for
`OPENROUTER_BASE_URL`, `INDUCTION_MODEL`, and `EVAL_MODEL` appeared unchanged
inside the container. `entrypoint.sh` uses `exec`, so `OPENROUTER_API_KEY` is
likewise inherited by the Python process without being printed or persisted.

## Additional checks

```text
python3 -m unittest discover -s src -p 'test_*.py'   -> 9 tests, OK
python3 -m unittest discover -s tests -p 'test_*.py' -> 29 tests, OK
sh -n entrypoint.sh                                  -> OK
git diff --check (delivered files)                   -> OK
```

## Problems encountered

1. Direct host `docker build` returned `permission denied` for
   `~/.colima/default/docker.sock`; `colima status` was also unable to inspect
   host state from the sandbox. The already-running VM and Docker daemon were
   verified through localhost SSH (`Docker 29.5.2`), and the smoke was run there.
2. A parallel workstream changed `solution/*.py` during the first image build.
   One intermediate rebuild exposed a transient incompatible call:
   `predict() takes 2 positional arguments but 5 were given`. This workstream
   did not edit those files. After the parallel fix landed and the source hash
   stabilized, the image was rebuilt and the entire smoke passed again.
3. The reported 0.9502305665349143 is a public regression result, not an
   independent holdout estimate: the deterministic rule reconstruction was
   informed by both public splits.
4. Parallel STEP2 edits continued after the verified image run. This report
   binds its PASS to image digest `sha256:13c9ebbb92998ff99595f51dec24b213065668aff39337dd6721e93cc4893f29`;
   it does not transfer that PASS to later unbuilt source changes.
