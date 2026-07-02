# pr-agent — локальный запуск

Локальный запуск [pr-agent](https://github.com/qodo-ai/pr-agent): диффит твою ветку
против базовой, прогоняет через LLM и пишет ревью в `review.md` в корне репозитория.
**Без PR, без git-токена, наружу ничего не постится.** Под капотом — LiteLLM, поэтому
провайдер переключаемый (DeepSeek / GLM / LM Studio) — см. [справочник провайдеров](../../docs/providers.md).

Ставится **один раз глобально**, команда `pr_agent_review` доступна в **любом** проекте —
в коде проектов ничего не лежит.

---

## 1. Установка (один раз на машине)

```bash
bash reviewers/pr-agent/setup/central-setup.sh
```

Скрипт идемпотентный: ставит `uv` (если нет), ставит `pr-agent==0.36.1` как изолированный
глобальный uv-tool (**без клона репозитория**), кладёт конфиг в
`~/.config/pr-agent-review/config.env` (`chmod 600`) и команду `pr_agent_review` в
`~/.local/bin`. Повторный запуск не перетирает уже вписанные ключи.

> Если `~/.local/bin` не в `PATH` — добавь `export PATH="$HOME/.local/bin:$PATH"` в
> `~/.zshrc` (или выполни `uv tool update-shell`).

## 2. Конфигурация: выбрать провайдера и вписать ключ

Открой `~/.config/pr-agent-review/config.env` (эталон — [`setup/config.env.template`](setup/config.env.template)).
Раскомментирован **ровно один** провайдер, остальные — под `#`. По умолчанию активен
DeepSeek: впиши ключ вместо `ВСТАВЬ_СЮДА_DEEPSEEK_KEY`.

Маппинг провайдера в переменные окружения (эндпоинты и id моделей — в
[справочнике провайдеров](../../docs/providers.md)):

| Провайдер | Переменные |
|---|---|
| **DeepSeek** | `CONFIG__MODEL="deepseek/deepseek-v4-pro"` · `DEEPSEEK__KEY="sk-..."` |
| **GLM (z.ai)** | `CONFIG__MODEL="openai/glm-5.2"` · `OPENAI__API_BASE=".../api/coding/paas/v4"` · `OPENAI__KEY` · `CONFIG__CUSTOM_MODEL_MAX_TOKENS` · `CONFIG__DUPLICATE_EXAMPLES=true` |
| **LM Studio** | `CONFIG__MODEL="openai/<id-модели>"` · `OPENAI__API_BASE="http://localhost:1234/v1"` · `OPENAI__KEY="lm-studio"` · `CONFIG__CUSTOM_MODEL_MAX_TOKENS` · `CONFIG__DUPLICATE_EXAMPLES=true` |

Префикс `openai/` говорит LiteLLM использовать OpenAI-совместимый клиент и слать запросы
на `OPENAI__API_BASE`. Для GLM и LM Studio `custom_model_max_tokens` + `duplicate_examples`
**обязательны** (LiteLLM не знает их окно/формат). Сменить провайдера сразу для всех
проектов — отредактировать этот один файл.

## 3. Запуск ревью

В любом проекте, на ветке с коммитами и **чистым рабочим деревом**:

```bash
pr_agent_review master review     # ревью текущей ветки против master
cat review.md
```

`pr_agent_review [базовая-ветка] [команда]` (по умолчанию `master review`):

- База — **локальная** ветка (`git branch`), не только удалённая.
- Команды: `review` (по умолчанию), `describe`, `improve`, `ask "вопрос"`, `reflect`.
- Вывод: `review.md` (для `describe` — `description.md`) в корне репозитория; наружу ничего не постится.
- Какой провайдер/модель активны — команда печатает строкой `>> ... model: ...` при запуске.

> Незакоммиченные правки команда сама временно прячет в `stash` и возвращает после (даже
> при ошибке/Ctrl-C). В дифф попадает только закоммиченное (HEAD vs merge-base с базой).

## 4. Подводные камни

- **Пустой diff.** Нужны коммиты, которых нет в базовой ветке. На голом `master` ревьюить нечего.
- **Чистое дерево.** Команда автостэшит отслеживаемые правки; при **прямом** вызове
  `pr-agent` (без обёртки) — сначала `git commit`/`git stash`, иначе
  `The repository is not in a clean state`.
- **Размер диффа vs контекст.** Большой diff + маленькая локальная модель → pr-agent
  сжимает дифф, качество падает. Для крупных ревью — DeepSeek/GLM.
- **`custom_model_max_tokens` + `duplicate_examples`** обязательны для GLM и LM Studio.
  Плюс глобальный кап `max_model_tokens` (дефолт 32000) режет вход через `min(...)` —
  подними `CONFIG__MAX_MODEL_TOKENS=<N>` (или `0` — снять), чтобы использовать большой контекст.
- **Не работает в `git worktree`.** Провайдер ищет каталог с `.git`-**директорией**, а у
  линкованного worktree `.git` — файл-указатель. Запускай в обычном рабочем дереве или полном клоне.

## 5. Обслуживание

```bash
uv tool upgrade pr-agent                          # обновить
uv tool uninstall pr-agent                        # удалить пакет
rm -f  ~/.local/bin/pr_agent_review               # + команду
rm -rf ~/.config/pr-agent-review                  # + конфиг с ключами
```

> Почему Python 3.12, а не системный: pr-agent закреплён на `litellm`, который требует
> Python `<3.14`. venv на 3.12 поднимается через `uv`, не трогая системный интерпретатор.

---

Встроить в пайплайн (комментит PR/MR автоматически) — см. [ci.md](ci.md).
Наверх — [обзор ревьюера](README.md) · [все ревьюеры](../../README.md).
