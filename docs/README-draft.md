# A Judge That Learns from an Expert

## What is this, and who is it for?

This is a two-stage learned judge for the Plata track. It infers topic-specific
evaluation rules from expert-labeled conversations, saves those rules as
auditable artifacts, and applies them to unseen conversations. It is for teams
that need a reproducible `good`/`bad` classifier whose decisions can be traced
back to the expert's own examples.

## How do I run it?

### Docker

```sh
docker build -t plata-judge .

docker run --rm \
  -v "$PWD/out/public_input:/input:ro" \
  -v "$PWD/out/public_artifacts:/artifacts" \
  plata-judge adapt

docker run --rm \
  -v "$PWD/out/public_input:/input:ro" \
  -v "$PWD/out/public_artifacts:/artifacts:ro" \
  -v "$PWD/out/public_output:/output" \
  plata-judge eval
```

Create the host directories and inputs first; see [the complete Docker guide](DOCKER.md).
`eval` intentionally runs in a separate container.

### Without Docker

```sh
python3 src/prepare_inputs.py \
  --train data/public_train.csv \
  --test data/public_test.csv \
  --out-dir out/public_input

python3 -m solution adapt \
  --input out/public_input/train.jsonl \
  --artifacts out/public_artifacts

python3 -m solution eval \
  --input out/public_input/test.jsonl \
  --artifacts out/public_artifacts \
  --output out/public_output/predictions.csv
```

Python 3.10 or newer is required. The deterministic path has no third-party
dependencies and needs no API key.

## What expertise is encoded?

The system does not start from one universal notion of a “good” answer. During
`adapt`, it tests parameterized rule families against the supplied labels and
keeps only rules supported by the expert's data. Rules are scoped by topic;
one applicable violation makes the conversation `bad`. Conflicting or
unsupported candidates are retained as boundaries instead of being silently
promoted to rules.

The generated [`explanation.md`](../artifacts/explanation.md) links active
criteria to labeled training examples, shows counterexamples and boundaries,
and states the priority order used by `eval`. That file is generated anew from
the submitted training set; the repository link is only available after a local
adaptation run.

## Which model does it use, and under what license?

- Default planned open-weight model: `openai/gpt-oss-120b`, Apache-2.0.
- Alternative: Gemma 4 31B — `<fill exact endpoint/model ID>`;
  license: `<confirm and link the exact model license used>`.
- Actual induction model for the submitted run: `<fill from run_meta.json>`.
- Actual evaluation model for the submitted run: `<fill from run_meta.json>`.

Select endpoints with `INDUCTION_MODEL` and `EVAL_MODEL`; configure OpenRouter
with `OPENROUTER_API_KEY` and `OPENROUTER_BASE_URL`. With no key, the solution
runs deterministically and records that no model calls were made.

## Does the product improve the same base model?

This comparison must use the same model, prompts held constant except for the
learned artifacts, and the same evaluation split. Fill the table from a recorded
run before submission:

| Topic | Same model, zero-shot | Same model + `adapt` | Delta |
|---|---:|---:|---:|
| `credit` | `<run>` | `<run>` | `<calc>` |
| `financial_position` | `<run>` | `<run>` | `<calc>` |
| `savings` | `<run>` | `<run>` | `<calc>` |
| `spending` | `<run>` | `<run>` | `<calc>` |
| **Macro topic accuracy** | **`<run>`** | **`<run>`** | **`<calc>`** |

Deterministic public regression: **0.950 macro topic accuracy, 76/80 correct**.
This is a local public-test result, not an independent claim of transfer to the
private set; the deterministic rule work was informed by the public data.

## Where does it not work?

- A rule absent from the adaptation labels cannot be reliably recovered by the
  deterministic fallback.
- Semantic or stylistic requirements may need the configured open-weight model;
  without it, those checks remain unverified rather than guessed.
- Sparse, contradictory, or topic-shifted labels can leave candidates in the
  boundary set.
- The public regression does not estimate private-set performance.

## What are the steps to first value?

1. Convert the provided CSV files to `train.jsonl` and `test.jsonl`.
2. Run `adapt` once and inspect `/artifacts/explanation.md`.
3. Run `eval` in a separate container using the same read-only artifacts.
4. Validate `/output/predictions.csv` with the organizer's scorer.

That produces a complete prediction file and an explanation tied to the same
rules used for prediction.
