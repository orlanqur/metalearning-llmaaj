> Internal working report, written in Russian during the hackathon. The judge-facing documentation is README.md, docs/APPROACH.html, docs/BLIND-EVAL.md, docs/DOCKER.md and docs/SECURITY.md.
# Шаг 2 — модельные предикаты и индукция правил

Дата: 2026-10-24. Версия решения: `0.2.0`. Вход: `original`.

Реализованы API-клиент, семантические проверки, безопасный DSL, поиск/сужение правил, zero-shot baseline и leave-one-rule-out. Всё использует стандартную библиотеку Python. `.env` отсутствовал; `OPENROUTER_API_KEY` отсутствовал и в окружении. Поэтому **качество живой модели и способность переоткрывать правила не измерены**. Локальная проверка без модели завершена; public test сохранил macro accuracy **0.9502305665349143**.

## Реализация

### `solution/llm.py`

- `urllib.request` → OpenAI-compatible `/chat/completions`.
- Ключ: `OPENROUTER_API_KEY`; base URL: `OPENROUTER_BASE_URL`, default `https://openrouter.ai/api/v1`.
- `INDUCTION_MODEL`: default `openai/gpt-oss-120b`; пустой/отсутствующий `EVAL_MODEL` наследует его.
- Локальный `.env`: буквальный парсер `KEY=VALUE`, кавычки и `export`; без исполнения shell и интерполяции. Уже установленное окружение имеет приоритет. Значения ключей не выводятся и не сохраняются.
- `temperature=0`, `response_format.type=json_schema`, `strict=true`; схема продублирована в инструкции. JSON проверяется локально. На отказ structured outputs используется запрос без `response_format`; парсер принимает обычный JSON, fenced JSON и объект в тексте. Формат запроса сверён с [официальной документацией OpenRouter](https://openrouter.ai/docs/guides/features/structured-outputs).
- Всего **3 попытки**, включая первую; паузы 1 и 2 секунды, timeout 45 секунд на HTTP-вызов. После исчерпания попыток circuit breaker прекращает новые сетевые вызовы в этом процессе; кэш продолжает читаться.
- Ключ кэша: SHA256 канонического JSON `[model, system, user, schema]`. Adapt пишет в `<artifacts>/cache`; eval читает этот каталог и пишет в `<output-directory>/cache`. Если пути совпадают, запись eval идёт в `eval_cache`. Кэш сохраняет только проверенный ответ и идентификаторы; запись атомарная. Повреждённый кэш игнорируется.
- `model_log.json`/логи eval: статусы, hash запроса, число попыток, длительность, токены и cost, если провайдер его вернул. Неизвестная стоимость не подменяется оценкой; `cost_complete=false` отмечает неполноту. Тексты HTTP-ошибок не пишутся, поскольку они могут содержать секреты.
- `--no-model` или `SOLUTION_DISABLE_LLM=1` запрещают живые запросы. Уже существующие валидные cache entries могут использоваться.

### `solution/semantic.py`

Узкий предикат получает компактный FactSheet с populated context fields, весь диалог, конкретное правило и до трёх ближайших train-примеров той же темы. TF-IDF считается по тексту диалогов; текущий ID и идентичный диалог исключаются из few-shot. Index сохраняет сообщения, метки, факты и context hash — отдельный eval-процесс не нуждается в исходном train.

Результат: `{verdict: yes|no|unknown, quote, reason}`. Для `yes` цитата должна дословно встречаться в сообщении ассистента; иначе результат понижается до `unknown`. Нет ключа/кэша или API недоступен → `None`/`not_checked`. Unknown не является нарушением и сохраняется в логе. При отсутствии другого активного нарушения используется сохранённая метка большинства темы; обычный default остаётся `good`.

Атомарные шаблоны: выполненное действие, досрочное снятие Fijo, минимальный платёж против процентов, согласие с неверным утверждением пользователя, неответ при наличии необходимых данных. Новые семантические критерии могут прийти из индукции. Шаблоны повторно проверяются на переданном train, а не активируются автоматически.

### `solution/dsl.py`

Интерпретатор JSON-дерева: `and/or/not`, числовые сравнения с допуском, `add/sub/mul/div`, присутствие/отсутствие числа типа `money/number/percent`, область `all/first/last`, наличие populated context field, boolean flag и буквальная подстрока user/assistant. Допуск по умолчанию `max(1, 0.005 × abs(expected))`; его можно задать явно.

Доступ только к фиксированному набору корней FactSheet. Нет Python `eval`/`exec`, генерации Python, произвольных атрибутов, файловых/сетевых операций или регулярных выражений от модели. Ограничены глубина, количество узлов и длины строк. Отсутствующий числовой операнд остаётся unknown даже под `not`; деление на ноль тоже unknown.

Пример нарушения «при удержании не назван доступный остаток»:

```json
{
  "op": "and",
  "args": [
    {"op": "flag", "name": "has_hold"},
    {"op": "number_absent", "kind": "money", "value": {"ref": "expected.available_now"}}
  ]
}
```

Это только иллюстрация синтаксиса; без train-verification выражение не становится активным правилом.

### `solution/induce.py`

1. Остатки: ошибки текущих активных правил плюс все bad без объяснения; bad идут первыми. Список вычисляется и без ключа.
2. Для каждого остатка — ближайший good той же темы по TF-IDF JSON context. Пара, оба FactSheet и исходные сообщения передаются модели, которая предлагает 1–2 атомарных правила. Списка известных семейств в discovery prompt нет.
3. Отдельный вызов объединяет гипотезы в ≤8 канонических кандидатов **на тему**. `impl` — JSON-строка DSL либо текст семантического условия.
4. Каждый исполнимый кандидат проверяется `verify.py` на всём train с topic/applicability gate; сохраняются TP/FP, цитаты и все измеренные witness-ID. Модельные `expected_bad_ids` не используются как предсказания.
5. При FP выполняется один раунд сужения по good-контрпримерам и bad-свидетелям. Невалидный/недоступный ответ → boundary. После сужения действуют те же пороги: precision ≥0.9, ≥3 различных context среди TP, ни одного unchecked результата и отсутствие падения числа правильных ответов в каждой теме. Последний критерий проверяется для текущего манифеста плюс кандидат, последовательно после каждого принятия.
6. Прошедшие кандидаты добавляются с `origin: induced`; остальные остаются boundary либо отклоняются как невалидные/дубликаты. Исходные предложения, объединение, начальная проверка, сужение, причины отказа и финальные решения — в `induction_log.json`.

Дополнительный консервативный gate — отсутствие unchecked train-строк. Контексты различаются по точному каноническому SHA256; близкие, но не идентичные контексты пока не объединяются.

### Adapt, eval и explanation

После инстанцирования шаблонов adapt запускает индукцию, затем **тот же `predict`, что использует eval**, на train. Сохраняются `rules_spec.json`, `fewshot_index.json`, `induction_log.json`, `model_log.json`, `run_meta.json`, `judge_prompt.txt`, `explanation.md`.

Explanation детерминированно строится из сохранённого манифеста: критерии, приоритеты, ссылки/цитаты, boundary, механизм поиска, таблица train и ограничения. Свободный пересказ моделью не используется. `judge_prompt.txt` — справочный перечень условий манифеста; узкий semantic runtime передаёт модели одно конкретное правило. Eval не читает метки test, но использует labeled train few-shot из артефактов.

Хэш финального манифеста:

```text
0cc8a08ebc3c9396d65603808639e8ff159cdecadfa380171f4b819ba68e14ce
```

Он совпадает в explanation, run_meta и логах eval. Логи eval также связывают SHA256 входа и predictions. В текущем прогоне: **44 кандидата, 26 active, 18 boundary; индуцированных правил нет**, `induction.status=skipped_no_key`, один train-остаток. Восемь семантических кандидатов не проверены моделью.

## Фактические результаты

Метрики рассчитаны неизменённым `src/evaluate.py`. Positive = `bad`.

| Тема | Train correct/N | Train accuracy | Public correct/N | Public accuracy |
|---|---:|---:|---:|---:|
| credit | 36/36 | 1.000000 | 14/15 | 0.933333 |
| financial_position | 36/36 | 1.000000 | 21/22 | 0.954545 |
| savings | 34/34 | 1.000000 | 20/20 | 1.000000 |
| spending | 43/44 | 0.977273 | 21/23 | 0.913043 |
| **Macro accuracy** | | **0.9943181818181819** | | **0.9502305665349143** |

Train: 149/150, TP=59, FP=0, FN=1, TN=90. Public test: 76/80, TP=26, FP=0, FN=4, TN=50. Предсказания совпали с сохранённым результатом шага 1; подгонки по новым test-ошибкам не выполнялось.

| Диагностика | Фактический результат |
|---|---|
| Голая `EVAL_MODEL` zero-shot | **Не измерено**: 0/80 модельных ответов; `model_baseline_valid=false`, `model_macro_topic_accuracy=null` |
| Технический fallback zero-shot | 80 валидных строк; majority по train даёт macro **0.625889328063241**. Это **не качество модели** и не число для сравнения «голая модель vs adapt» |
| LOO `MIN_INTEREST` | Отключены и lexical, и semantic шаблоны семейства; четыре исходных TP стали FN; train macro **0.966540404040404** (145/150) |
| Переоткрытие скрытого семейства | **Не проверено**: `rediscovered=null`, `status=skipped_no_key`; целевой recall ≥0.7 означает ≥3 из 4 исходных TP для одного принятого индуцированного правила |

Готовая честная формулировка для README: «Public macro accuracy без модели — 0.9502305665. Zero-shot openai/gpt-oss-120b и модельная индукция ещё не измерены: в среде не было API-ключа».

### Время и стоимость

Финальный локальный цикл (`python3 -S`, host machine): adapt 3.599 с; eval train 0.516 с; eval public test 0.311 с; zero-shot fallback с scorer 0.079 с; LOO 3.648 с. Это wall time процессов из `out/step2/commands.json`, не скорость модели. Чистый отдельный adapt+eval с проверками занял 3.925 с.

**Реальных модельных HTTP-вызовов: 0; токенов: 0; стоимость: 0.** В тестах ответы API имитировались; их фиктивная usage/cost не является расходом. Латентность, стоимость и совместимость конкретного живого endpoint остаются `not_checked`.

## Проверки

- **33/33** теста решения, включая 19 новых; **9/9** upstream tests.
- JSON/fenced/prose parsing, schema validation, `.env` precedence, кэш между отдельными клиентами, отсутствие ключа, malformed cache, structured-output fallback, три попытки, circuit breaker, incomplete HTTP body, malformed usage, отсутствие ключа в логах.
- DSL: числа/типы/допуски, arithmetic, and/or/not, known false, missing operands, zero division, отказ от Python и слишком глубоких выражений.
- Semantic: исключение собственного примера, grounding цитаты, unknown и majority fallback; принятие индуцированного semantic правила на контролируемых данных.
- Индукция: контрастная пара → clustering → полная проверка → сужение → принятие; дубликаты context не удовлетворяют поддержке, падение любой темы запрещает принятие, одинаковые refinement-ID не дублируются.
- Полный eval при искусственных таймаутах API сохранил каждый input ID и корректный CSV; API-ошибка не вышла наружу.
- Чистая временная папка содержала только `solution/` и JSONL; `python3 -S` выполнил adapt и отдельный eval. Артефакты были read-only на eval. Манифест, fewshot, explanation, judge_prompt и induction_log совпали побайтно с основным запуском; predictions тоже совпали.
- Детерминированно сверены: точный хэш explanation/manifest, train summary со штатным scorer, полнота/уникальность ID, TP/FP и реальные train labels свидетелей, отсутствие сторонних импортов и вызовов Python eval/exec, удаление семейства в LOO, неизменность `src/` и `data/`.
- Отдельная строгая самопроверка выполнена; независимый проверяющий не запускался. Исправленные находки: неверная форма JSON-кэша, malformed usage/HTTP response, дубли refinement-ID и неточная фраза explanation о train labels.

Доказательства: [`commands.json`](../out/step2/commands.json), [`validation.json`](../out/step2/validation.json), [`score.json`](../out/step2/score.json), [`train_score.json`](../out/step2/train_score.json), [`zero_shot.report.json`](../out/step2/zero_shot.report.json), [`leave_one_rule_out.json`](../artifacts/step2_loo_min_interest/leave_one_rule_out.json), [`run_meta.json`](../artifacts/step2/run_meta.json). Генерируемые каталоги игнорируются Git.

## Запуск сейчас и после добавления ключа

В `.env.example` указаны все переменные. Ключ можно добавить в локальный игнорируемый `.env` или передать окружением; shell `source` не нужен. Для гарантированного отсутствия живых вызовов добавить `--no-model`. Без этого флага те же команды автоматически включат модель, когда ключ появится:

```sh
python3 -S -m solution adapt --input out/public_input/train.jsonl --artifacts artifacts/step2
python3 -S -m solution eval --input out/public_input/test.jsonl --artifacts artifacts/step2 --output out/step2/predictions.csv
python3 -S src/evaluate.py --test data/public_test.csv --predictions out/step2/predictions.csv --out out/step2/score.json
python3 -S -m solution.validate zero-shot --input out/public_input/test.jsonl --artifacts artifacts/step2 --output out/step2/zero_shot.csv --labels data/public_test.csv
python3 -S -m solution.validate leave-one-rule-out --input out/public_input/train.jsonl --artifacts artifacts/step2 --output artifacts/step2_loo_min_interest --family MIN_INTEREST
python3 -S -m unittest discover -s tests -v
python3 -S -m unittest discover -s src -p 'test_*.py'
```

`out/public_input` подготовлен штатным prepare_inputs на шаге 1. Для нового train передать его JSONL и чистый каталог artifacts. После появления ключа adapt сначала проверит семантические шаблоны, затем предложит/объединит/проверит правила на остатках; eval использует только принятые правила и few-shot из сохранённых артефактов. Baseline отправит весь context+dialog без learned rules; LOO заново адаптируется без указанного семейства и измерит пересечение TP.

## Пробелы и границы

Живой API, качество семантики, реальное обнаружение новых правил, zero-shot и rediscovery не подтверждены. Нет grouped-context cross-validation с повторной индукцией внутри фолдов, near-duplicate grouping или поиска вариантов всех унаследованных числовых конвенций из §7a. Train-цифры — resubstitution. Ручная библиотека шага 1 опиралась на исследование обоих публичных наборов; public test не независимый holdout. Без модели остаются прежние один train FN и четыре test FN.

DSL проверяет присутствие чисел и буквальных выражений, но не понимает их смысловую роль; неоднозначные случаи должны проверяться семантически. Неполная модельная проверка не активирует правило. Один исчерпанный HTTP-запрос открывает circuit breaker до следующего процесса, поэтому краткий сбой может сократить индукцию; это отражается в статусе/логе.

Dockerfile и `docs/DOCKER.md` не редактировались. Docker smoke другого исполнителя относится к его сохранённой версии исходников; текущий шаг подтверждён чистым Python-запуском, но образ после этих изменений здесь не пересобирался. `src/`, `data/` и материалы analysis не менялись. Коммитов, push, передачи или приёмки организаторами не было.
