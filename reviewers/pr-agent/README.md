# pr-agent

AI-ревьюер на базе [qodo-ai/pr-agent](https://github.com/qodo-ai/pr-agent): диффит ветку
против базовой и выдаёт ревью. Богатый набор команд (`review`, `describe`, `improve`,
`ask`, `reflect`), провайдер переключаемый (DeepSeek / GLM / LM Studio) через LiteLLM.

**Кому:** нужно глубокое ревью и разные режимы (описание PR, предложения по коду, вопросы
к диффу); не жалко поставить Python-тулзу глобально.

## Навигация

- 🖥 [**Локально**](local.md) — установка одной командой, конфиг провайдера, запуск.
- 🔁 [**В CI**](ci.md) — авто-ревью с комментированием PR/MR (GitHub / GitLab / Bitbucket / Jenkins).
- ⚙️ [`setup/`](setup/) — `central-setup.sh` и шаблон конфига `config.env.template`.
- 🧩 [Справочник провайдеров](../../docs/providers.md) · [все ревьюеры](../../README.md).
