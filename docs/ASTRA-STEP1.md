# ШАГ 1 — детерминированная основа Plata

Дата: 2026-10-24. Язык входа: `original` (исходные многоязычные диалоги).

**Итог: public test macro_topic_accuracy = 0.9502305665349143, цель ≥ 0.95 выполнена.**
Это локальный результат шага 1, не результат приватной оценки или сдачи организаторам.

## Что реализовано

- `solution/facts.py`: FactSheet для четырёх тем; арифметика остатков, удержаний и долга; предыдущий календарный месяц и ровно три полных месяца; расходы с возвратами; отдельные переводы; агрегаты completed-транзакций по merchant/category/month; выбранные и противоположные ставки; даты с годом, флаги и числа каждого ответа ассистента.
- `solution/checkers.py`: параметризованные шаблоны 1–7 из PLAN §4, дополнительные узкие проверки дат/сумм и перенесённые лексические эвристики. Результат каждой исполняемой проверки: `rule_id`, `violated`, `evidence` с цитатами. `llm_predicate(facts, params)` возвращает `None`; диспетчер сохраняет `violated: null`, `status: not_checked`.
- `solution/rules_library.py`: библиотека гипотез, инстанцируемых по темам, полям и продуктам входного train. Суммы и даты вычисляются заново для каждого context. Нет готовых меток, item_id или числовых ответов из реконструкции.
- `solution/verify.py`: каждый кандидат проверяется на всём train через свой topic/applicability; сохраняются TP, FP, precision, coverage, статистика по темам, ID и цитаты примеров/контрпримеров. Coverage = TP / все bad темы; для общих конвенций — все bad четырёх тем. `active` требует TP≥1, FP=0; неподдержанные или непроверенные кандидаты тоже остаются `boundary` с отдельной причиной.
- `solution/adapt.py`: train-only инстанцирование и verify; `rules_spec.json`, `fewshot_index.json`, `explanation.md`, `run_meta.json`. Explanation рендерится из сохранённого манифеста по пяти критериям жюри. Run metadata содержит Python/версию решения, язык, время, SHA256 входа и файлов кода, ноль вызовов моделей/сети.
- `solution/eval.py`: читает только вход и манифест; любая активная проверка темы → bad, иначе good. Случайно переданная label отбрасывается загрузчиком. CSV содержит ровно `item_id,label`, одну строку на ID.
- `python -m solution adapt|eval`: пути по умолчанию соответствуют `/input`, `/artifacts`, `/output` из README. `requirements.txt` не содержит зависимостей; ключи в `.env.example` пусты; локальные выходы исключены `.gitignore`.

Допуск денежных значений: `max(1, abs(expected) * 0.005)`. Форматы `21,617`, `21 617`, `21617.00`, NBSP/узкий NBSP и смешанные десятичные разделители нормализуются. `21.6k` намеренно не поддерживается. Для ставок сохранён допуск исходника 0.05 процентного пункта.

## Фактические метрики штатного src/evaluate.py

| Тема | Train верно / всего | Train accuracy | Public test верно / всего | Public test accuracy |
|---|---:|---:|---:|---:|
| credit | 36 / 36 | 1.000000 | 14 / 15 | 0.933333 |
| financial_position | 36 / 36 | 1.000000 | 21 / 22 | 0.954545 |
| savings | 34 / 34 | 1.000000 | 20 / 20 | 1.000000 |
| spending | 43 / 44 | 0.977273 | 21 / 23 | 0.913043 |
| **macro_topic_accuracy** | | **0.9943181818181819** | | **0.9502305665349143** |
| Overall accuracy | 149 / 150 | 0.9933333333333333 | 76 / 80 | 0.9500000000000000 |

Train: TP=59, FP=0, FN=1, TN=90; Cohen kappa=0.9860724233983286.
Public test: TP=26, FP=0, FN=4, TN=50; Cohen kappa=0.8904109589041095.
Positive здесь означает `bad`. Матрицы штатного scorer идут в порядке `good,bad`.

Доказательства: [`out/score.json`](../out/score.json), [`out/train_score.json`](../out/train_score.json),
[`out/validation.json`](../out/validation.json), [`artifacts/rules_spec.json`](../artifacts/rules_spec.json),
[`artifacts/explanation.md`](../artifacts/explanation.md). Эти генерируемые файлы игнорируются Git и воспроизводятся командами ниже.

Промежуточные метрики 0.94860 и 0.96110 не являются итоговыми. Первая выявила слишком дробное разбиение KNOWN_DATA; критерий запроса известного поля объединён с параметризованными полевыми условиями и заново проверен на всём train. Во второй действовали случайно поддержанные внутри одной темы строгие кандидаты про ссылки/анкоры. После проверки этих общих конвенций по всем четырём темам они получили FP и отключены. Итоговая цифра выше получена после этих исправлений, из чистого запуска.

## Семейства исходного judge.py

Все 18 семейств представлены шаблонами; хотя бы один вариант каждого семейства активен. Не каждый узкий вариант имеет поддержку train.

| Семейство | Шаблон / источник параметров |
|---|---|
| KNOWN_DATA | asks_known_field / denies_known_field; наличие соответствующего поля context и унаследованные языковые паттерны |
| AMOUNT | amount_mismatch / turn_contradiction; баланс продукта, месячные покупки, долг выписки |
| DATE | date_mismatch; даты context, включая явный год |
| NET | required_number_missing; own−debt и допустимые варианты с hold/locked |
| HOLD | required_number_missing; balance−hold и доступный ликвидный итог |
| CREDIT_AS_MONEY | poison_number_present; own+available_credit/credit_limit |
| RATE | rate_mismatch; текущая подписка, продукт и ставки из context |
| PERIOD_EXPLICIT / PERIOD_DEFAULT | wrong_period; предыдущий месяц / последние три полных месяца |
| REFUND | poison_number_present / amount_mismatch; purchases−refunds, merchant/category/period |
| OWN_TRANSFER | poison_number_present и узкий lexical_predicate; transfers_own |
| OTHER_TRANSFER | required_number_missing при явном исключении переводов другим |
| TX_AMOUNT | amount_mismatch; completed-транзакции нужного merchant/month |
| MIN_INTEREST / PAID_STATUS | lexical_predicate, ограниченный данными credit_statement |
| ACTION / FIXED_LOCK / DENIAL | унаследованные lexical_predicate с контекстными условиями |

Фразы перенесены из `../analysis/astra/judge.py`; `rules.json` использован для сверки состава семейств, а не как источник готовых вердиктов. Файлы реконструкции не изменены. Их SHA256 сохранены в `out/validation.json`.

В финальном манифесте **40 кандидатов: 26 active, 14 boundary**. Из boundary: 7 имеют FP, 3 не имеют TP, 4 — непроверенные llm_predicate. Приоритеты видны в manifest; ранний активный hit достаточен для bad. Boundary никогда не отменяет активное нарушение.

## Allowlist выведен через контрпримеры train

Здесь проверяются намеренно строгие гипотезы, а не заранее прописанные исключения.

| Отклонённая строгая гипотеза | TP | FP |
|---|---:|---:|
| Переводы другим обязательно внутри единого итога | 2 | 8 |
| Собственные средства всегда только после hold | 3 | 7 |
| Допустим только один наблюдаемый lnk target | 10 | 50 |
| Каждый анкор обязательно переведён | 2 | 1 |
| Любая односимвольная опечатка в продукте — нарушение | 0 | 8 |
| Допустимы только простые проценты | 0 | 1 |
| Любое упоминание процентов на остаток запрещено | 4 | 13 |

Все семь автоматически стали boundary из-за FP>0. Ссылки на реальные item_id и цитаты находятся в explanation и manifest. Если TP=0, честно указано отсутствие bad-свидетеля: пара good/bad не выдумывается. Общие конвенции ссылок/анкоров/опечаток имеют scope `all`; остальные относятся к конкретной теме.

## Что оставлено на следующие шаги

- Четыре llm_predicate — смысл утверждения о выполненном действии, досрочном снятии, процентах/минимальном платеже, согласии с неверным утверждением, роли суммы и периода. Сейчас работает только ограниченный словарь фраз исходника; универсальной семантической проверки нет.
- Нет hypothesize/cluster, открытия новых семейств, сужения гипотез моделью, kNN-судьи, judge_prompt, grouped-context split, Dockerfile или zero-shot baseline. Это последующие шаги PLAN, не заявленные результаты шага 1.
- Train-оценка является resubstitution, а не внутренним holdout. Публичный test тоже не независим: исходная ручная реконструкция строилась после изучения обоих публичных наборов. Текущий adapt читает только переданный train; новых выражений/ответов по test в код не добавлялось.
- Год в явно написанной дате учитывается; однако роль даты распознаётся ограниченно: дата гипотетического сценария может быть принята за фактическую. Числовые проверки в основном используют явные суммы с MXN/песо/pesos. Числа без валюты сохранены в FactSheet, но не все используются как денежные утверждения.
- Лексические шаблоны не гарантируют полноту на новых формулировках, языках и продуктах. Одно семейство KNOWN_DATA объединяет полевые варианты; поддержка всего семейства не доказывает отдельную поддержку каждой фразы. Популяция неизвестного на train поля не создаёт автоматически новый вариант в eval.
- Неизвестные или непроверенные нарушения становятся good при отсутствии другого активного hit — это явно заданный fallback, а не подтверждение корректности.

Оставшиеся пропуски:

| Набор / item_id | Причина |
|---|---|
| train `5f9ae3d8d52eaf3dade5beee0fce7f0e` | `normalmente` отсутствует в унаследованном default-period словаре; пропуск был и в исходнике |
| test `15b42e3513d7c700cc9ae71435bf4f29` | KNOWN_DATA для spending не имеет TP на train и не активирован |
| test `73380ff8277a4289397c9acadd797641` | Явное включение собственных переводов: узкий лексический вариант без TP на train |
| test `9273f1d3f88303616b4e658ef581c389` | Вариант известной даты оплаты внутри accounts не инстанцирован из схемы train |
| test `ac17233bc6736cf20601c097638fe414` | Проверка оставшегося долга credit.AMOUNT.remaining_debt без TP на train |

## Воспроизведение

Python 3.10+, сторонние пакеты и ключи не нужны. Для prepare используйте пустой `out/public_input`: штатный скрипт намеренно отклоняет непустую папку.

```sh
python3 src/prepare_inputs.py --train data/public_train.csv --test data/public_test.csv --out-dir out/public_input
python3 -m solution adapt --input out/public_input/train.jsonl --artifacts artifacts
python3 -m solution eval --input out/public_input/test.jsonl --artifacts artifacts --output out/predictions.csv
python3 src/evaluate.py --test data/public_test.csv --predictions out/predictions.csv --out out/score.json
python3 -m solution eval --input out/public_input/train.jsonl --artifacts artifacts --output out/train_predictions.csv
python3 src/evaluate.py --test data/public_train.csv --predictions out/train_predictions.csv --out out/train_score.json
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s src -p 'test_*.py'
```

Для train-as-test используется прямой eval: upstream prepare отвергает пересекающиеся train/test ID. Eval намеренно отбрасывает label.

## Проверка и границы передачи

- 14 новых тестов: числовые форматы/допуски; переход года и неполный период; hold/debt/locked/credit; refunds/status; тариф; годы дат; известное false-поле; позднее противоречие; None от LLM; FP→boundary; сохранённые артефакты и объяснение; независимость от ID/label; fallback; дубли ID; CLI без site-packages.
- 9 upstream-тестов контракта — PASS. `git diff --exit-code -- src data` и `git status --short -- src data` подтвердили отсутствие правок upstream.
- Чистая временная папка содержала только `solution/` и JSONL. `python3 -S -m solution adapt/eval` успешно выполнились. Манифест, fewshot и explanation совпали побайтно с основным запуском; предсказания прошли штатный scorer. `run_meta` по определению имеет новое время запуска.
- Проверены уникальность и полнота ID, ровно две CSV-колонки, принадлежность всех witness-ID только train, соответствие TP/FP длинам списков и инвариант активации. Доказательства — `out/validation.json`.
- Выполнена строгая самопроверка по исходнику, контракту и детерминированным тестам; независимый агент не запускался. Сеть и модели не вызывались. Коммитов, push, отправки и деплоя не было.
