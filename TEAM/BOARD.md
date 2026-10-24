# Доска задач (меняй только свою строку; формат: статус | задача | владелец | файлы | обновлено)

- done | Шаг 1: детерминированные правила, adapt/eval, 0.950 public test | Astra (Codex) | solution/, tests/, docs/ASTRA-STEP1.md | 13:00
- done | Шаг 2: LLM-клиент, семантические правила, DSL, автопоиск правил, baseline (без ключа) | Astra (Codex) | solution/ docs/ASTRA-STEP2.md | 13:25
- dropped | Шаг 3 последовательный прогон gpt-oss (1 ч 38 мин, 276 вызовов) остановлен; замер повторяется гибридом с параллельными вызовами после слияния induce | Astra (Codex) | artifacts/step3 (кэш сохранён) | 15:02
- done | Dockerfile, entrypoint, LICENSE, docs/DOCKER.md, docs/README-draft.md | Sol (Codex) | Dockerfile entrypoint.sh LICENSE docs/ | 13:25
- done | Публичный прогон Gemini закончен: macro 0.9507 (76/80). README форка не написан | Михаил (Cursor) | docs/MISHA-GEMINI.md solution/llm.py | 14:25
- done | Демо для судей: demo/judge_demo.py --id <id> (вердикт, правило, цитата, похожие train) | Codex (Sol) | demo/ tests/test_demo.py | 13:45
- done | Слепая проверка: CV 0.922 vs 0.994, падение на пустом диалоге, 3 вердикта зависят от индекса хода | Codex (Blind) | eval_blind/ docs/BLIND-EVAL.md | 13:41
- done | Фикс по BLIND-EVAL + параллельные вызовы модели (LLM_WORKERS) + explanation EN + docs/SECURITY.md — слито 4a42e6d, тесты 39+9 OK, public 0.9502 | Claude-приёмщик | solution/ tests/ | 15:02
- doing | Режим adapt --from-scratch: многораундовая индукция, методика в промпте, induction trail в explanation, замер from-scratch vs гибрид | Astra-2 (Codex) | worktree ../induce, ветка orlanqur/induce, docs/ASTRA-INDUCE.md | 14:36
- done | Питч 3–5 мин + 3 вопроса судей + показ кода + 6 слабых мест; осталось подставить zero-shot и rediscovery из шага 3 | Claude-планировщик | TEAM/PITCH.md | 13:50
- todo | Чеклист FAQ перед сдачей, push, SHA организаторам, форма OrganizerHQ | Аркадий | — | —
