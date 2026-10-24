# Доска задач (меняй только свою строку; формат: статус | задача | владелец | файлы | обновлено)

- done | Шаг 1: детерминированные правила, adapt/eval, 0.950 public test | Astra (Codex) | solution/, tests/, docs/ASTRA-STEP1.md | 13:00
- done | Шаг 2: LLM-клиент, семантические правила, DSL, автопоиск правил, baseline (без ключа) | Astra (Codex) | solution/ docs/ASTRA-STEP2.md | 13:25
- doing | Шаг 3: те же прогоны с моделью (adapt, zero-shot, LOO) | Astra (Codex) | artifacts/step3 out/step3 docs/ASTRA-STEP3.md | 13:25
- done | Dockerfile, entrypoint, LICENSE, docs/DOCKER.md, docs/README-draft.md | Sol (Codex) | Dockerfile entrypoint.sh LICENSE docs/ | 13:25
- doing | README.md форка по шаблону FAQ; Gemini в llm.py, если нет ключа OpenRouter | Михаил (Cursor) | README.md solution/llm.py | 13:21
- done | Демо для судей: demo/judge_demo.py --id <id> (вердикт, правило, цитата, похожие train) | Codex (Sol) | demo/ tests/test_demo.py | 13:45
- done | Слепая проверка: CV 0.922 vs 0.994, падение на пустом диалоге, 3 вердикта зависят от индекса хода | Codex (Blind) | eval_blind/ docs/BLIND-EVAL.md | 13:41
- todo | Фикс по BLIND-EVAL: пустой диалог, привязка правил к роли, тесты; explanation на английском | Astra после шага 3 | solution/ tests/ | 13:41
- done | Питч 3–5 мин + 3 вопроса судей + показ кода + 6 слабых мест; осталось подставить zero-shot и rediscovery из шага 3 | Claude-планировщик | TEAM/PITCH.md | 13:50
- todo | Чеклист FAQ перед сдачей, push, SHA организаторам, форма OrganizerHQ | Аркадий | — | —
