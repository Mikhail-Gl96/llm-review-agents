# llm-review-agents

Набор **независимо подключаемых AI-ревьюеров кода** — каждый ставится и настраивается
отдельно, работает локально и в CI. Выбери ревьюера и режим ниже.

## Ревьюеры

| Ревьюер | Что делает | Стек | Кому | Режимы |
|---|---|---|---|---|
| [**pr-agent**](reviewers/pr-agent/README.md) | Диффит ветку против базовой; команды `review` / `describe` / `improve` / `ask` | Python (uv) | Глубокое ревью, разные режимы | [Локально](reviewers/pr-agent/local.md) · [CI](reviewers/pr-agent/ci.md) |
| [**open-code-review**](reviewers/open-code-review/README.md) | Быстрый CLI; незакоммиченное / диапазоны / коммит; свои правила; JSON | Node (npm) | Быстро, скриптуемо, свои правила | [Локально](reviewers/open-code-review/local.md) · [CI](reviewers/open-code-review/ci.md) |

## Как выбрать

- **pr-agent** — глубокое ревью и набор команд (описать PR, предложить правки, задать
  вопрос диффу). LiteLLM под капотом — любой провайдер. Ставится глобально, зовётся в
  любом проекте.
- **open-code-review** — быстро и скриптуемо: JSON-вывод, `--audience agent`, ревью
  диапазона/одного коммита, свои правила на уровне репозитория.

Общий справочник провайдеров (DeepSeek / GLM / LM Studio / OpenAI / Anthropic) — один на
всех: [docs/providers.md](docs/providers.md).

## Быстрый старт

Самый короткий путь — open-code-review:

```bash
npm install -g @alibaba-group/open-code-review
ocr config set llm.url https://api.deepseek.com/chat/completions
ocr config set llm.auth_token sk-***
ocr config set llm.model deepseek-chat
ocr review
```

Или pr-agent (поставить глобально, потом звать в любом проекте):

```bash
bash reviewers/pr-agent/setup/central-setup.sh
# впиши ключ в ~/.config/pr-agent-review/config.env
pr_agent_review master review
```

## Режимы запуска

- **Локально** — на своей машине, руками. См. `local.md` каждого ревьюера.
- **В CI** — авто-ревью на PR/MR. Готовые файлы под GitHub / GitLab / Bitbucket / Jenkins
  в `ci/` каждого ревьюера, инструкции — в `ci.md`.
- **По комментарию** *(в разработке)* — тегнуть бота в PR (`@review.<name>`), и только
  тогда стартует ревью. Отдельный модуль `bot/` (подпроект SP2).

## Ещё

- [Справочник провайдеров](docs/providers.md)
- [Как добавить нового ревьюера](docs/add-a-reviewer.md)

## Структура

```
reviewers/<name>/   # самодостаточный ревьюер: README, local.md, ci.md, setup/, ci/
docs/               # общее: providers.md, add-a-reviewer.md
```
