# Post-hackathon correctness fixes (25 October 2026)

**Post-hackathon development; excluded from the submitted competition version.**

The competition version is the branch `orlanqur/plata-clean-work`; nothing on it was
changed. This work lives on `post-hackathon/judge-correctness-2026-10-25`, branched from
`56a79fa33dcacf4fc9485b97a4635c28dcb3ba12` (the snapshot the bug report reviewed; the
solution code there is unchanged since `53d39fc`). It is not the commit the jury scored.

## Where the defects came from

After the hackathon, an external review (Codex and Astra) wrote behavioural tests that
learn the rules the normal way (`instantiate(public_train)` -> `verify` -> `predict`) and
then judge small synthetic conversations. 7 of its 13 tests failed on `56a79fa`. We
reproduced all 7 independently before changing anything. The tests are kept byte-identical
in [`post_hackathon/`](../post_hackathon/) (SHA-256 as listed in the report).

All three defects have the same root: a number or an event was compared with context
without first establishing which claim it belongs to. Claude fixed P2-01 and P2-02;
Claude Fable independently re-assessed the report, fixed P2-03, and found P2-04 and the
second instance of P2-02.

| ID | Checker | What went wrong | Fix |
|---|---|---|---|
| P2-01 | `rate_mismatch` | Every `%` in the conversation was compared with product rates: "You could save 20% of your income" next to a correct 10% rate gave `bad`. | Each percentage is read in its own sentence segment and classified: rate claim, share ("20% of your income", "save 20%", "20% дохода"), relative ("2% more"), other metric (inflation, tax, fee, discount, cashback — when that word is nearer than a rate word), or unbound. Only rate claims are compared. |
| P2-02 | `turn_contradiction` | Every MXN amount in a balance message was compared with one balance: a second account's correct balance or a suggested 100 MXN transfer gave `bad`. | Only the amount bound to the claim is compared: the first amount at or after it, in the same sentence. A hypothetical operation between claim and amount ("после перевода", "if you transfer") makes the checker abstain for that claim. The same fix applies to `facts.poison["changed_balances"]`, which had the identical pattern. |
| P2-02b | `turn_contradiction`, kind `monthly_purchases` | Not in the report, same defect: "Confirmado: gastaste 16,980 MXN… Te sugiero ahorrar 2,000 MXN" compared both amounts with the month's spending. | Covered by the same claim-to-amount binding. |
| P2-03 | `lexical_predicate`, guard `no_tool_confirmation` | Any `tool` message anywhere disabled the "claimed a completed transfer without confirmation" check: a failed transfer, a balance lookup, or a success logged after the claim gave `good`. | Each claim is checked on its own, against tool messages **before** it only. One of them must read as a *success* of a *money movement* (RU/ES/EN free text; JSON fields are used when present but never required). Where both sides name an MXN amount, the amounts must agree; where both name a context product, they must overlap. Failed, rejected, pending/in-progress, read-only (balance or rate lookup) and later results do not confirm. A tool text that cannot be classified ("OK", "Request received") is **not** a confirmation: a claim of a completed action needs positive evidence. |
| P2-04 | `rules_library.py`, ACTION pattern | Found while fixing P2-03: `\bhecho\b` also matched the idiom "de hecho" ("in fact") and "has hecho" ("you have done"), so "De hecho, tu Ahorro Flexible rinde 9% anual" was `bad`. | Pattern excludes those two forms; "¡Hecho!" and "he hecho la transferencia" still match. The rule's only train example is kept. |

### Why the checkers abstain instead of returning `unknown`

The report suggested returning `unknown` for an ambiguous link. We did not, on purpose:
`verify` marks a rule `boundary` (switched off) if it answers `unknown` on a single train
row, so one ambiguous training conversation would disable the whole rate or balance
check. In addition, `unknown` falls back to the topic majority, and every topic's
majority on public train is `good`, so in practice it would give the same verdict as
abstaining. An unbound percentage or an unbound amount is therefore simply not treated
as a claim, and it never produces a confident `bad`.

## Results (offline, no model, no network)

| Check | Before (`56a79fa`) | After |
|---|---|---|
| Report's behavioural suite (`post_hackathon/post_hackathon_regressions.py`) | 6 / 13 pass | 13 / 13 (three runs) |
| Existing tests (57 solution + 9 scorer + 4 audit harness) | 70 / 70 | 70 / 70 |
| New independent tests (`tests/test_claim_binding.py`, `tests/test_action_confirmation.py`) | — | 37 / 37 |
| `post_hackathon/pipeline_checks.py`: 6 invariance checks | 6 / 6 | 6 / 6, `network_calls` 0 |
| Public test, official scorer | 76/80, macro 0.9502305665349143, [[50,0],[4,26]] | the same |
| Public predictions by ID | — | byte-identical to before |
| Rule statuses after `adapt` (44 rules) | — | identical |

Every deterministic rule's firing on all 230 public conversations (150 train + 80 test) is
identical before and after. Public data contains no `tool` messages and no percentage that
is not a rate, so these fixes change no public verdict. They are correctness fixes for
inputs the public set does not exercise, **not** an accuracy improvement, and no private
score was measured.

## Known limits

- The classification is lexical (RU/ES/EN vocabularies), like the rest of the judge.
  "20% of your income", "save 20%", "inflation is 4%" are recognised; unusual phrasings
  may still be misread. A percentage with no rate word and no product name nearby is not
  checked at all.
- The balance rule checks the amount bound to its own product's claim. A wrong balance
  for a *different* account in the same message is not this rule's violation.
- Action confirmation does not check the direction of a transfer (products are matched as
  a set), and any earlier successful transfer counts, not only the latest exchange.
- New tests use synthetic conversations as contracts for each rule's meaning, with
  controls in which a wrong value must stay `bad` (in `tests/test_claim_binding.py`, nine
  behavioural tests fail on `56a79fa`, the controls pass on both). They are not
  organizer-labelled data and not a new accuracy measurement.
- Not fixed, noted for later: `date_mismatch` treats any date absent from context as a
  violation, including a hypothetical one ("if you deposit by 15 February");
  `facts.language()` assumes string message content (rows loaded through `io.py` are
  validated).
- The model-backed paths (semantic checks, rule induction) were not re-run; doing so needs
  an API key and must be reported separately from these offline results.
- Docker build/run was not re-checked in this environment.

## How to reproduce

From the repository root, with no API key in the environment:

```bash
python3 post_hackathon/post_hackathon_regressions.py
python3 post_hackathon/pipeline_checks.py
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s src -v
python3 -m unittest discover -s eval_blind -p 'test_*.py' -v
```
