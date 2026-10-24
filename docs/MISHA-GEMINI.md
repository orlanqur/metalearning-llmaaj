# Mikhail stopped here

24.10.2026, 14:25 CEST. Branch `orlanqur/plata-clean-work`.

I completed one public run with Gemini and recorded the numbers. I did not write the fork README: the root still contains the organizers' contract. I did not take on the pitch; it had already been assembled in `TEAM/PITCH.md`. I did not handle the OrganizerHQ submission, SHA, or checklist.

The provider-selection code is already in commit `c7173a8`. This file changes nothing in `solution/`. The key from `.env` and the `out/` directory are not tracked in git: both are in `.gitignore`.

## What exactly changed in the code

`solution/llm.py` selects the provider as follows. If no key is passed to the constructor, `GEMINI_API_KEY` is set, and `OPENROUTER_API_KEY` is empty, the client uses `https://generativelanguage.googleapis.com/v1beta/openai/`. The model comes from `INDUCTION_MODEL`, otherwise from `GEMINI_MODEL`, otherwise `gemini-4-argon`. `EVAL_MODEL`, if set, overrides it during evaluation.

If an OpenRouter key is present, the previous path remains, even when a Gemini key is also in the environment. An explicit key passed to the constructor by a test does not switch providers either. This commit therefore does not redirect Arkady's run through OpenRouter.

A short live request to `gemini-4-argon` succeeded on the first attempt and returned JSON with the `verdict` / `quote` / `reason` schema.

## How the run works

The official local sequence is:

```
python3 src/prepare_inputs.py --train data/public_train.csv --test data/public_test.csv --out-dir out/in
python3 -m solution adapt --input out/in/train.jsonl --artifacts out/art-gemini
python3 -m solution eval --input out/in/test.jsonl --artifacts out/art-gemini --output out/pred-gemini.csv
python3 src/evaluate.py --test data/public_test.csv --predictions out/pred-gemini.csv
```

`adapt` sees only the 150 labeled training conversations. Public test labels are not passed to it.

First, the library builds rule templates from the train schema. Then each rule is run against every conversation in its topic. A rule becomes `active` only if it has at least one correctly detected violation, zero false positives, and no unchecked rows. Otherwise it remains `boundary` and does not contribute on the test set.

A semantic template asks the model for yes, no, or unknown, plus a verbatim quote from an assistant response. A quote absent from the text makes the result unknown. Unknown does not count as a violation. A single such answer anywhere in train moves the entire rule to `boundary`.

After the templates, `induce` examines conversations that the active rules explained incorrectly and asks the model to propose a new rule. The new rule undergoes the same check on the full train set.

`eval` reads the saved `rules_spec.json`. It goes through active rules in priority order. The first confirmed violation yields `bad`. Boundary rules do not vote. `src/evaluate.py` compares `predictions.csv` with public labels and writes `macro_topic_accuracy`.

This has a practical consequence. Artifacts built without a key cannot be “evaluated further” using that key. In that run, all 8 semantic rules remained `boundary` with reason `not_checked`, there were 0 model calls on test, and the score remained 0.9502. For the model to participate at all, `adapt` must be rerun. I did exactly that, in a separate directory, `out/art-gemini`, not in `out/art` or `out/step3`.

## Why the run produced a score

`gemini-4-argon` returned structured JSON. Over 35 minutes, `adapt` made 302 successful calls and 304 network calls; two requests failed and were retried, and the circuit breaker did not open afterward. `model_status` in the manifest: `enabled`.

Of the eight semantic templates, six became active, all with precision 1:

- `credit.MIN_INTEREST.semantic`, 4 correctly detected violations
- `credit.NONANSWER.semantic`, 7
- `financial_position.NONANSWER.semantic`, 6
- `savings.ACTION.semantic`, 1
- `savings.FIXED_LOCK.semantic`, 4
- `spending.DENIAL.semantic`, 3

Two “the assistant did not answer the question” templates remained boundary rules due to false `bad` verdicts: `savings.NONANSWER.semantic` (1 true positive and 1 false positive) and `spending.NONANSWER.semantic` (6 true positives and 2 false positives).

One training conversation remained in the residuals, `5f9ae3d8d52eaf3dade5beee0fce7f0e`, topic spending. The model proposed a rule about the average over three full months, `spending.induced.563a7b934d0064b5`. Verification accepted it: 7 true positives, 0 false positives. The second proposed rule, about subtracting refunds, was not activated: the model could not check two training rows.

Relabeling the same 150 training conversations then yielded macro 1.0, with 0 errors. This is not a test. The model saw these labels while the rules were being selected.

Next, `eval` on 80 public conversations made 77 calls, all successful. There were no spurious interruptions.

## Public test results

Official `src/evaluate.py`:

| | no model | Gemini, this run |
|---|---:|---:|
| macro_topic_accuracy | 0.9502 | 0.9507 |
| correct | 76/80 | 76/80 |
| good/bad matrix | 50 correct good, 0 false bad, 4 misses, 26 correct bad | 49, 1, 3, 27 |

By topic with the model: credit 14/15, financial_position 22/22, savings 20/20, spending 20/23.

Without the model, financial_position was 21/22 and spending 21/23. The model caught a missed violation in financial position and added one false “bad” in spending. The number of correct answers therefore stayed the same; macro increased by 0.0005 because topics are averaged separately.

The five rows where at least one of the two runs disagreed with the label:

| item_id | topic | label | Gemini | no model |
|---|---|---|---|---|
| `9273f1d3f88303616b4e658ef581c389` | financial_position | bad | bad | good |
| `f97db6875c365928b32f79930721b834` | spending | good | bad | good |
| `15b42e3513d7c700cc9ae71435bf4f29` | spending | bad | good | good |
| `73380ff8277a4289397c9acadd797641` | spending | bad | good | good |
| `ac17233bc6736cf20601c097638fe414` | credit | bad | good | good |

`15b42e35` remained a miss.

Tokens as returned by the API, without a monetary estimate: adapt 1 446 334 prompt and 20 333 completion, eval 333 660 prompt and 4 222 completion. The provider did not populate the cost field.

## What this score cannot establish

The organizers will take the fork commit and run `adapt` themselves on private training data, starting with an empty artifacts directory. The public test contains no hidden rules, so 0.9507 says nothing about them. The blind evaluation grouped by train contexts, already in `docs/BLIND-EVAL.md`, gives 0.922; I did not rerun it.

The run was local, not in Docker. The model was closed-source Gemini because my `.env` has no OpenRouter key. The team's submission default is different: an open model through OpenRouter. In the step 3 `docs`, there was still no live OpenRouter response as of 14:05; that run failed at DNS. If the organizers' container has no key, the code will fall back to deterministic rules and 0.9502; this has already been checked separately, including in a container without network access.

Local run files, if they are still on disk: `out/art-gemini/`, `out/pred-gemini.csv`, `out/score-gemini.json`, `out/adapt-gemini.log`. They are not committed to the fork.
