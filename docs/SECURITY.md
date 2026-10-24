# Safety notes

**What it is.** A judge that labels banking-assistant conversations `good` or `bad`. It has no tools and performs no actions; it is not financial advice.

**Prompt injection.** Conversations and context are untrusted text.
- Prompts mark dialogs and context as data, never instructions (`solution/semantic.py`, `solution/induce.py`).
- Model output is schema-checked: `yes` / `no` / `unknown`. A `yes` needs an exact quote from an assistant turn, otherwise it becomes `unknown`.
- Numbers and dates are computed by code. Deterministic checks run first, and the model cannot overrule a deterministic violation.
- Induced rules use a small condition language with no `eval`/`exec`. A rule is accepted only after verification against the training labels (precision ≥ 0.9, at least 3 distinct contexts).
- Measured: injection probes from the blind audit (`eval_blind/`) — see the README for results with and without the model.

**Failures.** Requests have a 45 s socket timeout, a total deadline per request (`LLM_DEADLINE`, default 135 s; providers can keep a connection alive with whitespace) and 3 retries, after which the run falls back to the deterministic rules. `predictions.csv` is always written, and malformed messages are dropped instead of aborting the run. The API key is read from `.env` or the environment and is never logged.
