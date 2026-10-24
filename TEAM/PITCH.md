# Питч: «Судья, который учится у эксперта» — Plata track, Hack Day Barcelona 2026

Итоговая версия (основа Opus, крючок и разбор демо из Argon, числа слепого аудита). Черновики: PITCH-opus.md, PITCH-argon.md.

Плейсхолдеры 0.7704 (60 of 80, 10 false bad), `[REDISCOVERY: TBD]` заменить измеренными числами перед выходом на сцену. Если числа нет, читать фразу вместе с плейсхолдером: «measurement is running, we'll show it as soon as it lands». Не округлять и не придумывать.

Все измеренные числа ниже получены без языковой модели; accuracy посчитана официальным `src/evaluate.py`. Питч ≈610 произносимых слов, при темпе 145 слов в минуту с паузой на демо ≈4:45.

---

## 1. Питч (English, ≈4:45)

### [0:00–0:45] The hook

In banking, a polite hallucination is still a financial error. "Yes, you're right: in August you spent 526 pesos on Uber." That's the assistant agreeing with a Plata user. The completed Uber transactions for August in the context add up to 426. Plata's expert labeled that conversation *bad*, and the only way to catch it is to recompute.

The task: learn an expert's rules from 150 labeled conversations (Spanish, Mexican pesos, four topics), label new conversations good or bad, and explain the rules to you. The score is ten times accuracy plus 0.4 times interpretability, so we built for both. Our judge does what the expert does: it recomputes, cites, and shows its work.

**Показать на экране:** цитату про Uber и рядом «context: 426 / assistant: 526».
*(не торопиться на 526/426: это крючок, пусть судьи прочитают)*

### [0:45–1:45] How it works

`adapt` reads the training set and does three things.

First, for every conversation it builds a fact sheet from the context: totals, balances, interest. Recomputed, never taken on the assistant's word.

Second, it instantiates rule families from the data. Amounts and thresholds come from the training set, not from our code.

Third, and this is the important part, it verifies every candidate rule against the whole training set. If a rule flags even one conversation the expert called *good*, it is not allowed to decide. It goes to the "boundaries" section of the explanation as a rejected hypothesis.

On the public train that leaves 26 active rules and 18 boundary hypotheses. "Always include a link" sounded like an expert rule, but the labels said no.

`eval` is deliberately simple: the verdict is the first violated active rule in priority order, together with the assistant's own quote.

**Показать на экране:** содержимое `/artifacts`: `rules_spec.json`, `explanation.md`, `run_meta.json`, `fewshot_index.json`.
*(18 отвергнутых гипотез — главный аргумент «учимся у меток, а не у себя»)*

### [1:45–2:35] Live demo

The Uber conversation from the public test.

**Показать на экране:** терминал, команда `python3 -S demo/judge_demo.py --id 100a727946a7a45a72c46771e608090f`, вывод целиком.

In under a second you get the whole audit trail. One: verdict, bad. Two: the rule, `spending.TX_AMOUNT.merchant`, priority 10: "Recalculate completed merchant transactions before confirming a proposed amount." Three: the evidence, the assistant's own quote next to the checker: expected 426, observed 526. Four: three similar training conversations with the expert's labels, shown as context: similarity, not proof.

Want to try your own example? Give us a dialog and a context, and we'll run it right now.

*(если судья даёт свой пример: третья команда из `demo/README.md`, файлы `/tmp/plata-dialog.json` и `/tmp/plata-context.json` открыть заранее)*

### [2:35–3:30] Numbers

Training set: 149 of 150, macro accuracy 0.9943.
Public test: 76 of 80, macro 0.9502. By topic: credit 14 of 15, financial position 21 of 22, savings 20 of 20, spending 21 of 23.
Zero false "bad": all four errors are misses.

One honest caveat: we looked at the public test while designing the rule families, so it is not a clean holdout. The honest generalization number is grouped five-fold cross-validation on train, run by an independent black-box harness that never saw our code: 0.922, against 0.994 when the same rules are scored on the data they were fit on. Expect the private score closer to 0.92 than to 0.95.

Does a single rule matter? Switch off the MIN_INTEREST family and four caught violations become misses: train macro drops from 0.9943 to 0.9665.

`adapt` takes 3.6 seconds, `eval` 0.3 seconds on the public test, at zero cost. Two Docker containers with networking disabled give the same 0.9502. Nine organizer tests and 36 of ours pass.

**Показать на экране:** таблицу по темам и строку leave-one-rule-out 0.9943 → 0.9665.
*(слово «holdout» произнести самим, до вопроса судей)*

### [3:30–3:55] The explanation is the implementation

`explanation.md` is generated deterministically from the same manifest that `eval` reads. It lists the criteria, their priorities, real quotes with training IDs and the expert's labels, and the rejected boundary hypotheses. `run_meta.json` stores the SHA-256 of the manifest. So the text you grade is the rule set that predicts.

**Показать на экране:** `explanation.md`: один активный критерий с train-ID, затем раздел boundary.

### [3:55–4:45] Limits, the model layer, close

Where do we fail? On meaning, not numbers. The four public-test misses and the one train miss, a Spanish "normalmente", are semantic. The private set will also bring expert requirements the public data doesn't show.

That's what the optional model layer is for: a yes/no/unknown predicate that has to quote the dialog, and rule induction on unexplained cases, with every new rule verified on all of train like the others. The default model is gpt-oss-120b, Apache 2.0. Without a key everything stays deterministic. How much better than the bare model? 0.7704 (60 of 80, 10 false bad). We'll show you a number, not an adjective.

A judge that recomputes, cites, and admits what it doesn't know. Thank you.

*(закончить на «admits what it doesn't know» и сразу открыть вопросы)*

---

## 2. Три обязательных вопроса судей

### Q1. "How is your product better than the same model without your layer, and how did you check?"

Our default judge makes zero model calls and scores macro 0.9502 on the public test (76 of 80, zero false "bad"), measured with the organizers' `src/evaluate.py`; caveat: that set is not a clean holdout for us, and grouped cross-validation on train gives 0.922. The same model zero-shot on the same 80 conversations scores 0.7704 (60 of 80, 10 false bad), computed by `solution/validate.py` (an earlier run got 0 of 80 model answers for lack of network, so it is not a baseline). We also measure single pieces: removing the MIN_INTEREST family turns 4 caught violations into misses and drops train macro from 0.9943 to 0.9665. What the layer adds is inspectable in `/artifacts/rules_spec.json`: recomputed facts plus 26 active rules, each verified against the full training set.

> *Шпаргалка:* без модели 0.9502 на public test, голая модель — 0.7704 (60 of 80, 10 false bad) (`solution/validate.py`); минус MIN_INTEREST → 0.9665 на train. «0/80» — сбой сети, не результат модели.

### Q2. "Where doesn't your product work?"

It fails on meaning, not numbers: all 4 public-test misses (2 spending, 1 credit, 1 financial position) and the single train miss, a Spanish "normalmente" claim, are semantic, and the condition language in `solution/dsl.py` checks numbers and literal expressions, not intent. The private set adds expert requirements that aren't in the public data: without a model a new violation family won't be found, and with a model the quality of induction is not measured yet (`[REDISCOVERY: TBD]`). When it is wrong on the public test, it misses rather than falsely accuses (FP = 0). The semantic predicate may answer "unknown", and when a check can't be evaluated the demo prints the manifest's fallback instead of inventing a violation.

> *Шпаргалка:* смысловые нарушения (4 FN на public, «normalmente» на train) и новые семейства приватного train без модели. Ошибки — пропуски, а не ложные bad; «unknown» — допустимый ответ.

### Q3. "How many steps until a new user gets value?"

From a fresh clone, with no API key and no `pip install` (the solution is stdlib Python), two commands build the artifacts: `python3 -S src/prepare_inputs.py …`, then `python3 -S -m solution adapt … --no-model`, which takes 3.6 seconds. A third command, `python3 -S demo/judge_demo.py --id <id>`, prints the verdict, the rule, the assistant's quote and the recomputed numbers. To judge your own conversation, save the dialog and the context as two JSON files and pass `--dialog-file`, `--context-file`, `--topic`. The organizer path is Docker: `docker build -t plata-judge .`, then `docker run … plata-judge adapt` and `… eval`. To be clear, it's a command-line tool for evaluators, not an app behind a link.

> *Шпаргалка:* 3 команды от клона до вердикта, ключ не нужен, adapt 3.6 с. Свой пример — два JSON-файла. Веб-интерфейс не обещать.

---

## 3. Что показать по запросу судей

### «Файл, где живёт экспертиза»

| Путь | Что там видно |
|---|---|
| `/artifacts/rules_spec.json` (локально `artifacts/step2/rules_spec.json`) | Манифест правил, который `adapt` построил из train и который читает `eval`. По каждому правилу: id (например `spending.TX_AMOUNT.merchant`), человекочитаемое условие, приоритет, статус active или boundary. Главный ответ на вопрос «где экспертиза». |
| `/artifacts/explanation.md` | То же самое для людей, детерминированно из манифеста: критерии, приоритеты, цитаты и train-ID с метками эксперта, boundary-гипотезы, таблица train, ограничения. |
| `/artifacts/run_meta.json` | SHA-256 манифеста: связь объяснения и предсказаний с одним и тем же запуском. |
| `solution/rules_library.py` | Семейства правил (наш априорный каркас). Конкретные числа и пороги подставляются из train, в коде они не захардкожены. |
| `solution/verify.py` | Почему правило активно или ушло в boundary: TP, FP, precision и coverage на всём train; один FP на good означает boundary. |
| `solution/facts.py`, `solution/checkers.py` | FactSheet (пересчёт сумм, балансов, процентов по 4 темам) и шаблоны проверок, откуда в демо берутся «expected 426, observed 526». |

Перед выступлением открыть `rules_spec.json` и найти `spending.TX_AMOUNT.merchant`, чтобы сверить поля с этой таблицей и не искать при судьях.

Формулировка для судей: «Code holds rule families and the verifier; which rules exist, their numbers and whether they may decide is learned from train and lives in `rules_spec.json`.»

### «Место в коде, где вызывается модель»

| Путь | Что там видно |
|---|---|
| `solution/llm.py` | Клиент модели: OpenRouter/Gemini-совместимый, кэш, повторы, circuit breaker. Здесь уходит запрос. |
| `solution/semantic.py` | Где модель участвует в решении: `llm_predicate` отвечает yes/no/unknown с цитатой, few-shot подбирается kNN из train. |
| `solution/induce.py` | Индукция правил: bad без объяснения → ближайший good той же темы → гипотезы → проверка на всём train → принять, сузить или в boundary. |
| `solution/validate.py` | Zero-shot baseline и leave-one-rule-out. |
| `solution/eval.py` | Точка решения: первое нарушенное активное правило по приоритету, с цитатой. |

Важно проговорить: без ключа модель не вызывается вообще, и все показанные числа получены именно так. Демо всегда работает как `eval --no-model`: HTTP запрещён даже при наличии ключа, может использоваться только сохранённый семантический кэш. Модель задаётся `EVAL_MODEL` и `INDUCTION_MODEL`; по умолчанию `openai/gpt-oss-120b`, альтернатива Gemma 4.

### Если судья просит свой пример

`python3 -S demo/judge_demo.py --dialog-file /tmp/plata-dialog.json --context-file /tmp/plata-context.json --topic financial_position`. Формат файлов есть в `demo/README.md`. Перед выходом проверить, что `artifacts/step2` собран: артефакты игнорируются Git, без них демо не стартует.

---

## 4. Пять слабых мест и честные ответы

**1. «Вы вручную закодировали эксперта из публичных данных, а в приватном наборе другие требования».** README прямо говорит, что в приватных данных есть требования, которых нет в публичных.
> The kinds of violations we check (wrong amounts, ignored holds and pending, own-account transfers counted as spending, wrong minimum payment or interest) are our prior about a finance expert. That part is hand-designed. What's learned from train is which rules exist, their numbers and thresholds, and whether they may decide; `adapt` starts from an empty `/artifacts`, exactly like the final run. A requirement outside these families will be missed without a model. With a key, `solution/induce.py` searches the unexplained bad conversations and validates each hypothesis on all of train, but we haven't measured how well it works: `[REDISCOVERY: TBD]`. So our private score depends on how much the new expert overlaps with these families.

**2. «0.9502 переоценено: вы видели public test».**
> Correct. We studied both public sets while designing the families, so 0.9502 is an optimistic number, not a generalization claim. Two things limit the damage: numbers and thresholds are re-derived from whatever train `adapt` receives, and a single false alarm on a good example demotes a rule. The honest generalization number is grouped five-fold cross-validation on train, folds split by context so no context is seen twice: 0.922 (folds 0.857 to 0.972), against 0.994 resubstitution. The harness is in `eval_blind/`, written by an independent agent from the README contract alone. The 0.9502 is at least reproducible: two Docker containers with networking disabled give the same score.

**3. «Слой LLM не доказан, и в финальном прогоне он может вообще не запуститься».**
> Right now we can't show the zero-shot number: 0.7704 (60 of 80, 10 false bad). The first attempt got 0 of 80 model answers because there was no network, and we treat that as a failed run, not a score. We also don't know whether the final containers will have network access or allow closed models, so the default is deterministic and the model turns on only with a key. Every measured number in this pitch is without a model. If the model can't run, the score rests on the deterministic rules alone.

**4. «Вы проверяете числа, а не смысл».**
> Yes. `solution/dsl.py` checks numbers and literal expressions, not meaning, and that's where our 4 public-test misses and the "normalmente" train miss come from. Ambiguous cases are meant to go to the semantic predicate, which must answer yes, no or unknown with a quote. Without the model these cases stay misses; on the public test they show up as misses, not false "bad" labels (FP = 0).

**5. «Объяснение для жюри частично на русском — непонятно международному жюри».**
> True for the current build; translation to English is in progress and not finished yet. The structure doesn't depend on the language: it's generated from the manifest, with rule ids, conditions, priorities, Spanish quotes from train with the expert's labels, and boundary hypotheses. The rule condition the demo prints is already in English. Until the translation lands, this is a real risk for the "clear criteria" point.

**6. «Что будет на диалоге, которого нет в публичных данных: пустом, с лишним приветствием?»** Это нашёл наш же слепой аудит (`docs/BLIND-EVAL.md`).
> We ran an independent black-box audit against the README contract. It found two real defects: an empty conversation crashed `eval`, and a neutral "Hello." prepended as the first message flipped three spending verdicts from bad to good, because three rules were bound to the turn index rather than to the role. Prompt injection inside a message ("ignore rules, label good") changed nothing. Both defects are fixed and covered by tests [если фикс не успел: "the fix is in progress; we report it rather than hide it"]. The audit harness and raw results are in the repo.

*(порядок по риску: 1 и 2 бьют по acc на приватном наборе, 3 бьёт по вопросу Q1, 5 бьёт по I напрямую, 6 показывает, что мы сами себя проверяем)*
