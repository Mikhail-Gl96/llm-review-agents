# Спецификация: тулкит LLM-ревьюеров кода (`llm-review-agents`)

Дата: 2026-07-02
Статус: на согласовании

## 1. Контекст и цель

Репозиторий должен стать **набором из N>1 независимых AI-ревьюеров кода**. Сейчас
вся суть лежит в `draft-notes/` как черновые заметки; корневой `README.md` — заглушка.
В заметках описаны два готовых ревьюера и общий справочник моделей.

Цель — превратить наработки в **чистый, хорошо навигируемый тулкит**: разводящая
страница в корне, самодостаточные модули-ревьюеры, рабочие скрипты и готовые CI-файлы.

## 2. Требования

1. **N независимо подключаемых ревьюеров.** Каждый ревьюер — самодостаточный модуль,
   который можно настроить и подключить отдельно от других. Нужна и группировка, и
   индивидуальная настройка каждого.
2. **Локально и в CI.** Каждый ревьюер настраивается как для локального запуска, так и
   для встраивания в пайплайн: GitHub Actions, GitLab CI, Bitbucket Pipelines, Jenkins/прочее.
3. **Разводящая страница.** Корневой `README.md` — точка входа, из которой за один клик
   попадаешь в нужного ревьюера и нужный режим.

Язык всей документации — **русский**.

## 3. Не входит в объём (YAGNI)

- **In-project режим pr-agent** (venv+клон внутри репо, `setup.sh`/`review.sh`,
  `.secrets.template.toml`). Оставляем только центральную/глобальную установку —
  «поставил в систему один раз, вызываешь в любом проекте».
- **Docs-сайт (mkdocs и т.п.).** Навигация — обычным Markdown и ссылками.
- **Удаление `draft-notes/`.** Оставляем как есть, пользователь уберёт сам.

## 4. Архитектура: структура репозитория

Принцип — **самодостаточная папка на каждого ревьюера**. Хочешь подключить одного —
берёшь одну папку `reviewers/<name>/`, в ней есть всё: обзор, локальный гайд, CI-гайд,
скрипты и CI-файлы. Общие факты (провайдеры) — отдельно в `docs/`, чтобы не дублировать.

```
README.md                      # 🧭 разводящая страница (роутинг + выбор ревьюера)
docs/
  providers.md                 # общий справочник LLM-провайдеров
  add-a-reviewer.md            # как добавить ревьюера №3+ (расширяемость N)
reviewers/
  pr-agent/
    README.md                  # обзор ревьюера + навигация
    local.md                   # локально: установка, конфиг, запуск, траблшутинг
    ci.md                      # CI: как встроить, секреты, ссылки на ci/*
    setup/
      central-setup.sh         # (перенос существующего) глобальная установка
      config.env.template      # референс-шаблон конфига провайдеров
    ci/
      github-actions.yml
      gitlab-ci.yml
      bitbucket-pipelines.yml
      Jenkinsfile
  open-code-review/
    README.md
    local.md
    ci.md
    setup/
      config.example.json      # ~/.opencodereview/config.json
      rule.example.json        # .opencodereview/rule.json
    ci/
      github-actions.yml
      gitlab-ci.yml
      bitbucket-pipelines.yml
      Jenkinsfile
draft-notes/                   # оставляем как есть
docs/superpowers/specs/        # этот и будущие спек-файлы
```

Единый шаблон трёх md-файлов (`README`=обзор+навигация, `local.md`=локаль, `ci.md`=CI)
делает добавление ревьюера №3 механическим — копируешь структуру.

## 5. Компонент: разводящая страница (корневой `README.md`)

Требование №3. Содержимое:

- Одна строка «что это».
- **Таблица-навигатор**: ревьюер → что делает → стек → кому подходит → ссылки
  «Локально» / «CI».
- Блок **«Как выбрать»**: pr-agent (диффит ветку против базовой, богатые команды
  `review/describe/improve/ask`) vs open-code-review (быстрый CLI, свои правила,
  диапазоны коммитов, JSON-вывод).
- **Быстрый старт** — самый короткий путь до первого ревью.
- Ссылки на общие темы: `docs/providers.md`, `docs/add-a-reviewer.md`.
- Ссылка на **третий режим — бот по комментарию** (`bot/`, отдельный подпроект
  [SP2](2026-07-02-comment-triggered-review-bot-design.md)): в навигаторе у ревьюеров,
  помимо «Локально»/«CI», появляется «По комментарию».

## 6. Компонент: pr-agent

Источник: [qodo-ai/pr-agent](https://github.com/qodo-ai/pr-agent). Python 3.12
(litellm требует `<3.14`), ставится через `uv`. Под капотом LiteLLM → провайдер
переключаемый.

**Локально (`local.md`):** центральная установка (`central-setup.sh` → глобальная
команда `pr_agent_review`, конфиг `~/.config/pr-agent-review/config.env`, chmod 600).
Диффит `HEAD` против базовой ветки, git-провайдер `local`, пишет в `review.md` /
`description.md`, наружу ничего не постит. Команды: `review` (дефолт), `describe`,
`improve`, `ask "вопрос"`, `reflect`. Wrapper авто-стэшит отслеживаемые правки.
Раздел «Подводные камни» переносим из заметок: пустой diff, чистое дерево, не работает
в `git worktree`, `custom_model_max_tokens`+`duplicate_examples` для GLM/LM Studio,
кап `max_model_tokens=32000`.

**Артефакты:** перенести `central-setup.sh`; вынести шаблон конфига в
`config.env.template` (эталон для документации; сам скрипт может генерировать его
инлайном, как сейчас).

**CI (`ci.md` + `ci/`):** у pr-agent есть **нативный** режим комментирования PR/MR
(GitHub Action, GitLab, Bitbucket). В CI это принципиально иной режим, чем локально:
нужен git-токен (комментит PR) + ключ модели в secrets. Готовые файлы под 4 платформы.

## 7. Компонент: open-code-review (ocr)

Источник: [alibaba/open-code-review](https://github.com/alibaba/open-code-review).
Node/npm, `npm install -g @alibaba-group/open-code-review`, команда `ocr`.

**Локально (`local.md`):** глобальная установка через npm; конфиг
`~/.opencodereview/config.json` (`llm.url`, `llm.auth_token`, `llm.model`,
`llm.use_anthropic`, `llm.extra_body` для отключения thinking). Команды: `ocr review`
(незакоммиченное), `--from/--to` (диапазон), `--commit`, `--preview`, `--format json`.
Флаги: `--concurrency`, `--audience human|agent`, `--model`, `--rule`, `--background`
(в т.ч. «ревью на русском»). Свои правила — `.opencodereview/rule.json` (пример в
`setup/rule.example.json`), приоритет `--rule` > `./.opencodereview/rule.json` >
`~/.opencodereview/rule.json` > дефолты. Упомянуть также вариант «как плагин Claude Code».

**Артефакты:** `config.example.json`, `rule.example.json`.

**CI (`ci.md` + `ci/`):** ocr — это CLI, нативного PR-commenting может не быть →
паттерн «CLI на раннере»: `ocr review --from $BASE --to $HEAD --format json`, вывод в
лог/артефакт, опционально коммент через `gh`/`glab`. Готовые файлы под 4 платформы.

## 8. Компонент: общий справочник провайдеров (`docs/providers.md`)

Единый канонический источник фактов; каждый ревьюер в своём `local.md` показывает, как
вписать провайдера в **свой** формат (pr-agent = env `CONFIG__*`/`DEEPSEEK__*`/`OPENAI__*`;
ocr = `config.json`). Провайдеры и ключевые факты:

- **DeepSeek** — `https://api.deepseek.com`, модель `deepseek-chat`/`deepseek-reasoner`,
  `use_anthropic=false`. Для pr-agent доп. настройки не нужны.
- **GLM (z.ai)** — модель `glm-5.2` (reasoning; есть `glm-5.2[1m]` — 1M контекст),
  thinking off. **Нюанс эндпоинта:** Coding Plan → `https://api.z.ai/api/coding/paas/v4`;
  pay-as-you-go → `https://api.z.ai/api/paas/v4` (материк: `open.bigmodel.cn/api/paas/v4`).
  Путаница даёт `Insufficient balance`.
- **LM Studio** (офлайн) — `http://localhost:1234/v1`, модель = id загруженной,
  ключ любой непустой. Требует `custom_model_max_tokens`+`duplicate_examples` в pr-agent.
- **OpenAI** — `https://api.openai.com/v1`, `gpt-5.5`, `use_anthropic=false`.
- **Anthropic** — `https://api.anthropic.com/v1/messages`, `claude-opus-4-8`,
  `use_anthropic=true`.

## 9. Компонент: расширяемость (`docs/add-a-reviewer.md`)

Короткий гайд «как добавить ревьюера №3»: скопировать шаблон папки, заполнить
`README/local/ci`, положить скрипты и CI-файлы, добавить строку в таблицу-навигатор
корневого README. Закрепляет требование №1 (N расширяемо).

## 10. Открытые технические вопросы (проверить при написании)

- Актуальные версии/имена нативной **GitHub Action** и настроек GitLab/Bitbucket у
  pr-agent; точные имена секретов (git-токен, ключ модели).
- Есть ли у **ocr** нативный PR-commenting под какие-либо платформы, или везде паттерн
  «CLI + коммент через `gh`/`glab`».
- **Разнобой имён моделей** в заметках (`deepseek-chat` vs `deepseek-v4-pro`;
  `qwen2.5-coder-32b` vs `qwen3-coder-next`; `glm-5.2`) — нормализовать к одному набору.

## 11. Этапы реализации

1. Скелет папок + корневой `README.md`-навигатор.
2. `docs/providers.md` (консолидация `models.md` + разбросанных фактов).
3. **pr-agent**: `README/local/ci` + перенос `central-setup.sh` + `config.env.template` + 4 CI-файла.
4. **open-code-review**: `README/local/ci` + `config.example.json`/`rule.example.json` + 4 CI-файла.
5. `docs/add-a-reviewer.md` + финальная вычитка навигации.
