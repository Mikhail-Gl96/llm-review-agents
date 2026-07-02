# open-code-review (ocr)

Быстрый CLI-ревьюер [alibaba/open-code-review](https://github.com/alibaba/open-code-review):
ревью незакоммиченного, диапазона коммитов или одного коммита; свои правила по glob-путям;
машинный JSON-вывод. Провайдер любой (OpenAI-совместимый режим).

**Кому:** нужно быстро и скриптуемо (JSON, `--format`, `--audience agent`), с собственными
правилами ревью на уровне репозитория; ok с Node/npm.

## Навигация

- 🖥 [**Локально**](local.md) — установка npm, конфиг провайдера, запуск, свои правила.
- 🔁 [**В CI**](ci.md) — «CLI на раннере» с комментированием PR/MR (GitHub / GitLab / Bitbucket / Jenkins).
- ⚙️ [`setup/`](setup/) — примеры `config.example.json` и `rule.example.json`.
- 🧩 [Справочник провайдеров](../../docs/providers.md) · [все ревьюеры](../../README.md).
