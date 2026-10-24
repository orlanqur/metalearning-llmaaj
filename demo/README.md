# Judge demo

Python 3.10+, stdlib only. Run from the repository root; no package installation or API key is required.
The CLI imports `solution.eval.predict` and `SemanticRuntime.fewshot`; it does not modify the solution code or artifacts.
By default, it reads `artifacts/step2` relative to the repository root. An explicit `--artifacts` is resolved relative to the current directory.

## Preparing artifacts

Requires `rules_spec.json` and `fewshot_index.json` from the same adapt run, optionally `cache/`.
Artifacts are ignored by Git. If step2 is missing, prepare it on public train:

```sh
python3 -S src/prepare_inputs.py --train data/public_train.csv --test data/public_test.csv --out-dir out/demo_input
python3 -S -m solution adapt --input out/demo_input/train.jsonl --artifacts artifacts/step2 --no-model
```

The demo always runs as `eval --no-model`: HTTP is disabled even if a key is present, but the saved semantic cache may be used.
The cache model is selected using the standard `EVAL_MODEL`/`INDUCTION_MODEL` settings from the environment or the root `.env`.
For unknown checks, the fallback from the manifest is displayed. A `good` verdict may have no triggered rule;
`bad` may also be the majority label when checks are unknown — the CLI does not invent a violation.

## Three run commands

1. Public test example:

```sh
python3 -S demo/judge_demo.py --id 100a727946a7a45a72c46771e608090f
```

2. Train example with an explicit artifacts directory:

```sh
python3 -S demo/judge_demo.py --id 788b8ddedccb1543d09913a7eb1eea12 --artifacts artifacts/step2
```

3. Your own conversation and context:

```sh
python3 -S demo/judge_demo.py --dialog-file /tmp/plata-dialog.json --context-file /tmp/plata-context.json --topic financial_position
```

For the third command, save the following in `/tmp/plata-dialog.json`:

```json
[{"role":"user","content":"How much money?"},{"role":"assistant","content":"You have 100 MXN."}]
```

And in `/tmp/plata-context.json`:

```json
{"today":"2026-01-10","accounts":[{"product":"Cash","balance":100,"current_debt":20}]}
```

Instead of `--topic`, you can pass context as `{"topic":"financial_position","context":{...}}`
or the conversation as `{"topic":"financial_position","conversation":[...]}`. The API requires a topic to select rules;
conflicting values are rejected. Valid values are `credit`, `financial_position`, `savings`, `spending`.
An unknown ID, missing file/topic, or invalid JSON causes the CLI to exit with code 2.

## Actual output

Below is the complete stdout of the first command using locally rebuilt step2 artifacts (public train, `--no-model`).
The quote comes from the conversation being evaluated, the condition from the manifest, and the calculated amounts from the evidence checker.
Similar examples come from `fewshot_index.json`; labels apply to the entire conversation.
Text similarity does not prove the same violation; retrieval excludes the query ID and identical conversations.
If another index contains fewer than two suitable examples, the CLI reports the actual count.

```text
Example: 100a727946a7a45a72c46771e608090f (public_test.csv; topic=spending)
Mode: offline; saved semantic cache allowed; no network calls
Verdict: bad
Rule: spending.TX_AMOUNT.merchant (priority=10)
Condition: Recalculate completed merchant transactions before confirming a proposed amount.
Decision: first violated active rule in (priority, id) order; later rules not evaluated.
Evidence: Confirmed merchant amount disagrees with completed transactions
Assistant quote (turn 1):
> Sí, tienes razón: en agosto de 2026 gastaste 526 MXN en Uber.
Checker details (may include context-derived values): {"merchant": "uber", "month": "2026-08", "expected": 426, "observed": 526.0}

Similar train examples (TF-IDF dialog; same topic; self/identical dialog excluded):
- 33b3d072865a9ae4dc780e3048c823f6 | label=bad
  assistant excerpt (first 220 characters):
> He revisado tus datos: las compras en septiembre de 2026 fueron 17,480 MXN. Además hubo 1,200 MXN en transferencias a otros y 2,500 MXN en movimientos entre tus propias cuentas.
- 4d009bf5057d52d86af17be43908d677 | label=bad
  assistant excerpt (first 220 characters):
> En ropa (Zara, H&M y Pull&Bear) gastaste **6,020 MXN** en los últimos tres meses completos, julio, agosto y septiembre, unos **2,007 MXN al mes**.
- f922db12640a7720effc405b2062f70c | label=bad
  assistant excerpt (first 220 characters):
> Promedio mensual (junio–agosto): 21,933 MXN. Desglose promedio: Compras 16,033 MXN; Transferencias a otras personas 1,733 MXN; Transferencias entre mis cuentas 4,167 MXN. Reembolsos promedio: 0 MXN.
Similarity does not imply the same violation; labels belong to whole train conversations.
```

## Verification

`python3 -S -m unittest discover -s tests -p test_demo.py -v`

One integration test creates temporary train-only artifacts, checks good/bad, the rule and quotes against `predict`,
neighbor labels against the source train data, both input modes, input errors, an unknown semantic check, and the absence of writes to artifacts.
