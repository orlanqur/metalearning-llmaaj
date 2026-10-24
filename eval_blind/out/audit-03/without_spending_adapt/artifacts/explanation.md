# Explanation — learned rules and deterministic checks

Manifest SHA256: `d46f5fb80e0b855252a20731284f0df435dc9bdabaa8e67b81f0416fb78005e9`

## 1. Clear criteria

Candidates are parameterized inherited templates. Context supplies amounts, dates, rates and periods. Inherited templates require TP >= 1 and FP = 0 with no unchecked rows. Induced rules require precision >= 0.9, at least three distinct TP contexts, no unchecked rows, and no accuracy loss in any topic. These observations do not establish universal rules.

| Rule | Topic | Criterion | TP | FP | Precision | Bad coverage |
|---|---|---|---:|---:|---:|---:|
| `credit.DATE.context` | credit | Dates asserted as facts must occur in context (explicit years also agree). | 1 | 0 | 1.000 | 0.083 |
| `credit.KNOWN_DATA.deny_date` | credit | Do not withhold a payment date supplied by the statement. | 4 | 0 | 1.000 | 0.333 |
| `credit.MIN_INTEREST.lexical` | credit | A minimum payment below the interest-free payment cannot waive interest. | 4 | 0 | 1.000 | 0.333 |
| `credit.PAID_STATUS.lexical` | credit | Do not call an already covered statement payment pending. | 1 | 0 | 1.000 | 0.083 |
| `financial_position.CREDIT_AS_MONEY.poison` | financial_position | Do not add available credit or a credit limit to own funds. | 4 | 0 | 1.000 | 0.267 |
| `financial_position.HOLD.available_amount` | financial_position | When funds are held, state a supported currently spendable amount. | 4 | 0 | 1.000 | 0.267 |
| `financial_position.NET.net_amount` | financial_position | When debt exists, give own funds after debt using one supported availability convention. | 5 | 0 | 1.000 | 0.333 |
| `savings.ACTION.lexical` | savings | Do not assert a completed transfer without a confirming tool event. | 1 | 0 | 1.000 | 0.083 |
| `savings.AMOUNT.balance_cuenta_veluna` | savings | A newly asserted account balance must agree with unchanged context. | 1 | 0 | 1.000 | 0.083 |
| `savings.DATE.context` | savings | Dates asserted as facts must occur in context (explicit years also agree). | 1 | 0 | 1.000 | 0.083 |
| `savings.FIXED_LOCK.lexical` | savings | Do not promise early withdrawal of a fixed-term deposit. | 4 | 0 | 1.000 | 0.333 |
| `savings.RATE.ahorro_flexible` | savings | Rates attributed to Ahorro Flexible must match that product. | 4 | 0 | 1.000 | 0.333 |
| `savings.RATE.selected_tariff` | savings | Quoted rates must match the subscription and product in context. | 3 | 0 | 1.000 | 0.250 |
| `credit.KNOWN_DATA.ask_populated_field` | credit | Do not request a balance, debt, payment, subscription or transaction detail already populated in context. | 2 | 0 | 1.000 | 0.167 |
| `financial_position.KNOWN_DATA.ask_populated_field` | financial_position | Do not request a balance, debt, payment, subscription or transaction detail already populated in context. | 3 | 0 | 1.000 | 0.200 |
| `savings.KNOWN_DATA.ask_populated_field` | savings | Do not request a balance, debt, payment, subscription or transaction detail already populated in context. | 1 | 0 | 1.000 | 0.083 |

Coverage denominator: all bad training rows in the rule's topic; `all` means all four topics for shared formatting conventions. Precision denominator: TP + FP.

## 2. Clear priorities

Eval orders active rules by `(priority, id)`. Any violation in any assistant turn makes the entire conversation bad. No good example or boundary overrides an active violation. If none fires and a check is unknown/unavailable, use the saved topic majority; otherwise use the manifest default_label. Unknown is never itself a violation. Numeric tolerance is max(1 currency unit, 0.5% of expected); rate tolerance is 0.05 percentage points.

- Priority 10: `credit.DATE.context`, `credit.KNOWN_DATA.deny_date`, `credit.MIN_INTEREST.lexical`, `credit.PAID_STATUS.lexical`, `financial_position.CREDIT_AS_MONEY.poison`, `financial_position.HOLD.available_amount`, `financial_position.NET.net_amount`, `savings.ACTION.lexical`, `savings.AMOUNT.balance_cuenta_veluna`, `savings.DATE.context`, `savings.FIXED_LOCK.lexical`, `savings.RATE.ahorro_flexible`, `savings.RATE.selected_tariff`
- Priority 20: `credit.KNOWN_DATA.ask_populated_field`, `financial_position.KNOWN_DATA.ask_populated_field`, `savings.KNOWN_DATA.ask_populated_field`

## 3. Links to training examples

- `credit.DATE.context`: [0eea79a6cac297b8b6e8dd9141342211](#example-0eea79a6cac297b8b6e8dd9141342211) (bad); [13d8ebe62247572aebdcc41e54a9972a](#example-13d8ebe62247572aebdcc41e54a9972a) (good)
- `credit.KNOWN_DATA.deny_date`: [2ba2e55ebb82fbdf3f2c5fe8563ef381](#example-2ba2e55ebb82fbdf3f2c5fe8563ef381) (bad); [2c970a10f2f03e74e3e27474eb8cba7c](#example-2c970a10f2f03e74e3e27474eb8cba7c) (bad); [13d8ebe62247572aebdcc41e54a9972a](#example-13d8ebe62247572aebdcc41e54a9972a) (good)
- `credit.MIN_INTEREST.lexical`: [13120e9df1d7546bfb9747489ec52f54](#example-13120e9df1d7546bfb9747489ec52f54) (bad); [247303d9f7e7030f41fa4e2c316b8b65](#example-247303d9f7e7030f41fa4e2c316b8b65) (bad); [13d8ebe62247572aebdcc41e54a9972a](#example-13d8ebe62247572aebdcc41e54a9972a) (good)
- `credit.PAID_STATUS.lexical`: [a1a651b2ad3fc21371964782fca2306c](#example-a1a651b2ad3fc21371964782fca2306c) (bad); [13d8ebe62247572aebdcc41e54a9972a](#example-13d8ebe62247572aebdcc41e54a9972a) (good)
- `financial_position.CREDIT_AS_MONEY.poison`: [c09ec6bd7674048bc119a4b012fb077b](#example-c09ec6bd7674048bc119a4b012fb077b) (bad); [c90e863af9a20b3f91262df81ac8d13e](#example-c90e863af9a20b3f91262df81ac8d13e) (bad); [18d0b59b0cb5c3eefb47d9f4b1cf1117](#example-18d0b59b0cb5c3eefb47d9f4b1cf1117) (good)
- `financial_position.HOLD.available_amount`: [284db98e9fbb9c6869b0c143058552a3](#example-284db98e9fbb9c6869b0c143058552a3) (bad); [8b99e4d6dd481e022802f71bac669664](#example-8b99e4d6dd481e022802f71bac669664) (bad); [18d0b59b0cb5c3eefb47d9f4b1cf1117](#example-18d0b59b0cb5c3eefb47d9f4b1cf1117) (good)
- `financial_position.NET.net_amount`: [1bedba8378bf0d211f19975329848356](#example-1bedba8378bf0d211f19975329848356) (bad); [54ac7aedcdc80c809e147100b6eabd7f](#example-54ac7aedcdc80c809e147100b6eabd7f) (bad); [18d0b59b0cb5c3eefb47d9f4b1cf1117](#example-18d0b59b0cb5c3eefb47d9f4b1cf1117) (good)
- `savings.ACTION.lexical`: [0b056b6072e50369a8477e95a5d53e77](#example-0b056b6072e50369a8477e95a5d53e77) (bad); [0b50f54eca499508d9b1aac7c8d48c25](#example-0b50f54eca499508d9b1aac7c8d48c25) (good)
- `savings.AMOUNT.balance_cuenta_veluna`: [80079c6727853d113b1ecb6b72c7dc96](#example-80079c6727853d113b1ecb6b72c7dc96) (bad); [0b50f54eca499508d9b1aac7c8d48c25](#example-0b50f54eca499508d9b1aac7c8d48c25) (good)
- `savings.DATE.context`: [b74bb59f9ed75f5e126fef51f0705e5f](#example-b74bb59f9ed75f5e126fef51f0705e5f) (bad); [0b50f54eca499508d9b1aac7c8d48c25](#example-0b50f54eca499508d9b1aac7c8d48c25) (good)
- `savings.FIXED_LOCK.lexical`: [11ff2e6665f635832001290394d7b043](#example-11ff2e6665f635832001290394d7b043) (bad); [1cc197350645f6c731ff191fc0a597e5](#example-1cc197350645f6c731ff191fc0a597e5) (bad); [29b7b26be9c10bc329efe3b9dbdadf51](#example-29b7b26be9c10bc329efe3b9dbdadf51) (good)
- `savings.RATE.ahorro_flexible`: [25043fb0721c9de79e5cc72adba5139b](#example-25043fb0721c9de79e5cc72adba5139b) (bad); [4db99b0fb8e5be99f886023b2b3d2079](#example-4db99b0fb8e5be99f886023b2b3d2079) (bad); [0b50f54eca499508d9b1aac7c8d48c25](#example-0b50f54eca499508d9b1aac7c8d48c25) (good)
- `savings.RATE.selected_tariff`: [25043fb0721c9de79e5cc72adba5139b](#example-25043fb0721c9de79e5cc72adba5139b) (bad); [7475d87278111b12a6efcf987968e123](#example-7475d87278111b12a6efcf987968e123) (bad); [0b50f54eca499508d9b1aac7c8d48c25](#example-0b50f54eca499508d9b1aac7c8d48c25) (good)
- `credit.KNOWN_DATA.ask_populated_field`: [1947acadc729f44cef4c17f20ec81669](#example-1947acadc729f44cef4c17f20ec81669) (bad); [4de0c1d47616e3cd3b10af2989e5f3bd](#example-4de0c1d47616e3cd3b10af2989e5f3bd) (bad); [13d8ebe62247572aebdcc41e54a9972a](#example-13d8ebe62247572aebdcc41e54a9972a) (good)
- `financial_position.KNOWN_DATA.ask_populated_field`: [22c3c8a00320a4740b3f8a20536583a8](#example-22c3c8a00320a4740b3f8a20536583a8) (bad); [6a2c08047b0396f96250e4a086d920d1](#example-6a2c08047b0396f96250e4a086d920d1) (bad); [18d0b59b0cb5c3eefb47d9f4b1cf1117](#example-18d0b59b0cb5c3eefb47d9f4b1cf1117) (good)
- `savings.KNOWN_DATA.ask_populated_field`: [4f6de85c6f13f76ea29f8d13edfea60d](#example-4f6de85c6f13f76ea29f8d13edfea60d) (bad); [0b50f54eca499508d9b1aac7c8d48c25](#example-0b50f54eca499508d9b1aac7c8d48c25) (good)

## 4. Clear boundaries

FP > 0 means the strict template conflicts with at least one good label and is disabled. Induced candidates with FP receive one narrowing round and must then pass the saved acceptance gates. This is evidence against that candidate, not permission for arbitrary errors. TP = 0 means insufficient support. Unavailable semantic checks remain explicitly not_checked. No boundary was assigned manually.

- `credit.AMOUNT.remaining_debt` — Remaining debt must match statement debt or debt minus payments. Status: no_positive_support; TP=0, FP=0.
  Evidence: [13d8ebe62247572aebdcc41e54a9972a](#example-13d8ebe62247572aebdcc41e54a9972a) (good).
  No violating bad witness; no good/bad pair is claimed.
- `credit.MIN_INTEREST.semantic` — The assistant claims paying only the minimum avoids interest although the minimum is below the statement interest-free payment. Status: not_checked; TP=0, FP=0.
  No violating bad witness; no good/bad pair is claimed.
- `credit.NONANSWER.semantic` — The assistant fails to answer the user's financial question despite the necessary facts being present in context, including deflection or requesting already known information. Status: not_checked; TP=0, FP=0.
  No violating bad witness; no good/bad pair is claimed.
- `financial_position.NONANSWER.semantic` — The assistant fails to answer the user's financial question despite the necessary facts being present in context, including deflection or requesting already known information. Status: not_checked; TP=0, FP=0.
  No violating bad witness; no good/bad pair is claimed.
- `savings.ACTION.semantic` — The assistant claims a transfer or other account-changing action was completed without a confirming tool event. Status: not_checked; TP=0, FP=0.
  No violating bad witness; no good/bad pair is claimed.
- `savings.FIXED_LOCK.semantic` — The assistant promises that a fixed-term Ahorro Fijo deposit can be withdrawn before maturity. Status: not_checked; TP=0, FP=0.
  No violating bad witness; no good/bad pair is claimed.
- `savings.NONANSWER.semantic` — The assistant fails to answer the user's financial question despite the necessary facts being present in context, including deflection or requesting already known information. Status: not_checked; TP=0, FP=0.
  No violating bad witness; no good/bad pair is claimed.
- `all.CONVENTION.anchor` — Strict hypothesis: every link anchor must be translated. Status: false_positives; TP=1, FP=1.
  Evidence: [46c829c7efe83c74cc11d2e53c3689cc](#example-46c829c7efe83c74cc11d2e53c3689cc) (good); [0b056b6072e50369a8477e95a5d53e77](#example-0b056b6072e50369a8477e95a5d53e77) (bad).
- `all.CONVENTION.links` — Strict hypothesis: only one observed link target is acceptable. Status: false_positives; TP=6, FP=39.
  Evidence: [0b50f54eca499508d9b1aac7c8d48c25](#example-0b50f54eca499508d9b1aac7c8d48c25) (good); [16d369527ab15f75a2a8b8c24fb2069e](#example-16d369527ab15f75a2a8b8c24fb2069e) (good); [0b056b6072e50369a8477e95a5d53e77](#example-0b056b6072e50369a8477e95a5d53e77) (bad).
- `all.CONVENTION.typo` — Strict hypothesis: any one-letter misspelling of a context product is bad. Status: false_positives; TP=0, FP=8.
  Evidence: [0b50f54eca499508d9b1aac7c8d48c25](#example-0b50f54eca499508d9b1aac7c8d48c25) (good); [48441f52eb41cdd6e85d90117f6ee697](#example-48441f52eb41cdd6e85d90117f6ee697) (good); [13d8ebe62247572aebdcc41e54a9972a](#example-13d8ebe62247572aebdcc41e54a9972a) (good).
  No violating bad witness; no good/bad pair is claimed.
- `credit.CONVENTION.residual_interest` — Strict hypothesis: reject every claim of interest on the residual after the interest-free payment. Status: false_positives; TP=4, FP=13.
  Evidence: [13d8ebe62247572aebdcc41e54a9972a](#example-13d8ebe62247572aebdcc41e54a9972a) (good); [199023647cd1fac04e8210e6985c7fdf](#example-199023647cd1fac04e8210e6985c7fdf) (good); [1947acadc729f44cef4c17f20ec81669](#example-1947acadc729f44cef4c17f20ec81669) (bad).
- `financial_position.CONVENTION.own_after_hold` — Strict hypothesis: own funds must always be quoted after holds. Status: false_positives; TP=3, FP=7.
  Evidence: [588a2b1aba93d7078fc4ac397d90a761](#example-588a2b1aba93d7078fc4ac397d90a761) (good); [90940f0e7d6bc9f5e5b7993fd386fe7b](#example-90940f0e7d6bc9f5e5b7993fd386fe7b) (good); [284db98e9fbb9c6869b0c143058552a3](#example-284db98e9fbb9c6869b0c143058552a3) (bad).
- `savings.CONVENTION.interest` — Strict hypothesis: only simple interest calculations are acceptable. Status: false_positives; TP=0, FP=1.
  Evidence: [16d369527ab15f75a2a8b8c24fb2069e](#example-16d369527ab15f75a2a8b8c24fb2069e) (good); [0b50f54eca499508d9b1aac7c8d48c25](#example-0b50f54eca499508d9b1aac7c8d48c25) (good).
  No violating bad witness; no good/bad pair is claimed.

## 5. Consistency with implementation

This file is rendered from `rules_spec.json`. `solution.eval` uses its `rules[].status`, `topic`, `applicability`, `checker`, `params` and `priority`. `solution.checkers.run_check` executes the saved rule; eval never re-instantiates templates or reads test labels. Labeled train examples are retrieved from fewshot_index.json; the current example is excluded. TP/FP witnesses and full quotes are persisted in that same manifest. `llm_predicate` returns yes/no/unknown with an assistant quote, or None if unavailable. The cache key binds model, system, user and schema. Eval reads artifacts/cache and writes its output cache.

### Internal check (limited)

Train resubstitution macro topic accuracy: 1.000000. Grouped-context split: not run. This is fitting-set performance, not an independent estimate. Inherited templates were reconstructed using both public splits; even a separate public score is not a clean holdout.

### Train evaluation through the same eval engine

| Topic | Correct / N | Accuracy | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|
| credit | 36 / 36 | 1.000000 | 12 | 0 | 0 | 24 |
| financial_position | 36 / 36 | 1.000000 | 15 | 0 | 0 | 21 |
| savings | 34 / 34 | 1.000000 | 12 | 0 | 0 | 22 |

## Как найдены правила

Шаблоны инстанцируются из полей входного train и заново проверяются на всём train. Индукция использует ошибки текущего манифеста и bad без объяснения: ближайший good той же темы по TF-IDF context, 1–2 атомарные гипотезы без списка известных семейств, затем до 8 канонических правил на тему. Каждый кандидат проверяется на всём train; при FP выполняется один раунд сужения. Все гипотезы и отказы сохраняются в induction_log.json.

Фактический статус индукции: `skipped_disabled`. Принятые ID: нет.

## Ограничения

Модельные шаги: `skipped_no_key_or_disabled`. При отсутствии ключа новые правила, семантические критерии, zero-shot baseline и rediscovery не подтверждены живой моделью. Кэш может дать ранее проверенный ответ; API-ошибки и unknown логируются. Поддержка считается по точным различным context; near-duplicate grouping и cross-validation не реализованы. Совпадение train не доказывает качество на приватном наборе.

### Quoted training evidence

<a id="example-0b056b6072e50369a8477e95a5d53e77"></a>
**0b056b6072e50369a8477e95a5d53e77 — expert label `bad`**

> Turn 1: Rafael, en tu Cuenta Veluna tienes 33 500 MXN; Ahorro Flexible tiene 1 000 MXN. No tienes Veluna+, así que Ahorro Flexible rinde 9% anual. Ahorro Fijo no puede retirarse antes del vencimiento. Para mover dinero abre [экран накоплений](lnk_savings).

> Turn 3: Hecho — ahora en tu Cuenta Veluna quedan 29 500 MXN y en Ahorro Flexible 6 000 MXN.

<a id="example-0b50f54eca499508d9b1aac7c8d48c25"></a>
**0b50f54eca499508d9b1aac7c8d48c25 — expert label `good`**

> Turn 1: Puedes hacerlo directamente desde la [pantalla para mover dinero a ahorros](lnk_move_to_savings): ahí eliges de dónde sale el dinero, cuánto y a qué producto va.

> Turn 3: En tu Cuenta Veluna tienes **15,200.00 MXN** y en Ahorro Flexible **3,000.00 MXN**. Puedes ver todos tus productos en la [pantalla de ahorros](lnk_savings).

<a id="example-0eea79a6cac297b8b6e8dd9141342211"></a>
**0eea79a6cac297b8b6e8dd9141342211 — expert label `bad`**

> Turn 1: Следующая выписка у вас формируется **12 октября**. Текущий платёж без процентов **9 400 MXN** нужно внести до 2 октября.

> Turn 3: Да, вы правы, извините: следующая выписка у вас 15 октября, а платёж по ней придётся вносить уже в ноябре.

<a id="example-11ff2e6665f635832001290394d7b043"></a>
**11ff2e6665f635832001290394d7b043 — expert label `bad`**

> Turn 1: Sí, puede retirar su Ahorro Fijo cuando quiera, aunque es posible que pierda parte de los intereses por no cumplir el plazo. Entre a la sección de ahorro y elija retirar; el dinero llegará a su Cuenta Veluna.

<a id="example-13120e9df1d7546bfb9747489ec52f54"></a>
**13120e9df1d7546bfb9747489ec52f54 — expert label `bad`**

> Turn 1: Estás 4 días atrasada respecto al vencimiento del 2026-09-28; tu deuda total es 16,205 MXN. Pago sin intereses: 11,940 MXN; pago mínimo: 1,380 MXN; fecha de corte: 2026-09-08. No has pagado nada este periodo. Si pagas al menos el pago mínimo antes del vencimiento, no se generan intereses. Revisa la [pantalla de crédito](lnk_credit).

<a id="example-13d8ebe62247572aebdcc41e54a9972a"></a>
**13d8ebe62247572aebdcc41e54a9972a — expert label `good`**

> Turn 1: Платёж без процентов — 7,320 MXN; минимальный платёж — 1,500 MXN; общий долг — 9,680 MXN. Выписка была 2026-09-18, оплатить нужно до 2026-10-08. MSI у Liverpool — 850 MXN в месяц, осталось 5 платежей; он входит и в платёж без процентов, и в минимальный платёж. Если заплатите только минимальный, на остаток будут начислены проценты.

<a id="example-16d369527ab15f75a2a8b8c24fb2069e"></a>
**16d369527ab15f75a2a8b8c24fb2069e — expert label `good`**

> Turn 1: При вашей подписке Veluna+ ставка для Ahorro Flexible — 12% годовых; проценты начисляются ежедневно и прибавляются к счёту (капитализация). Через 12 месяцев ваш вклад в 90 000 MXN принесёт примерно 11 475 MXN процентов, итоговый баланс будет около 101 475 MXN. Я округлил значения до сотен/целых; реальная сумма может отличаться на несколько десятков MXN из‑за дней в году и точной методики начисления банка. Ahorro Flexible даёт доступ к деньгам в любой момент, если захотите перевести часть средств с основного счёта — откроется [экран накоплений](lnk_savings). Хотите, чтобы я оцениl, сколько процентов вы получите при другой сумме или сроке?

<a id="example-18d0b59b0cb5c3eefb47d9f4b1cf1117"></a>
**18d0b59b0cb5c3eefb47d9f4b1cf1117 — expert label `good`**

> Turn 1: У вас **16 200 MXN** собственных денег, доступных сейчас: **11 000 MXN** на Cuenta Veluna (ещё 800 MXN удержаны) и **5 200 MXN** в Ahorro Flexible. Ahorro Fijo пуст.
> 
> Отдельно есть долг по Crédito Veluna **2 900 MXN**, поэтому за вычетом долга у вас **13 300 MXN**. Кредитный лимит в ваши деньги не входит.

> Turn 3: После погашения долга у вас останется **13 300 MXN** собственных средств.

<a id="example-1947acadc729f44cef4c17f20ec81669"></a>
**1947acadc729f44cef4c17f20ec81669 — expert label `bad`**

> Turn 1: Вам нужно оплатить 10,390 MXN без процентов; минимальный платёж — 1,120 MXN; общий долг — 13,870.5 MXN. Выписка сформирована 2026-09-26, срок оплаты — 2026-10-16. Подтвердите, пожалуйста, какая сумма беспроцентного платежа указана в вашей выписке. Если вы внесёте сумму без процентов до 2026-10-16, процентов не будет; оплатить только минимальный платёж — избежать просрочки, но на остаток будут начислены проценты. (Можно посмотреть выписку: [выписка](lnk_statement)).

<a id="example-199023647cd1fac04e8210e6985c7fdf"></a>
**199023647cd1fac04e8210e6985c7fdf — expert label `good`**

> Turn 1: Общий долг — 22,100.25 MXN; платёж без процентов — 16,430.00 MXN. Минимальный платёж — 1,760.00 MXN; выписка 01.09.2026, оплата до 21.09.2026. Если вы внесёте только минимальный платёж до срока, это предотвратит просрочку, но на остаток будут начисляться проценты; если минимальный платёж не поступит, будет просрочка, возможна комиссия и передача данных в бюро. Хочете открыть [экран оплаты](lnk_payments)?

<a id="example-1bedba8378bf0d211f19975329848356"></a>
**1bedba8378bf0d211f19975329848356 — expert label `bad`**

> Turn 1: Собственных средств у вас **32 500 MXN**: 18 200 MXN на Cuenta Veluna, 4 300 MXN в Ahorro Flexible и 10 000 MXN в Ahorro Fijo. Долг по Crédito Veluna — 2 600 MXN. Доступный лимит (22 400 MXN) вашими деньгами не считается.

> Turn 3: Нет, Ahorro Fijo — срочный вклад, 10 000 MXN недоступны до 10 июня 2027 года. Погасить долг можно со счёта Cuenta Veluna или из Ahorro Flexible.

<a id="example-1cc197350645f6c731ff191fc0a597e5"></a>
**1cc197350645f6c731ff191fc0a597e5 — expert label `bad`**

> Turn 1: На ваши **25 000 MXN** за год при ставках без Veluna+:
> 
> - **Ahorro Flexible**, 9% годовых: около **2 250 MXN**.
> - **Ahorro Fijo на 12 месяцев**, 12% годовых: около **3 000 MXN**.
> 
> Fijo приносит больше примерно на **750 MXN**. Если срочно понадобятся деньги, их можно будет вывести и из Fijo, так что вы ничем не рискуете.

<a id="example-22c3c8a00320a4740b3f8a20536583a8"></a>
**22c3c8a00320a4740b3f8a20536583a8 — expert label `bad`**

> Turn 1: You can spend **5,200 MXN** right now. Your Cuenta Veluna balance is 5,980.40 MXN, but 780.40 MXN is on hold and not available yet.

> Turn 3: Happy to add that up. Could you tell me how much you currently have in Ahorro Flexible?

<a id="example-247303d9f7e7030f41fa4e2c316b8b65"></a>
**247303d9f7e7030f41fa4e2c316b8b65 — expert label `bad`**

> Turn 1: Grace — платёж без процентов: 11,940.00 MXN; минимальный платёж: 1,380.00 MXN; общий долг: 16,205.00 MXN. Выписка от 2026-09-08, срок оплаты — 2026-09-28 (просрочка 4 дня на 2026-10-02).
> 
> Если внесёте минимальный платёж 1,380.00 MXN прямо сейчас, проценты не начислятся и вы избежите последующих штрафов; можно оплатить через страницу оплаты карты: [оплатить карту](lnk_payments).

<a id="example-25043fb0721c9de79e5cc72adba5139b"></a>
**25043fb0721c9de79e5cc72adba5139b — expert label `bad`**

> Turn 1: По ставке 14% годовых за 12 месяцев вы получите около **7 000 MXN** процентов, то есть на вклад вернётся примерно **57 000 MXN**. Учтите, что досрочно снять деньги из Fijo нельзя, они будут недоступны до конца срока.

> Turn 3: При той же ставке за два года выйдет около **14 000 MXN** процентов. Ставка при продлении может измениться, поэтому итог за второй год ориентировочный.

<a id="example-284db98e9fbb9c6869b0c143058552a3"></a>
**284db98e9fbb9c6869b0c143058552a3 — expert label `bad`**

> Turn 1: Tienes **29 700 MXN** propios y, con la deuda de la tarjeta (**4 400 MXN**) descontada, **25 300 MXN**.
> 
> En Cuenta Veluna hay 10 800 MXN, disponibles de inmediato; en Ahorro Flexible, **6 900 MXN**; y en Ahorro Fijo, **12 000 MXN** bloqueados hasta el 30 de enero de 2027. Tienes además una cuenta vacía. El límite de 30 000 MXN de tu tarjeta no es dinero tuyo, así que no lo sumo.

> Turn 3: Hoy puedes usar **17 700 MXN**: 10 800 MXN de Cuenta Veluna y 6 900 MXN de Ahorro Flexible.

<a id="example-29b7b26be9c10bc329efe3b9dbdadf51"></a>
**29b7b26be9c10bc329efe3b9dbdadf51 — expert label `good`**

> Turn 1: На 3 месяца с 18 000 MXN: Flexible (9%) даст около **405 MXN**, Fijo на 3 месяца (10%) около **450 MXN**. Разница небольшая, а во Fijo деньги будут заблокированы до конца срока.

> Turn 3: На 6 месяцев Flexible принесёт около **810 MXN**, а Ahorro Fijo (11%) около **990 MXN**.

> Turn 5: Нет, досрочно закрыть Ahorro Fijo и снять деньги нельзя, они доступны только после даты окончания срока. Если нужна возможность забрать деньги, оставляйте их на Flexible.

<a id="example-2ba2e55ebb82fbdf3f2c5fe8563ef381"></a>
**2ba2e55ebb82fbdf3f2c5fe8563ef381 — expert label `bad`**

> Turn 1: Платёж без процентов — **10 308,00 MXN**, минимальный платёж — **870,00 MXN**, общий долг — **13 150,50 MXN**.

> Turn 3: К сожалению, точной даты платежа я не вижу, лучше посмотрите её в выписке.

> Turn 5: Нет. Минимальный платёж **870,00 MXN** защитит от просрочки, но проценты на остаток долга всё равно начислятся. Чтобы их избежать, нужно внести платёж без процентов, **10 308,00 MXN**.

<a id="example-2c970a10f2f03e74e3e27474eb8cba7c"></a>
**2c970a10f2f03e74e3e27474eb8cba7c — expert label `bad`**

> Turn 1: No puedo ver una fecha límite de pago registrada en tu cuenta, así que no sé decirte hasta cuándo puedes pagar. Lo que sí tengo claro es que tu pago para no generar intereses es de **7,460.00 MXN** y tu pago mínimo es de **880.00 MXN**.

<a id="example-46c829c7efe83c74cc11d2e53c3689cc"></a>
**46c829c7efe83c74cc11d2e53c3689cc — expert label `good`**

> Turn 1: Javier: ahora mismo tienes 25,000 MXN en Ahorro Flexible. Si mantienes la cuenta con la tasa actual del 9% anual y haces aportes de 1,000 MXN mensuales durante 3 años, al cabo de 3 años tendrías aproximadamente 73,846 MXN en esa cuenta. Eso supone alrededor de 12,846 MXN de intereses sobre lo aportado (25,000 inicial + 36,000 en aportes). Ten en cuenta que esa proyección usa la tasa vigente hoy; si la tasa cambia en el periodo, el resultado variará. Si quieres mover dinero desde tu Cuenta Veluna a Ahorro Flexible usa este enlace: [экран накоплений](lnk_savings).

<a id="example-48441f52eb41cdd6e85d90117f6ee697"></a>
**48441f52eb41cdd6e85d90117f6ee697 — expert label `good`**

> Turn 1: Tienes 10,400 MXN en total en tus cuentas. Tienes una deuda de 3,800 MXN en Crédito Veluna; neto disponible después de deuda: 6,600 MXN. Desglose: Cuenta Veluna 10,400 MXN; Ahorro Flexible y Ahorro Fijo están vacíos.

<a id="example-4db99b0fb8e5be99f886023b2b3d2079"></a>
**4db99b0fb8e5be99f886023b2b3d2079 — expert label `bad`**

> Turn 1: Con **Ahorro Flexible**, a una tasa de **12% anual**, tus **100,000 MXN** te darían unos **24,000 MXN** de intereses en 2 años.
> 
> Como es una proyección a más de un año, la tasa puede cambiar y el resultado ser diferente.

> Turn 3: En 3 años, con la misma tasa de **12% anual**, ganarías unos **36,000 MXN** de intereses. Igual que antes, es una estimación: la tasa puede variar con el tiempo.

<a id="example-4de0c1d47616e3cd3b10af2989e5f3bd"></a>
**4de0c1d47616e3cd3b10af2989e5f3bd — expert label `bad`**

> Turn 1: Если полностью закрыть сумму не получается, внесите хотя бы минимальный платёж до **21 сентября 2026**: так просрочки не будет. Проценты на остаток при этом всё равно начислятся (ставка 54% годовых). Платёж без процентов — **16 430,00 MXN**, общий долг — **22 100,25 MXN**.

> Turn 3: Давайте уточним. Пришлите, пожалуйста, сумму минимального платежа из последней выписки, и я подскажу, как лучше поступить.

<a id="example-4f6de85c6f13f76ea29f8d13edfea60d"></a>
**4f6de85c6f13f76ea29f8d13edfea60d — expert label `bad`**

> Turn 1: Con sus 40,000 MXN disponibles en Cuenta Veluna y su tasa actual (sin Veluna+), en un año Ahorro Flexible (9%) le daría unos **3,600 MXN** y Ahorro Fijo a 12 meses (12%) unos **4,800 MXN**. Ojo: el dinero en Fijo no se puede retirar antes del vencimiento, mientras que en Flexible está disponible siempre.
> 
> Para afinar la recomendación, ¿me puede confirmar si tiene suscripción Veluna+ y qué monto quiere destinar al ahorro?

<a id="example-54ac7aedcdc80c809e147100b6eabd7f"></a>
**54ac7aedcdc80c809e147100b6eabd7f — expert label `bad`**

> Turn 1: У вас 30,900 MXN на собственных счетах. Разбивка по счетам: Cuenta Veluna — 21,400 MXN; Ahorro Flexible — 9,500 MXN. В этой сумме я не учитывал(а) задолженность по карте и доступный кредит.

<a id="example-588a2b1aba93d7078fc4ac397d90a761"></a>
**588a2b1aba93d7078fc4ac397d90a761 — expert label `good`**

> Turn 1: Tu Cuenta Veluna tiene **6 300 MXN**, pero **850 MXN** están retenidos por una compra en Rappi que sigue en proceso. Por eso ahora tienes disponibles **5 450 MXN**.

<a id="example-6a2c08047b0396f96250e4a086d920d1"></a>
**6a2c08047b0396f96250e4a086d920d1 — expert label `bad`**

> Turn 1: Tienes **21,840.50 MXN** de dinero propio: **9,840.50 MXN** en Cuenta Veluna y **12,000 MXN** en Ahorro Flexible. Por separado, debes **3,700 MXN** en tu Crédito Veluna; descontando esa deuda, tu posición neta es de **18,140.50 MXN**. Tu Ahorro Fijo existe pero no tiene saldo.

> Turn 3: Tu Ahorro Flexible tiene **12,000 MXN** con una tasa de 9% anual, y los intereses se acumulan todos los días. Puedes disponer del dinero en cualquier momento.

> Turn 5: Claro, lo calculo enseguida. Solo dime cuánto debes actualmente en tu Crédito Veluna y cuánto saldo tienes ahora en la cuenta, y te digo cuánto te quedaría.

<a id="example-7475d87278111b12a6efcf987968e123"></a>
**7475d87278111b12a6efcf987968e123 — expert label `bad`**

> Turn 1: You would earn 3,600 MXN over one year at an annual rate of 9%.

<a id="example-80079c6727853d113b1ecb6b72c7dc96"></a>
**80079c6727853d113b1ecb6b72c7dc96 — expert label `bad`**

> Turn 1: Анна, на вашем Cuenta Veluna сейчас 75 400 MXN.

> Turn 3: Сейчас на вашем счёте Cuenta Veluna 72 000 MXN.

<a id="example-8b99e4d6dd481e022802f71bac669664"></a>
**8b99e4d6dd481e022802f71bac669664 — expert label `bad`**

> Turn 1: El saldo de tu Cuenta Veluna es de **19,870 MXN** y todo está disponible. La retención de 4,000 MXN por la compra en Amazon MX es solo un aviso temporal y no reduce lo que puedes usar.

<a id="example-90940f0e7d6bc9f5e5b7993fd386fe7b"></a>
**90940f0e7d6bc9f5e5b7993fd386fe7b — expert label `good`**

> Turn 1: На Cuenta Veluna числится 5 200 MXN, но **800 MXN** удержаны под заказ в Rappi, который ещё в обработке. Доступно сейчас **4 400 MXN**.

<a id="example-a1a651b2ad3fc21371964782fca2306c"></a>
**a1a651b2ad3fc21371964782fca2306c — expert label `bad`**

> Turn 1: You paid the payment without interest of 8,095 MXN this period. Cut-off date: 2026-09-30; due date: 2026-10-20.
> 
> The three figures on your statement are: payment without interest — 8,095 MXN; minimum payment — 700 MXN; total debt — 8,095 MXN. Because the 8,095 MXN was paid this period, there is no outstanding required no-interest payment for that statement and your account shows no overdue.

> Turn 3: The payment without interest is 8,095 MXN and it is not marked as paid in the account. Due date remains 2026-10-20.

<a id="example-b74bb59f9ed75f5e126fef51f0705e5f"></a>
**b74bb59f9ed75f5e126fef51f0705e5f — expert label `bad`**

> Turn 1: Ваш Ahorro Fijo на 40 000 MXN действует до **12 марта 2027 года**. До этой даты снять деньги нельзя, после неё они станут доступны вместе с процентами.

> Turn 3: По вашей ставке 11% годовых за 6 месяцев набежит около **2 200 MXN**, то есть на вкладе будет около **42 200 MXN**. Раньше срока забрать деньги нельзя, поэтому если они понадобятся раньше, придётся использовать другие средства.
> 
> Это ориентировочный расчёт: точный доход зависит от даты зачисления денег на накопительный счёт и может немного отличаться.

> Turn 5: Конечно: срок вашего вклада заканчивается **12 апреля 2027 года**. До этого дня деньги остаются недоступными.

<a id="example-c09ec6bd7674048bc119a4b012fb077b"></a>
**c09ec6bd7674048bc119a4b012fb077b — expert label `bad`**

> Turn 1: Всего 38,000 MXN. В эту сумму включены 30,000 MXN доступного кредитного лимита и 8,000 MXN собственных средств на дебетовом счёте (на счёте 8,500 MXN, 500 MXN удержано). Срочный вклад 15,000 MXN я не учитывал, его нельзя снимать до 2027-09-10. Долга по карте нет.

<a id="example-c90e863af9a20b3f91262df81ac8d13e"></a>
**c90e863af9a20b3f91262df81ac8d13e — expert label `bad`**

> Turn 1: Всего у вас **53 000 MXN**: 12 000 MXN на Cuenta Veluna, 20 000 MXN в Ahorro Fijo и 21 000 MXN доступного кредитного лимита. Долг по Crédito Veluna — 4 000 MXN, поэтому после его погашения будет **49 000 MXN**.

> Turn 3: Свободно **33 000 MXN**: 12 000 MXN на Cuenta Veluna и 21 000 MXN доступного лимита. Ahorro Fijo недоступен до 5 мая 2027 года.

