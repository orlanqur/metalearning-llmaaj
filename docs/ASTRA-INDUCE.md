# Самообучение Plata — 2026-10-24
Модель `openai/gpt-oss-120b`; `original`; train 150, public test 80; ветка `orlanqur/induce`.
`adapt --from-scratch` / `ADAPT_MODE=from_scratch`: библиотека не инстанцируется, старт правил пустой; default остаётся hybrid.
Остатки bad → ближайший good той же темы → 1–3 гипотезы → весь train → active / одно сужение / boundary → новые остатки.
Лимиты: ≤6 раундов, 8 пар/раунд, `INDUCTION_MAX_CALLS=400` на весь adapt (библиотека, verify, retries); кэш бюджет не расходует.
Gate: TP≥1, FP=0, not_checked=0, без ухудшения темы; остановка — нет active-прогресса/остатков, бюджет или недоступность API.
Промпт требует пересчёта context и фактических условий; примеры библиотеки — только грамматика. Английский `Induction trail` рендерится из manifest со свидетелями и отказами.

| Режим / выборка | Macro | credit | financial_position | savings | spending |
|---|---:|---:|---:|---:|---:|
| Библиотека без модели / train | 0.994318 | 1.000000 | 1.000000 | 1.000000 | 0.977273 |
| Библиотека без модели / test | 0.950231 | 0.933333 | 0.954545 | 1.000000 | 0.913043 |
| From-scratch, checkpoint / train | 0.624926 | 0.694444 | 0.583333 | 0.676471 | 0.545455 |
| From-scratch, checkpoint / test | 0.625889 | 0.600000 | 0.681818 | 0.700000 | 0.521739 |
| Hybrid / train | 0.994318 | 1.000000 | 1.000000 | 1.000000 | 0.977273 |
| Hybrid / test | 0.925231 | 0.933333 | 0.954545 | 0.900000 | 0.913043 |

| Режим | HTTP adapt | Токены adapt | USD adapt | Wall adapt, с |
|---|---:|---:|---:|---:|
| Библиотека без модели | 0 | 0 | 0.000000 | 2.7 |
| From-scratch, checkpoint | ≥78 | ≥409648 | ≥0.039919 | 3300.0 (timeout) |
| Hybrid | 299 | 1251046 | 0.070911 | 1965.9 |

From-scratch **не завершён**: timeout 55 мин, сохранены 3 active из незавершённого раунда; test содержит 1 fallback. Это оценка checkpoint, не полного самообучения.
Hybrid: adapt завершён; две новые гипотезы отвергнуты за невалидный числовой scope, новых active нет; test ниже 0.950231 на 0.025 (savings 0.9 вместо 1.0).
Один запрос from-scratch занял 1402.38 с и 115373 completion tokens, затем дал ValueError JSON; его расход включён. Расход незавершённых запросов неизвестен: ≥ — префикс журнала.
Добавлен опциональный `LLM_MAX_TOKENS` ([контракт OpenRouter](https://openrouter.ai/docs/api_reference/parameters#max-tokens)); default unset сохранён. Исходные прогоны unset, повтор eval — 4096.
Повтор hybrid eval: 12 HTTP, 44432 токена, $0.002091 + 26 ответов из кэша; fallback 2. From-scratch bounded eval: завершён: 17 HTTP, 99284 токена, $0.023749.
При запрошенном max_tokens=4096 провайдер в одном ответе сообщил 32898 completion tokens; это не гарантированный лимит wall time.
Полная стоимость всех попыток eval не установлена; исходный hybrid eval прерван по timeout. Smoke лимита: 1 HTTP / 267 токенов / $0.00002528; отдельно от таблицы adapt.
Артефакты: `artifacts/from_scratch/`, `artifacts/hybrid/` — manifest, explanation, induction_log, model_log, run_meta, cache; partial явно помечен.
Метрики: `out/induce/{library_no_model,from_scratch,hybrid}/{train_score.json,test_score.json}`; predictions и логи связаны хэшами, финальная перепривязка использовала кэш без HTTP.
Команды/история: `commands.json`, `commands_original.json`, `usage.json`; повторные eval в `out/induce/{hybrid,from_scratch_snapshot}_bounded/`; параметры в `out/induce/protocol.json`.
Повтор: штатный prepare_inputs → `python3 -S -m solution.measure_induction <режим>` в чистые каталоги; лимит ответа включается env отдельно. Частичное восстановление: `out/induce/finalize_partial.py`.
Проверки: 48/48 tests + 9/9 scorer; `out/induce/tests.txt`, `scorer-tests.txt`, `validation.json`; финальный no-key smoke подтвердил побайтно прежний test 0.9502305665349143.
Строгая самопроверка: `out/induce/review.md`; отдельного критика не было. Train — resubstitution, CV нет; FactSheet/грамматика априорны, библиотека ранее учитывала оба public split.
`src/`, `data/`, `README.md`, `TEAM/`, `eval_blind/`, `demo/` неизменны. Артефакты/out gitignored и локальны.
Код обнаружен в коммите `ed6c15e` (13:37:59 UTC, создан вне успешных Git-действий этой сессии); финальный отчёт незакоммичен: повторный git add заблокирован sandbox на общем index.lock. Push не выполнялся.
Старт 12:34 UTC; отчёт обновлён 13:42:22 UTC; жёсткая граница 13:44 UTC.
