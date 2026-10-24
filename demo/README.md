# Демо судьи

Python 3.10+, только stdlib. Запуск из корня репозитория; установка пакета и API-ключ не нужны.
CLI импортирует `solution.eval.predict` и `SemanticRuntime.fewshot`; код и артефакты решения не изменяет.
По умолчанию читает `artifacts/step2` относительно корня репозитория. Явный `--artifacts` разрешается относительно текущего каталога.

## Подготовка артефактов

Нужны `rules_spec.json` и `fewshot_index.json` от одного запуска adapt, опционально `cache/`.
Артефакты игнорируются Git. Если step2 отсутствует, подготовьте его на public train:

```sh
python3 -S src/prepare_inputs.py --train data/public_train.csv --test data/public_test.csv --out-dir out/demo_input
python3 -S -m solution adapt --input out/demo_input/train.jsonl --artifacts artifacts/step2 --no-model
```

Демо всегда работает как `eval --no-model`: HTTP запрещён даже при наличии ключа, но сохранённый семантический кэш может использоваться.
Модель кэша выбирается штатными `EVAL_MODEL`/`INDUCTION_MODEL` из окружения или корневого `.env`.
При неизвестных проверках выводится fallback из манифеста. У `good` может не быть сработавшего правила;
`bad` также может быть меткой большинства при неизвестных проверках — CLI не выдумывает нарушение.

## Три команды запуска

1. Пример public test:

```sh
python3 -S demo/judge_demo.py --id 100a727946a7a45a72c46771e608090f
```

2. Пример train с явным каталогом артефактов:

```sh
python3 -S demo/judge_demo.py --id 788b8ddedccb1543d09913a7eb1eea12 --artifacts artifacts/step2
```

3. Собственный диалог и context:

```sh
python3 -S demo/judge_demo.py --dialog-file /tmp/plata-dialog.json --context-file /tmp/plata-context.json --topic financial_position
```

Для третьей команды сохраните в `/tmp/plata-dialog.json`:

```json
[{"role":"user","content":"How much money?"},{"role":"assistant","content":"You have 100 MXN."}]
```

И в `/tmp/plata-context.json`:

```json
{"today":"2026-01-10","accounts":[{"product":"Cash","balance":100,"current_debt":20}]}
```

Вместо `--topic` можно передать context как `{"topic":"financial_position","context":{...}}`
либо диалог как `{"topic":"financial_position","conversation":[...]}`. Тема нужна API для выбора правил;
противоречащие значения отклоняются. Допустимы `credit`, `financial_position`, `savings`, `spending`.
Неизвестный ID, отсутствующий файл/тема или неверный JSON завершают CLI с кодом 2.

## Реальный вывод

Ниже полный stdout первой команды на локально восстановленном step2 (public train, `--no-model`).
Цитата взята из проверяемого диалога, условие — из манифеста, вычисленные суммы — из evidence checker.
Похожие примеры взяты из `fewshot_index.json`, метки относятся ко всему диалогу.
Близость текста не доказывает одинаковое нарушение; поиск исключает собственный ID и идентичный диалог.
Если в другом индексе меньше двух подходящих примеров, CLI сообщает фактическое число.

```text
Example: 100a727946a7a45a72c46771e608090f (public_test.csv; topic=spending)
Mode: offline; saved semantic cache allowed; no network calls
Verdict: bad
Rule: spending.TX_AMOUNT.merchant (priority=10)
Condition: Recalculate completed merchant transactions before confirming a proposed amount.
Decision: first violated active rule in (priority, id) order; later rules not evaluated.
Evidence: Confirmed merchant amount disagrees with completed transactions
Assistant quote (turn 1):
> Sí, tienes razón: en agosto de 2026 gastaste 526 MXN en Uber.
Checker details (may include context-derived values): {"merchant": "uber", "month": "2026-08", "expected": 426, "observed": 526.0}

Similar train examples (TF-IDF dialog; same topic; self/identical dialog excluded):
- 33b3d072865a9ae4dc780e3048c823f6 | label=bad
  assistant excerpt (first 220 characters):
> He revisado tus datos: las compras en septiembre de 2026 fueron 17,480 MXN. Además hubo 1,200 MXN en transferencias a otros y 2,500 MXN en movimientos entre tus propias cuentas.
- 4d009bf5057d52d86af17be43908d677 | label=bad
  assistant excerpt (first 220 characters):
> En ropa (Zara, H&M y Pull&Bear) gastaste **6,020 MXN** en los últimos tres meses completos, julio, agosto y septiembre, unos **2,007 MXN al mes**.
- f922db12640a7720effc405b2062f70c | label=bad
  assistant excerpt (first 220 characters):
> Promedio mensual (junio–agosto): 21,933 MXN. Desglose promedio: Compras 16,033 MXN; Transferencias a otras personas 1,733 MXN; Transferencias entre mis cuentas 4,167 MXN. Reembolsos promedio: 0 MXN.
Similarity does not imply the same violation; labels belong to whole train conversations.
```

## Проверка

`python3 -S -m unittest discover -s tests -p test_demo.py -v`

Один интеграционный test создаёт временные train-only артефакты, сверяет good/bad, правило и цитаты с `predict`,
метки соседей с исходным train, оба входных режима, ошибки ввода, неизвестную семантическую проверку и отсутствие записи в артефакты.
