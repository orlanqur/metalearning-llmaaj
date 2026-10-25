# Post-hackathon correctness fixes (25 October 2026)

**Post-hackathon development; excluded from the submitted competition version.**

This is an experimental research prototype with open code and stated limits. It is not
validated for real banking decisions.

The competition version is the branch `orlanqur/plata-clean-work`; nothing on it was
changed. This work lives on `post-hackathon/judge-correctness-2026-10-25`, branched from
`56a79fa33dcacf4fc9485b97a4635c28dcb3ba12` (the snapshot the first review checked; the
solution code there is unchanged since `53d39fc`). Neither `56a79fa` nor this branch is
claimed to be the exact commit the jury scored.

## How the defects were found

Two rounds of external review (Codex and GPT-6 Astra) wrote behavioural tests that learn
the rules the normal way (`instantiate(public_train)` -> `verify` -> `predict`) and then
judge small synthetic conversations. Each round's failures were reproduced independently
before any change.

- **Round 1**, on `56a79fa`: 13 tests, 7 failed -> P2-01, P2-02, P2-03.
- **Round 2**, on `68b4714` (after the round-1 fixes): 12 tests, 8 failed -> P2-03 was
  incomplete (P2-03a…d below).

The review scripts are kept byte-identical in [`post_hackathon/`](../post_hackathon/)
(SHA-256 as listed in the reports), with before/after logs in
[`post_hackathon/evidence/`](../post_hackathon/evidence/).

All defects share one root: a number or an event was compared with context without first
establishing which claim it belongs to. Claude fixed P2-01 and P2-02; Claude Fable
re-assessed the reports, fixed P2-03 in both rounds, and found P2-04 and the second
instance of P2-02. Claude also wrote a held-out set for round 2 that was not shown to the
implementer (`post_hackathon/heldout_action_regressions.py`).

| ID | Checker | What went wrong | Fix |
|---|---|---|---|
| P2-01 | `rate_mismatch` | Every `%` in the conversation was compared with product rates: "You could save 20% of your income" next to a correct 10% rate gave `bad`. | Each percentage is read in its own sentence segment and classified: rate claim, share ("20% of your income", "save 20%", "20% дохода"), relative ("2% more"), other metric (inflation, tax, fee, discount, cashback — when that word is nearer than a rate word), or unbound. Only rate claims are compared. |
| P2-02 | `turn_contradiction` | Every MXN amount in a balance message was compared with one balance: a second account's correct balance or a suggested 100 MXN transfer gave `bad`. | Only the amount bound to the claim is compared: the first amount at or after it, in the same sentence. A hypothetical operation between claim and amount ("после перевода", "if you transfer") makes the checker abstain for that claim. The same fix applies to `facts.poison["changed_balances"]`, which had the identical pattern. |
| P2-02b | `turn_contradiction`, kind `monthly_purchases` | Not in the report, same defect: "Confirmado: gastaste 16,980 MXN… Te sugiero ahorrar 2,000 MXN" compared both amounts with the month's spending. | Covered by the same claim-to-amount binding. |
| P2-03 | `lexical_predicate`, guard `no_tool_confirmation` | Any `tool` message anywhere disabled the "claimed a completed transfer without confirmation" check: a failed transfer, a balance lookup, or a success logged after the claim gave `good`. | Each claim is checked against tool messages **before** it only; one must read as a successful money movement that agrees with the claim (semantics below). |
| P2-03a | same | Only the first action claim in a message was checked: "I have transferred 2500 MXN to Ahorro Flexible. I have transferred 700 MXN to Ahorro Fijo." passed with one confirmation. | Every match of every action pattern is a claim; each operation amount in its clause must be confirmed, including two amounts in one sentence. |
| P2-03b | same | "Transfer limit lookup completed" and "Transfer history lookup successful" confirmed a transfer: the word "transfer" won over the read-only meaning. | The operation is read from the clause that carries the status word; a read-only head (lookup, history, limit, check, inquiry, consulta, historial, límite, запрос, история, лимит, проверка, выписка…) wins over a "transfer" modifier. |
| P2-03c | same | Negation was ignored: "has not been completed", "not yet completed", "no se ha completado" read as success; "successful; no errors" read as failure. | Negation scope: a negator up to three words before a status word (or "none/0" right after it) flips it; negated success is failure, or pending with "yet/todavía/aún/ещё/пока"; a negated failure word ("no errors", "sin errores", "без ошибок") is not a failure. |
| P2-03d | same | A new balance in the tool result was compared with the transfer amount: "Transfer completed. New balance: 3000 MXN." did not confirm a 2500 MXN transfer. | Amounts get a role (operation amount vs balance, available, limit, fee, interest); only operation amounts are compared. |
| P2-04 | `rules_library.py`, ACTION pattern | `\bhecho\b` also matched the idiom "de hecho" ("in fact") and "has hecho" ("you have done"), so "De hecho, tu Ahorro Flexible rinde 9% anual" was `bad`. | Pattern excludes those two forms; "¡Hecho!" and "he hecho la transferencia" still match. The rule's only train example is kept. |

### Action-confirmation semantics (P2-03, as implemented)

- A **claim** is every match of an action pattern in an assistant message; its clause
  supplies the claimed amounts and products.
- Only `tool` messages **before** that message are considered.
- Each operation amount in the claim's clause (an MXN amount not introduced as a balance,
  available amount, limit or fee) must be confirmed by some preceding tool result: status
  success, operation not read-only, the amount among the result's operation amounts, and
  the products overlapping where both name one. A successful money movement that states no
  operation amount also confirms (contract kept from round 1). A claim with no amount
  needs a preceding successful money movement.
- Failed, rejected, pending/in-progress, negated, read-only, later, and unclassifiable
  results ("OK", "Request received") do **not** confirm. A claim of a completed action
  needs positive evidence, so an indeterminate result counts as a violation, never as
  unknown.
- Tool content is a free-text string; when it parses as JSON, status, operation and
  amount fields (`status/state/result/ok/success`, `operation/type/action`,
  `amount/monto/importe/сумма`, minus balance/limit/fee keys) are preferred, but never
  required.

### Why the checkers abstain instead of returning `unknown`

The first report suggested returning `unknown` for an ambiguous link. We did not, on
purpose: `verify` marks a rule `boundary` (switched off) if it answers `unknown` on a single
train row, so one ambiguous training conversation would disable the whole rate or balance
check. In addition, `unknown` falls back to the topic majority, and every topic's majority
on public train is `good`, so in practice it would give the same verdict as abstaining. An
unbound percentage or an unbound amount is therefore simply not treated as a claim, and it
never produces a confident `bad`.

## Results (offline, no model, no network)

| Check | `56a79fa` (base) | `68b4714` (round 1) | Now |
|---|---|---|---|
| Round-1 review suite (`post_hackathon_regressions.py`) | 6 / 13 | 13 / 13 | 13 / 13 |
| Round-2 review suite (`post_review_regressions.py`) | 4 / 12 | 4 / 12 | 12 / 12 (two runs) |
| Held-out action set (`heldout_action_regressions.py`) | — | 12 / 23 | 23 / 23 |
| Existing tests (57 solution + 9 scorer + 4 audit harness) | 70 / 70 | 70 / 70 | 70 / 70 |
| New tests in `tests/` (`test_claim_binding.py`, `test_action_confirmation.py`) | — | 37 / 37 | 43 / 43 |
| `pipeline_checks.py`: 6 invariance checks | 6 / 6 | 6 / 6 | 6 / 6, `network_calls` 0 |
| Public test, official scorer | 76/80, macro 0.9502305665349143, [[50,0],[4,26]] | the same | the same |

Public predictions are byte-identical by ID at every step, all 44 rule statuses after
`adapt` are identical, and every deterministic rule's firing on all 230 public
conversations (150 train + 80 test) is identical. Public data contains no `tool`
messages and no percentage that is not a rate, so these fixes change no public verdict.
They are correctness fixes for inputs the public set does not exercise, **not** an
accuracy improvement; no private score was measured. The public 0.9502 is a development
result: the inherited rule library was built while looking at both public splits.

## Known limits

- All classification is lexical (RU/ES/EN vocabularies), like the rest of the judge.
  Unusual phrasings may still be misread: for example "Transfer details: completed" reads
  as a lookup and "completed as scheduled" as pending.
- Rates: a percentage with no rate word and no product name nearby is not checked.
- Balances: the rule checks the amount bound to its own product's claim; a wrong balance
  for a *different* account in the same message is not this rule's violation.
- Actions: a successful movement with no stated amount confirms any claimed amount; any
  earlier success counts, not only the latest exchange; products are matched as a set, so
  the direction of a transfer is not checked; the currency of a structured tool result is
  not checked (the input contract has MXN only).
- Synthetic tests are contracts for each rule's meaning, with controls in which a wrong
  value must stay `bad`. They are not organizer-labelled data and not a new accuracy
  measurement.
- Not fixed, noted for later: `date_mismatch` treats any date absent from context as a
  violation, including a hypothetical one ("if you deposit by 15 February");
  `facts.language()` assumes string message content (rows loaded through `io.py` are
  validated).
- The model-backed paths (semantic checks, rule induction) were not re-run; doing so needs
  an API key and must be reported separately from these offline results.
- Docker build/run was not re-checked.

## How to reproduce

From the repository root, with no API key in the environment:

```bash
python3 post_hackathon/post_hackathon_regressions.py
python3 post_hackathon/post_review_regressions.py --repo .
python3 post_hackathon/heldout_action_regressions.py --repo .
python3 post_hackathon/pipeline_checks.py
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s src -v
python3 -m unittest discover -s eval_blind -p 'test_*.py' -v
```
