# Самообучение Plata — 2026-10-24
Модель: `openai/gpt-oss-120b`, язык `original`; train 150, public test 80.
Статус: реализация готова, живые измерения идут; окончательные результаты ниже будут заполнены по scorer.
`adapt --from-scratch` или `ADAPT_MODE=from_scratch` не вызывает библиотеку; default остаётся hybrid.
Цикл: остатки bad → ближайший good той же темы → 1–3 гипотезы → весь train → active / одно сужение / boundary → новые остатки.
Gate: TP≥1, FP=0, not_checked=0; нет ухудшения темы. Один FP отвергает версию правила.
Лимиты: ≤6 раундов, 8 пар/раунд; `INDUCTION_MAX_CALLS=400` считает все adapt HTTP-попытки, включая библиотеку, verify и retries; кэш бесплатен.
Остановка: нет новых active, нет остатков, бюджет вызовов/раундов или недоступность API (отдельный статус).
Промпт требует пересчёта context, сравнения пары и фактических условий; два примера библиотеки иллюстрируют только грамматику DSL.
Английский `Induction trail` рендерится из манифеста: счётчики раундов, свидетели с метками, причины отказа и реальные good-контрпримеры.

| Режим / выборка | Macro | credit | financial_position | savings | spending |
|---|---:|---:|---:|---:|---:|
| Библиотека без модели / train | 0.994318 | 1.000000 | 1.000000 | 1.000000 | 0.977273 |
| Библиотека без модели / test | 0.950231 | 0.933333 | 0.954545 | 1.000000 | 0.913043 |
| From-scratch / train | pending | pending | pending | pending | pending |
| From-scratch / test | pending | pending | pending | pending | pending |
| Hybrid / train | pending | pending | pending | pending | pending |
| Hybrid / test | pending | pending | pending | pending | pending |

| Режим | HTTP adapt/train/test | Токены adapt/train/test | Cost USD adapt/train/test | Wall adapt, с |
|---|---:|---:|---:|---:|
| Библиотека без модели | 0/0/0 | 0/0/0 | 0/0/0 | pending |
| From-scratch | pending | pending | pending | pending |
| Hybrid | pending | pending | pending | pending |

Доказательства: `artifacts/{from_scratch,hybrid}/`: `rules_spec.json`, `explanation.md`, `induction_log.json`, `model_log.json`, `run_meta.json`, кэш.
Метрики и команды: `out/induce/{library_no_model,from_scratch,hybrid}/{train_score.json,test_score.json,commands.json,usage.json}`; HTTP eval — `train.log.json`/`test.log.json`.
Повтор: подготовить входы штатным `src/prepare_inputs.py`; `python3 -S -m solution.measure_induction <режим>`; нужны чистые каталоги соответствующего режима.
Без ключа: отдельный запуск из чистой папки дал 0 HTTP и побайтно те же predictions (test **0.9502305665349143**); `out/induce/no_key_smoke/validation.json`.
Проверки: 48/48 тестов решения и 9/9 scorer; `out/induce/tests.txt`, `scorer-tests.txt`; строгая самопроверка `review.md`, детерминированный аудит `audit.py`; отдельный критик не запускался.
Ограничения: train — resubstitution, CV не выполнена; FactSheet/грамматика остаются априорным знанием, библиотека ранее учитывала оба public split; test не независимый holdout.
Время: старт 12:34 UTC, жёсткая граница 13:44 UTC; запуски ограничены 55 минутами от 12:40 UTC.
Git: ветка `orlanqur/induce`; коммиты заблокированы sandbox на общем `.git/worktrees/induce/index.lock`; push не выполнялся.
`src/`, `data/`, `README.md`, `TEAM/`, `eval_blind/`, `demo/` не менялись. Артефакты и out игнорируются Git и остаются локально.
