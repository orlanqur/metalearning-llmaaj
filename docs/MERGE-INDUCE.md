# MERGE-INDUCE — 2026-10-24
.env.example: preserved LLM_WORKERS=4, ADAPT_MODE=hybrid, induction limits, and optional LLM_MAX_TOKENS.
solution/adapt.py: preserved from-scratch and the Induction trail from the manifest; limitations and explanations are in English.
solution/induce.py: pmap discovery within each round with a shared history snapshot; verify/narrow/accept sequentially, then recalculate residuals; ≤6 rounds.
solution/llm.py: atomic HTTP-budget reservation without blocking I/O; the new test reproduced 2 requests with a limit of 1 before the fix, afterward — PASS.
`python3 -S -m unittest discover -s tests`: Ran 53 tests, OK (including induction_loop, robustness, and 2 merge regressions).
`python3 -S -m unittest discover -s src -p 'test_*.py'`: Ran 9 tests, OK.
Without keys, adapt/eval --no-model in artifacts/merge_check and out/merge_check.csv: exit 0, HTTP=0; `cmp out/accept.csv out/merge_check.csv`: exit 0, empty stdout.
`python3 -S src/evaluate.py --test data/public_test.csv --predictions out/merge_check.csv --out out/merge_check.json`: score=0.9502305665349143, 76/80.
Default hybrid: 44 rules, predictions unchanged; adapt --from-scratch --no-model: exit 0, 0 rules; explanation matches the manifest in both modes.
No conflict markers; hashes of all 448 protected files matched, no new files in protected paths; no Git commands were executed.
Sources: ASTRA-INDUCE.md and code/tests (SOL-FIX.md is missing); strict self-review, no separate critic/live LLM; logs and validation.json: out/merge_check_evidence/.
