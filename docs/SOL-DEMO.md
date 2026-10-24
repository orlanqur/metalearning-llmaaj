> Internal working report, written in Russian during the hackathon. The judge-facing documentation is README.md, docs/APPROACH.html, docs/BLIND-EVAL.md, docs/DOCKER.md and docs/SECURITY.md.
Готово. Демо, README с тремя командами и реальным выводом, один тест и [10-строчный отчёт](docs/SOL-DEMO.md) добавлены.

```sh
python3 -S demo/judge_demo.py --id 100a727946a7a45a72c46771e608090f
```

Тест прошёл. `solution/` не изменён, step3 не тронут, коммитов нет. Демо работает offline; отсутствовавшие артефакты step2 восстановлены.

