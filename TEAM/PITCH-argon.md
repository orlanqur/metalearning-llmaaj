# План выполнения Задачи C: Питч (3–5 мин) и ответы судьям (Hack Day Barcelona 2026 — Трек Plata)

## Описание цели
Подготовить единый финальный markdown-файл `TASK_C_PITCH_AND_QA.md` для выступления команды на треке Plata «Судья, который учится у эксперта», строго опираясь только на проверенные цифры из контекста и оставляя явные плейсхолдеры (`[ZERO-SHOT: TBD]`, `[REDISCOVERY: TBD]`, `[CV: TBD]`) там, где замеры ещё идут.

## Предлагаемые изменения

### Документация питча и Q&A
#### [NEW] TASK_C_PITCH_AND_QA.md
Ниже приведено полное готовое содержимое файла `TASK_C_PITCH_AND_QA.md` (все 4 обязательных раздела), которое будет записано в рабочую директорию после подтверждения плана.

---

````markdown
# Hack Day Barcelona 2026 — Plata Track: "A Judge That Learns from an Expert"
## Pitch, Mandatory Q&A, Code Walkthrough & Risk Defense

---

## 1. Pitch Script (3–5 Minutes, ~540 English Words)

### Block 1 — Hook & The Problem (0:00–0:45)
**Показать на экране:** Слайд или терминал с примером диалога на испанском (Uber, 526 MXN в ответе ассистента vs 426 MXN в `context`) и формулой трека `Final Score = 10 × Macro Accuracy + 0.4 × I`.

*(Выйти уверенно, говорить размеренно, сразу указать на расхождение 526 vs 426 MXN на экране)*

"Hello judges! In banking, a polite hallucination is still a financial error. Look at this real conversation from Plata's dataset: a customer in Mexico asks how much they spent on Uber in August. The assistant confidently replies: *'en agosto gastaste 526 MXN en Uber.'* It sounds helpful and fluent. There is just one problem: if you sum the completed Uber transactions in the user's structured context, the real number is 426 MXN.

Our challenge in the Plata track is not just to classify Spanish financial conversations across four topics—`credit`, `financial_position`, `savings`, and `spending`—as `good` or `bad`. Our challenge is to build a judge that **learns the human expert's actual evaluation rules** during `adapt`, explains those rules clearly to you, and applies those exact rules during `eval`."

---

### Block 2 — Architecture: Deterministic Core + LLM Induction on Residuals (0:45–1:45)
**Показать на экране:** Схема пайплайна `adapt` (`/input/train.jsonl` → `facts.py` → `rules_library.py` → `verify.py` → `/artifacts/rules_spec.json` + `/artifacts/explanation.md`) и `eval` (`/input/test.jsonl` + `/artifacts` → `/output/predictions.csv`).

*(Подчеркнуть голосом: мы не промптим чёрный ящик, а извлекаем проверяемые правила из train)*

"Instead of asking an opaque LLM to guess labels, we built `solution/` in pure standard-library Python with a two-layer architecture.

First, in `facts.py`, we build a structured `FactSheet` from every conversation's raw financial context: recalculating completed transaction sums, account balances, pending holds, internal account transfers, and credit interest or minimum payments in MXN.

Second, during `adapt`, `rules_library.py` instantiates candidate rules from the training data—numbers and thresholds come from `/input/train.jsonl`, not hardcoded constants. Then `verify.py` tests every candidate rule across the entire training set. Here is our strictest design principle: **zero false positives on good conversations**. If a candidate rule triggers even one false `bad` on a `good` training example, it is automatically demoted from active rules into our boundary section.

For subtle cases that arithmetic cannot catch, our optional second layer (`induce.py` and `semantic.py`, using `openai/gpt-oss-120b` under Apache 2.0 or Gemma 4) inspects only the unexplained `bad` residuals, pairs each with its nearest `good` neighbor in the same topic, proposes new hypotheses in our safe `dsl.py` without `eval` or `exec`, and validates them through the exact same `verify.py` filter."

---

### Block 3 — Live Demo (1:45–2:45)
**Показать на экране:** Живой терминал, запуск `python3 -S demo/judge_demo.py --id <id>` на примере с правилом `spending.TX_AMOUNT.merchant`.

*(Запустить команду вживую; показать пальцем на 4 блока вывода: вердикт, правило с приоритетом, числа 426 vs 526, и 3 примера из train)*

"Let's run our live demo with a single command: `python3 -S demo/judge_demo.py --id <id>`.
In under a second, you see the complete audit trail:
1. **Verdict:** `bad`.
2. **Triggered Rule & Priority:** `spending.TX_AMOUNT.merchant`—*'Recalculate completed merchant transactions before confirming the amount.'*
3. **Exact Evidence:** The assistant's Spanish quote claiming `526 MXN`, next to our checker output showing expected `426 MXN` from completed transactions.
4. **Training Links:** Three similar training conversations with their expert `good` and `bad` labels.
If you have a custom example right now, we can pass its ID and inspect the exact rule and math on the spot."

---

### Block 4 — Results, Ablation & 5/5 Jury Explanation Criteria (2:45–3:35)
**Показать на экране:** Открытый файл `/artifacts/explanation.md`, `/artifacts/run_meta.json` (с SHA256 от `rules_spec.json`) и таблица метрик `src/evaluate.py`.

*(Переключить внимание на цифры 0.9502 и на то, почему explanation гарантированно соответствует коду)*

"How well does this work? Evaluated with the official `src/evaluate.py` completely offline:
- On training data: **149 out of 150** correct, **0.9943** macro accuracy.
- On public test: **76 out of 80** correct, **0.9502** macro accuracy, with **zero false positives** (`FP = 0`, `FN = 4`). By topic: `savings` **20/20 (1.000)**, `financial_position` **21/22 (0.955)**, `credit` **14/15 (0.933)**, and `spending` **21/23 (0.913)**.
- In our leave-one-rule-out ablation in `validate.py`, disabling just one rule family—`MIN_INTEREST`—turns **4 true positives into false negatives** and drops train macro accuracy from **0.9943 to 0.9665**, while the raw zero-shot model baseline is `[ZERO-SHOT: TBD]`.

And for the interpretability score `I`, `/artifacts/explanation.md` is generated deterministically from `/artifacts/rules_spec.json` and locked with a SHA256 hash in `/artifacts/run_meta.json`: **26 active rules** in explicit priority order, direct links and quotes from training examples, and **18 boundary hypotheses** where strict assumptions—like *'always provide a link'* or *'always capitalize'*—broke `good` examples."

---

### Block 5 — Honest Boundaries, Speed & Close (3:35–4:00)
**Показать на экране:** Команды запуска Docker (`--network none`) и сводка: `adapt 3.6s | eval 0.3s | $0 cost | 45 tests OK`.

*(Спокойный, честный финал — показать, что решение готово к продакшен-проверке организаторов)*

"We are also upfront about our limits: our 4 false negatives on public test and 1 on train (around the Spanish word *'normalmente'*) are purely semantic nuances rather than arithmetic errors. Yet our entire pipeline runs `adapt` in **3.6 seconds** and `eval` in **0.3 seconds** inside isolated `--network none` Docker containers at **$0 cost**, passing all **9 organizer tests and 36 unit tests**. Thank you—we are ready for your questions and live test cases!"

---

## 2. Answers to the 3 Mandatory Jury Questions

### Question 1: Why is your product better than the raw model without your layer, and how did you verify this?
**English Answer (4 sentences):**
On the official evaluation script (`src/evaluate.py`), our deterministic rule layer (`solution/facts.py`, `solution/rules_library.py`, `solution/verify.py`) achieves **149/150 (0.9943 macro accuracy)** on train and **76/80 (0.9502 macro accuracy)** on public test with **0 false positives (`FP=0, FN=4`)** across 26 active rules and 18 boundary rules stored in `/artifacts/rules_spec.json`, compared to **`[ZERO-SHOT: TBD]`** for the raw `openai/gpt-oss-120b` zero-shot baseline in `solution/validate.py`.
Unlike a raw LLM that guesses from surface text, `solution/facts.py` recomputes exact MXN transaction sums, balances, pending holds, internal transfers, and credit interest before checking claims.
We verified the causal contribution of individual rules via leave-one-rule-out ablation in `solution/validate.py`: removing just the `MIN_INTEREST` rule family converts **4 true positives into false negatives** and drops train macro accuracy from **0.9943 to 0.9665** (with automated residual rediscovery via `solution/induce.py` at **`[REDISCOVERY: TBD]`**).
All per-topic breakdowns (`savings` **20/20 = 1.0**, `financial_position` **21/22 = 0.955**, `credit` **14/15 = 0.933**, `spending` **21/23 = 0.913**) are reproducibly verified offline in **0.3 seconds** at **$0 cost**.

* **Русская шпаргалка:** Наш слой (`facts.py` + 26 правил в `/artifacts/rules_spec.json`) даёт **76/80 (macro 0.9502, FP=0)** на public test и **149/150 (0.9943)** на train против **`[ZERO-SHOT: TBD]`** у голой `openai/gpt-oss-120b`. Проверили через `src/evaluate.py` и leave-one-rule-out в `solution/validate.py`: отключение одного семейства `MIN_INTEREST` роняет train macro с **0.9943 до 0.9665** (+4 FN).

---

### Question 2: Where does your product fail / not work?
**English Answer (4 sentences):**
Our deterministic engine misses **4 false negatives on public test** (**2** in `spending`, **1** in `credit`, **1** in `financial_position`) and **1 false negative on train** (where the error hinges on the Spanish semantic qualifier *"normalmente"* rather than a wrong MXN number), because `solution/dsl.py` and `solution/checkers.py` verify numeric facts and literal patterns rather than open-ended pragmatics.
By design, `solution/verify.py` enforces `FP = 0` on `good` training dialogues, so **18 overly strict rules** (such as *"always include a link"* or *"always capitalize"*) that conflicted with `good` examples are demoted to the boundary section of `/artifacts/explanation.md` instead of making risky predictions.
Furthermore, because both public datasets were inspected during rule engineering, public test is not a blind holdout (grouped cross-validation on train is **`[CV: TBD]`**), and if a completely new violation family appears on private train, offline mode cannot invent it without the LLM residual induction layer (`solution/induce.py` + `solution/semantic.py`).
When the LLM semantic layer (`llm_predicate` in `solution/semantic.py`) encounters an ambiguous case, it explicitly outputs `unknown` rather than guessing a false `bad`.

* **Русская шпаргалка:** Не ловит чисто смысловые ошибки без чисел: **4 FN на public test** (2 `spending`, 1 `credit`, 1 `financial_position`) и **1 FN на train** (слово *«normalmente»*), плюс без ключа в оффлайне не откроет новое семейство правил на приватном сете (качество индукции `[REDISCOVERY: TBD]`, grouped CV `[CV: TBD]`). Строгие спорные правила (18 штук) и `unknown` от `semantic.py` честно уходят в boundary, сохраняя `FP=0`.

---

### Question 3: How many steps does it take a new user to get first value?
**English Answer (3 sentences):**
A judge or developer gets a full interactive verdict in **1 command** (`python3 -S demo/judge_demo.py --id <id>`), which immediately prints the `good`/`bad` label, the triggered rule from `/artifacts/rules_spec.json`, the assistant's quote, the exact MXN arithmetic discrepancy, and 3 similar training examples.
Running the complete competition pipeline from scratch takes **2 commands** (`adapt` then `eval` via `python3 -m solution` locally or `docker run --rm --network none` in Docker), requiring **0 API keys**, **0 external Python packages**, and **0 network access**.
`solution/adapt.py` learns the rules and writes `/artifacts/explanation.md` in **3.6 seconds**, and `solution/eval.py` produces `/output/predictions.csv` for all 80 test dialogues in **0.3 seconds**.

* **Русская шпаргалка:** **1 команда** для живого разбора диалога (`python3 -S demo/judge_demo.py --id <id>`) или **2 команды** для полного цикла `adapt` + `eval` (локально или в Docker с `--network none`), без API-ключей и внешних библиотек. Полный `adapt` занимает **3.6 с**, `eval` — **0.3 с**, стоимость — **$0**.

---

## 3. What to Show on Jury Request (Code & Artifacts Walkthrough)

### A. «Файл, где живёт экспертиза» (Where the Domain Expertise Lives)
Если судьи просят показать, где зашита и как материализуется экспертиза эксперта Plata, открываем **связку из 3 кодовых файлов и 2 артефактов**:

1. **`solution/facts.py` — финансовая предметная область (FactSheet):**
   * **Что видно:** Парсинг структурированного `context` по 4 темам (`credit`, `financial_position`, `savings`, `spending`). Здесь пересчитываются реальные суммы завершённых транзакций по мерчантам и категориям, отдельно учитываются `hold`/`pending` операции, отделяются переводы между собственными счетами от реальных трат, а также считаются балансы, минимальный платёж и проценты по кредиту в MXN.
2. **`solution/rules_library.py` и `solution/checkers.py` — ~20 семейств правил эксперта Plata:**
   * **Что видно:** Шаблоны проверок и правила, которые инстанцируются параметрами из `/input/train.jsonl` (числа и пороги берутся из данных, а не захардкожены). Видно, какие содержательные ошибки ловит эксперт: искажение сумм/балансов/процентов относительно `context`, игнорирование `pending/hold`, смешивание переводов себе с расходами, ошибки в расчёте минимального платежа/процентов (`MIN_INTEREST`), советы, противоречащие данным.
   * **Конкретное правило для показа:** `spending.TX_AMOUNT.merchant` (*«Пересчитай завершённые транзакции мерчанта, прежде чем подтверждать сумму»*) — ловит кейс, где ассистент заявляет `526 MXN` по Uber в августе при реальной сумме завершённых операций `426 MXN`.
3. **`solution/verify.py` — фильтр строгости на обучающей выборке:**
   * **Что видно:** Подсчёт `TP`, `FP`, `precision` и `coverage` каждого правила на всём `train.jsonl`. Видно жёсткое условие: если правило даёт хотя бы один `FP` на `good`-диалоге (`FP > 0`), оно автоматически переводится из активных в `boundary`.
4. **`/artifacts/rules_spec.json` и `/artifacts/explanation.md` — сгенерированный манифест и объяснение для жюри:**
   * **Что видно:** В `rules_spec.json` лежат **26 активных правил** и **18 boundary-гипотез** с их приоритетами и статистикой на train; в `/artifacts/run_meta.json` — `SHA256`-хэш этого манифеста; а в `explanation.md` — детерминированно собранный из `rules_spec.json` отчёт под 5 критериев жюри (приоритеты, цитаты и ID из train, границы применимости).

---

### B. «Место в коде, где вызывается модель» (Where the LLM is Called in Code)
Если судьи просят показать вызов LLM и доказать, что система работает честно и безопасно:

1. **`solution/llm.py` — клиент модели и отказоустойчивость:**
   * **Что видно:** HTTP-клиент на чистом Python stdlib для OpenRouter / Gemini API. Дефолтная модель — открытая `openai/gpt-oss-120b` (лицензия Apache 2.0) через OpenRouter, альтернатива — `Gemma 4`. Видны локальный кэш ответов, ретраи, `circuit breaker` и мягкий фоллбэк: если нет API-ключа или контейнер запущен с `--network none`, пайплайн без ошибок работает в детерминированном режиме.
2. **`solution/semantic.py` — семантический предикат (`llm_predicate`):**
   * **Что видно:** Функция вызова модели для проверки смысловых условий, которые нельзя выразить чистой арифметикой. Модель получает kNN few-shot примеры из `/artifacts/fewshot_index.json` и обязана вернуть структурированный ответ `yes` / `no` / `unknown` вместе с точной цитатой из ответа ассистента.
3. **`solution/induce.py` и `solution/dsl.py` — автопоиск новых правил на остатках (Residual Rule Induction):**
   * **Что видно:** Во время `adapt` код берёт необъяснённые `bad`-примеры (остатки), находит для каждого ближайший `good`-пример из той же темы, вызывает LLM для генерации гипотез правил в безопасном языке условий `solution/dsl.py` (без `eval()` и `exec()`), а затем прогоняет каждую гипотезу через `solution/verify.py` на всём `train` (принять в active / сузить / отправить в boundary).
4. **`solution/validate.py` — валидация и сравнение с голой моделью:**
   * **Что видно:** Вызовы модели для честного замера zero-shot baseline (`[ZERO-SHOT: TBD]`), leave-one-rule-out абляции и теста на автоматическое переоткрытие удалённого правила `MIN_INTEREST` (`[REDISCOVERY: TBD]`).

---

## 4. Five Weak Spots Judges Can Attack & Honest Responses

### Weak Spot 1: "You engineered your ~20 rule families after looking at both public `train` and public `test`. Isn't `0.9502` overfitted to the public split?"
* **Честный ответ (EN):**
  "You are right that public `test` is not a blind holdout because both public splits were inspected during development, so transfer to the private set is not proven by the `0.9502` number alone. To prevent overfitting to individual examples, our rules in `solution/rules_library.py` are parameterized from `train.jsonl` and must achieve **zero false positives (`FP = 0`)** across all 150 training examples in `solution/verify.py`—which rejected 18 plausible but noisy hypotheses into boundary. We are also running grouped cross-validation on train (`[CV: TBD]`) and leave-one-rule-out ablation in `solution/validate.py` (where dropping `MIN_INTEREST` costs 4 TPs and lowers train macro from `0.9943` to `0.9665`) to measure generalization honestly."
* **Суть по-русски:** Признаём прямо: оба публичных набора изучались, поэтому `0.9502` — не слепой holdout. Защита от переобучения — инстанцирование порогов из `train`, жёсткий фильтр `FP=0` (отсеявший 18 правил в boundary), leave-one-rule-out (`0.9943 → 0.9665` без `MIN_INTEREST`) и замер grouped CV на train (`[CV: TBD]`).

---

### Weak Spot 2: "Your deterministic rules only check arithmetic and literal patterns. What happens on purely semantic mistakes?"
* **Честный ответ (EN):**
  "Purely semantic mistakes are our primary failure mode in offline mode: all **4 false negatives on public test** (2 in `spending`, 1 in `credit`, 1 in `financial_position`) and our **1 false negative on train** (caused by the Spanish word *'normalmente'*) are semantic nuances where the numbers look right. Our `solution/dsl.py` intentionally avoids fuzzy text heuristics that would create false positives on `good` dialogues. Instead, semantic checks are delegated to `llm_predicate` (`yes`/`no`/`unknown` with a mandatory quote) in `solution/semantic.py` when an API key is available, and documented transparently in the limitations section of `/artifacts/explanation.md`."
* **Суть по-русски:** Честно говорим, что все **4 FN на public test** и **1 FN на train** (*«normalmente»*) — смысловые, а не числовые. Мы сознательно не лечили их грубыми регулярками, чтобы не получить FP на `good`; для семантики есть `llm_predicate` в `solution/semantic.py`, а в оффлайне эти границы честно описаны в `explanation.md`.

---

### Weak Spot 3: "What if the organizers' private `train.jsonl` contains a brand-new family of expert rules that isn't in `rules_library.py`?"
* **Честный ответ (EN):**
  "If a completely new numerical or semantic rule family appears in private `train.jsonl` and the container runs without an LLM key, our deterministic library will only adapt thresholds for the existing ~20 rule families and will miss the new family. That is specifically why we built `solution/induce.py`: during `adapt`, it takes unexplained `bad` residuals, pairs them with the closest `good` conversations in the same topic, asks the LLM to propose new rules in `solution/dsl.py` or `solution/semantic.py`, and verifies them on the full training set via `solution/verify.py`. However, we are honest that the automated rediscovery rate on held-out rule families is still being measured (`[REDISCOVERY: TBD]`)."
* **Суть по-русски:** Без модели новое семейство правил найдено не будет — сработают только 26 инстанцированных правил из ~20 известных семейств. Для поиска новых семейств написан `solution/induce.py` (индукция на остатках `bad` против ближайших `good` с проверкой на всём train), но его эффективность сейчас в замере (`[REDISCOVERY: TBD]`).

---

### Weak Spot 4: "Docker containers in evaluation might have `--network none` or forbid closed commercial APIs. Doesn't your LLM layer break the contract?"
* **Честный ответ (EN):**
  "No—and we tested this exact scenario by running both `adapt` and `eval` Docker containers with `--network none`. Our default configuration requires no network and no API key, runs in **3.6 seconds** (`adapt`) and **0.3 seconds** (`eval`), passes all **9 organizer tests + 36 unit tests**, and achieves the full **0.9502** macro accuracy on public test. When network access is allowed, `solution/llm.py` defaults to open-weight models (`openai/gpt-oss-120b` under Apache 2.0 or Gemma 4) and wraps every call in a circuit breaker that falls back to deterministic execution if the network is blocked."
* **Суть по-русски:** Контракт не ломается: дефолтный режим — полностью детерминированный без сети, проверен двумя контейнерами `adapt`/`eval` с `--network none` (те же **0.9502**, **3.6 с / 0.3 с**). LLM-слой использует открытые модели (`openai/gpt-oss-120b` Apache 2.0 / Gemma 4) и защищён circuit breaker'ом в `solution/llm.py`.

---

### Weak Spot 5: "Your generated `/artifacts/explanation.md` still has Russian text in some rule descriptions, while the jury is international."
* **Честный ответ (EN):**
  "That is a fair catch: while the conversations are in Mexican Spanish and our metrics/code identifiers are in English, several human-readable rule descriptions in `/artifacts/explanation.md` were drafted in Russian and are currently being translated to English. Importantly, according to the README rubric, the interpretability score `I` (0 to 5) does not grade literary style—it grades five structural criteria: clear conditions, explicit priority order, direct links and quotes to training IDs with labels, explicit boundary rules (our 18 boundary hypotheses), and exact consistency with prediction (`SHA256`-verified against `/artifacts/rules_spec.json`). All five structural elements are already present and machine-verified."
* **Суть по-русски:** Признаём, что часть описаний правил в `explanation.md` сейчас на русском и переводится на английский. При этом по регламенту трека литературный стиль не оценивается: все 5 бинарных критериев оценки `I` (чёткие условия, приоритеты, привязка к ID/цитатам из train, 18 пограничных правил и 100% совпадение с кодом через `rules_spec.json` и `SHA256`) уже выполнены.
````

---

## План верификации
1. После подтверждения плана записать файл `TASK_C_PITCH_AND_QA.md` в рабочую директорию проекта.
2. Проверить наличие всех 4 разделов, соответствие тайминга и объёма питча (≈540 английских слов, в целевом коридоре 450–650 слов), длину ответов на 3 вопроса (3–5 предложений каждый + русская шпаргалка 1–2 строки) и отсутствие выдуманных чисел (использование `[ZERO-SHOT: TBD]`, `[REDISCOVERY: TBD]`, `[CV: TBD]`).
