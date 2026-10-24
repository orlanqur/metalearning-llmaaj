# Docker runner

The image exposes the organizer contract directly: `adapt` reads
`/input/train.jsonl` and writes `/artifacts`; `eval` runs in a new container,
reads `/input/test.jsonl` plus the persisted artifacts, and writes
`/output/predictions.csv`.

## Build

From the repository root:

```sh
docker build -t plata-judge .
```

The current image uses only the Python 3.12 standard library, so the build does
not download Python packages. `.env`, local outputs, artifacts, and Git metadata
are excluded from the build context. No credential is baked into the image.

## Prepare the public input

```sh
rm -rf /tmp/plata-smoke
mkdir -p /tmp/plata-smoke/input /tmp/plata-smoke/artifacts /tmp/plata-smoke/output
python3 src/prepare_inputs.py \
  --train data/public_train.csv \
  --test data/public_test.csv \
  --out-dir /tmp/plata-smoke/input
```

## Run adaptation

```sh
docker run --rm \
  -v /tmp/plata-smoke/input:/input:ro \
  -v /tmp/plata-smoke/artifacts:/artifacts \
  plata-judge adapt
```

## Run evaluation in a separate container

```sh
docker run --rm \
  -v /tmp/plata-smoke/input:/input:ro \
  -v /tmp/plata-smoke/artifacts:/artifacts:ro \
  -v /tmp/plata-smoke/output:/output \
  plata-judge eval
```

Optionally score the public predictions on the host:

```sh
python3 src/evaluate.py \
  --test data/public_test.csv \
  --predictions /tmp/plata-smoke/output/predictions.csv
```

## Optional model configuration

The container does not set or rewrite model configuration. Supply values at run
time only when a model-backed path is enabled:

```sh
docker run --rm \
  --env OPENROUTER_API_KEY \
  --env OPENROUTER_BASE_URL \
  --env INDUCTION_MODEL \
  --env EVAL_MODEL \
  -v /tmp/plata-smoke/input:/input:ro \
  -v /tmp/plata-smoke/artifacts:/artifacts \
  plata-judge adapt
```

`OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `INDUCTION_MODEL`, and
`EVAL_MODEL` reach the Python process unchanged. Do not place secrets in the
repository or image. Without an API key, the solution follows its deterministic
path and still emits complete artifacts and one prediction per test ID.

## Organizer execution

Organizers can build the submitted commit, mount their labeled private
`train.jsonl` into `/input`, and run `adapt` with a fresh writable artifacts
directory. They then start a separate `eval` container with that directory
mounted read-only, their unlabeled private `test.jsonl` at `/input/test.jsonl`,
and a writable `/output`. The only scored prediction file is
`/output/predictions.csv`.
