Готово:

- Созданы [Dockerfile](Dockerfile), [entrypoint.sh](entrypoint.sh), [.dockerignore](.dockerignore) и [LICENSE](LICENSE).
- Добавлены [Docker-инструкция](docs/DOCKER.md), [черновик README](docs/README-draft.md) и [полный отчёт с командами](docs/SOL-DOCKER.md).
- Docker smoke: отдельные контейнеры `adapt` и `eval`, 80 предсказаний, `76/80`, macro topic accuracy `0.9502305665349143`, без ключа и сетевых/model calls.
- Проверенный образ: `sha256:13c9ebbb92998ff99595f51dec24b213065668aff39337dd6721e93cc4893f29`.
- Тесты: upstream `9/9`, solution `29/29`; shell/static self-check — PASS.
- Обновлён [PROJECT-MEMORY.md](PROJECT-MEMORY.md).
- `solution/`, `src/`, `data/` не редактировал; коммитов не делал.

Важно: параллельный STEP2 продолжил менять `solution/*.py` после smoke. Поэтому PASS честно привязан к указанному image digest; текущий итог STEP2 нужно пересобрать и повторно прогнать перед приёмкой. `critic-reviewer` повлиял именно на это разграничение; независимый агент не запускался, выполнена строгая самопроверка.

