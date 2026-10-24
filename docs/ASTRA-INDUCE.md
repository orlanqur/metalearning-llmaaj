# Plata self-learning — 2026-10-24
Model `openai/gpt-oss-120b`; `original`; train 150, public test 80; branch `orlanqur/induce`.
`adapt --from-scratch` / `ADAPT_MODE=from_scratch`: the library is not instantiated, the initial rule set is empty; the default remains hybrid.
Residual bad → nearest good in the same topic → 1–3 hypotheses → full train → active / one narrowing / boundary → new residuals.
Limits: ≤6 rounds, 8 pairs/round, `INDUCTION_MAX_CALLS=400` for the entire adapt run (library, verify, retries); cache hits do not consume the budget.
Gate: TP≥1, FP=0, not_checked=0, no degradation within the topic; stop on no active-rule progress/no residuals, budget exhaustion, or API unavailability.
The prompt requires recalculating context values and factual conditions; library examples serve only as grammar. The English `Induction trail` is rendered from the manifest with supporting examples and rejections.

| Mode / dataset | Macro | credit | financial_position | savings | spending |
|---|---:|---:|---:|---:|---:|
| Library without model / train | 0.994318 | 1.000000 | 1.000000 | 1.000000 | 0.977273 |
| Library without model / test | 0.950231 | 0.933333 | 0.954545 | 1.000000 | 0.913043 |
| From-scratch, checkpoint / train | 0.624926 | 0.694444 | 0.583333 | 0.676471 | 0.545455 |
| From-scratch, checkpoint / test | 0.625889 | 0.600000 | 0.681818 | 0.700000 | 0.521739 |
| Hybrid / train | 0.994318 | 1.000000 | 1.000000 | 1.000000 | 0.977273 |
| Hybrid / test | 0.925231 | 0.933333 | 0.954545 | 0.900000 | 0.913043 |

| Mode | HTTP adapt | Tokens adapt | USD adapt | Wall adapt, s |
|---|---:|---:|---:|---:|
| Library without model | 0 | 0 | 0.000000 | 2.7 |
| From-scratch, checkpoint | ≥78 | ≥409648 | ≥0.039919 | 3300.0 (timeout) |
| Hybrid | 299 | 1251046 | 0.070911 | 1965.9 |

From-scratch **incomplete**: timeout after 55 min, 3 active rules saved from an unfinished round; test includes 1 fallback. This is a checkpoint evaluation, not a complete self-learning run.
Hybrid: adapt completed; two new hypotheses rejected for invalid numeric scope, no new active rules; test is below 0.950231 by 0.025 (savings 0.9 instead of 1.0).
One from-scratch request took 1402.38 s and 115373 completion tokens, then produced a JSON ValueError; its usage is included. Usage of unfinished requests is unknown: ≥ denotes the recorded log prefix.
Added optional `LLM_MAX_TOKENS` ([OpenRouter contract](https://openrouter.ai/docs/api_reference/parameters#max-tokens)); the unset default is preserved. Original runs used unset; the eval rerun used 4096.
Hybrid eval rerun: 12 HTTP, 44432 tokens, $0.002091 + 26 cached responses; fallback 2. From-scratch bounded eval: completed: 17 HTTP, 99284 tokens, $0.023749.
With max_tokens=4096 requested, the provider reported 32898 completion tokens in one response; this is not a guaranteed wall time limit.
The full cost of all eval attempts is unknown; the original hybrid eval was interrupted by timeout. Limit smoke test: 1 HTTP / 267 tokens / $0.00002528; separate from the adapt table.
Artifacts: `artifacts/from_scratch/`, `artifacts/hybrid/` — manifest, explanation, induction_log, model_log, run_meta, cache; partial is explicitly marked.
Metrics: `out/induce/{library_no_model,from_scratch,hybrid}/{train_score.json,test_score.json}`; predictions and logs are linked by hashes, the final relinking used cache without HTTP.
Commands/history: `commands.json`, `commands_original.json`, `usage.json`; eval reruns in `out/induce/{hybrid,from_scratch_snapshot}_bounded/`; parameters in `out/induce/protocol.json`.
Rerun: standard prepare_inputs → `python3 -S -m solution.measure_induction <режим>` into clean directories; the response limit is enabled separately via env. Partial recovery: `out/induce/finalize_partial.py`.
Checks: 48/48 tests + 9/9 scorer; `out/induce/tests.txt`, `scorer-tests.txt`, `validation.json`; the final no-key smoke test confirmed byte-identical predictions and the previous test score of 0.9502305665349143.
Strict self-review: `out/induce/review.md`; no separate critic. Train is resubstitution, no CV; FactSheet/grammar are prior knowledge, the library had previously used both public splits.
`src/`, `data/`, `README.md`, `TEAM/`, `eval_blind/`, `demo/` unchanged. Artifacts/out are gitignored and local.
The code was found in commit `ed6c15e` (13:37:59 UTC, created outside this session's successful Git actions); the final report is uncommitted: a repeated git add was blocked by the sandbox on the shared index.lock. No push was performed.
Started 12:34 UTC; report updated 13:42:22 UTC; hard cutoff 13:44 UTC.
