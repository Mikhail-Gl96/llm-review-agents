# Тулкит LLM-ревьюеров (SP1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Превратить черновые заметки в чистый навигируемый тулкит из двух независимо подключаемых AI-ревьюеров (pr-agent, open-code-review) с локальным запуском и готовыми CI-конфигами, с разводящей страницей в корневом README.

**Architecture:** Самодостаточные папки-модули `reviewers/<name>/` (обзор + `local.md` + `ci.md` + `setup/` + `ci/`). Общие факты о провайдерах — один раз в `docs/providers.md`. Корневой `README.md` — роутер. Расширяемость — `docs/add-a-reviewer.md`.

**Tech Stack:** Markdown; Bash (скрипты установки); YAML (GitHub Actions, GitLab CI, Bitbucket Pipelines); Groovy (Jenkinsfile); JSON (конфиги ocr). Ревьюеры: pr-agent (Python/uv/LiteLLM), open-code-review (Node/npm).

**Спецификация:** [SP1 design](../specs/2026-07-02-reviewers-toolkit-design.md). Связанный подпроект: [SP2 бот](../specs/2026-07-02-comment-triggered-review-bot-design.md) — не входит в этот план.

## Global Constraints

- **Язык всей документации — русский.**
- **pr-agent — только центральная установка** (глобальный `pr_agent_review`). In-project режим (venv+клон, `setup.sh`/`review.sh`) НЕ создаём.
- **`draft-notes/` не трогать** (пользователь удалит сам). Контент из неё **копировать/адаптировать**, а не перемещать.
- **Каждая папка `reviewers/<name>/` самодостаточна** — подключается независимо от других.
- **Факты о провайдерах живут один раз** в `docs/providers.md`; `local.md` каждого ревьюера ссылается на него и показывает лишь маппинг в свой формат конфига.
- **Корневой `README.md` — разводящая страница** (роутер), с неё за один клик в нужного ревьюера и режим.
- **Зафиксированная версия pr-agent:** `0.36.1`. **Python для pr-agent:** `3.12` (litellm требует `<3.14`).
- **Имена моделей (канон для документации):** DeepSeek `deepseek-chat` (дефолт) / `deepseek-reasoner`; GLM `glm-5.2` (+ `glm-5.2[1m]` — 1M контекст); LM Studio — id загруженной модели; OpenAI `gpt-5.5`; Anthropic `claude-opus-4-8`. Если провайдер сменил id — сверить с его докой на этапе исполнения.
- **Commit style:** заголовок на русском или английском по вкусу, тело — по необходимости; каждый таск завершается коммитом.

---

## Природа этого плана (важно)

Это **документация + скрипты + CI-конфиги**, а не приложение с юнит-тестами. Поэтому вместо TDD каждый таск идёт по циклу **Build → Verify → Commit**, где Verify — это линтеры/валидаторы и проверки структуры (см. «Verification toolbox»). Для prose-файлов дан **точный контент-спек** (обязательные секции + факты + файл-источник в `draft-notes/`, который адаптируем) — это не placeholder, а конкретное ТЗ на файл.

## Verification toolbox (переиспользуемые проверки)

- **VT-SHELL** — синтаксис bash: `bash -n <файл>`; плюс (если установлен) `shellcheck <файл>`. Ожидаемо: без ошибок. Если `shellcheck` нет — `brew install shellcheck` (опционально).
- **VT-YAML** — синтаксис YAML:
  ```bash
  python3 - "$@" <<'PY'
  import sys, glob, itertools
  try:
      import yaml
  except ImportError:
      sys.exit("PyYAML не установлен: python3 -m pip install --user pyyaml")
  files = list(itertools.chain.from_iterable(glob.glob(a, recursive=True) for a in sys.argv[1:]))
  for f in files:
      yaml.safe_load(open(f, encoding="utf-8"))
      print("OK", f)
  PY
  ```
  Для GitHub Actions дополнительно (если есть): `actionlint <файл>` (`brew install actionlint`).
- **VT-JSON** — синтаксис JSON: `python3 -m json.tool <файл> >/dev/null && echo OK`.
- **VT-LINKS** — все относительные markdown-ссылки указывают на существующие файлы (скрипт приведён в Task 6, Step L).
- **VT-TREE** — структура на месте: `test -f <path> && echo OK` или `find reviewers docs -type f`.

## File Structure (что создаём)

```
README.md                                   # роутер (Task 6)
docs/
  providers.md                              # общий справочник провайдеров (Task 2)
  add-a-reviewer.md                         # как добавить ревьюера №3+ (Task 5)
reviewers/
  pr-agent/                                 # Task 3
    README.md  local.md  ci.md
    setup/central-setup.sh  setup/config.env.template
    ci/github-actions.yml  ci/gitlab-ci.yml  ci/bitbucket-pipelines.yml  ci/Jenkinsfile
  open-code-review/                         # Task 4
    README.md  local.md  ci.md
    setup/config.example.json  setup/rule.example.json
    ci/github-actions.yml  ci/gitlab-ci.yml  ci/bitbucket-pipelines.yml  ci/Jenkinsfile
```

## Before you start

Мы на дефолтной ветке `main`. Создать рабочую ветку:

```bash
git switch -c feature/reviewers-toolkit
```

---

## Task 1: Скелет репозитория + перенос central-setup.sh

**Files:**
- Create (dirs): `docs/`, `reviewers/pr-agent/setup/`, `reviewers/pr-agent/ci/`, `reviewers/open-code-review/setup/`, `reviewers/open-code-review/ci/`
- Create: `reviewers/pr-agent/setup/central-setup.sh` (копия из `draft-notes/pr-agent/central-setup.sh`)

**Interfaces:**
- Produces: рабочая структура папок; путь `reviewers/pr-agent/setup/central-setup.sh` (на него ссылаются Task 3 и README).

- [ ] **Step 1: Создать дерево папок**

```bash
mkdir -p docs reviewers/pr-agent/setup reviewers/pr-agent/ci \
         reviewers/open-code-review/setup reviewers/open-code-review/ci
```

- [ ] **Step 2: Скопировать central-setup.sh (draft-notes не трогаем)**

```bash
cp draft-notes/pr-agent/central-setup.sh reviewers/pr-agent/setup/central-setup.sh
chmod +x reviewers/pr-agent/setup/central-setup.sh
```

- [ ] **Step 3: Verify** — VT-SHELL на скопированный скрипт + VT-TREE.

```bash
bash -n reviewers/pr-agent/setup/central-setup.sh && echo "shell OK"
command -v shellcheck >/dev/null && shellcheck reviewers/pr-agent/setup/central-setup.sh || echo "shellcheck пропущен"
find reviewers docs -type d
```
Ожидаемо: `shell OK`, дерево из 6+ папок, `draft-notes/` без изменений (`git status` — только новые файлы).

- [ ] **Step 4: Commit**

```bash
git add reviewers docs
git commit -m "chore: скелет тулкита + перенос central-setup.sh"
```

---

## Task 2: Общий справочник провайдеров `docs/providers.md`

**Files:**
- Create: `docs/providers.md`

**Interfaces:**
- Produces: `docs/providers.md` — единственный источник фактов о провайдерах; на него ссылаются `local.md` обоих ревьюеров и корневой README.

**Источник:** `draft-notes/models.md` + факты из `draft-notes/pr-agent/README.md` (§3) и `draft-notes/opencodereview.md`.

- [ ] **Step 1: Написать `docs/providers.md`**

Обязательное содержимое:

1. Вводная строка: «Единый справочник LLM-провайдеров для всех ревьюеров. Каждый ревьюер в своём `local.md` показывает, как вписать провайдера в его формат конфига.»
2. **Таблица провайдеров** (столбцы: Провайдер | Эндпоинт | Модель | Нюансы):

| Провайдер | Эндпоинт | Модель | Нюансы |
|---|---|---|---|
| **DeepSeek** | `https://api.deepseek.com` (chat: `/chat/completions`) | `deepseek-chat` (дефолт) / `deepseek-reasoner` | `use_anthropic=false`; для pr-agent доп. настроек не нужно |
| **GLM (z.ai)** | Coding Plan: `https://api.z.ai/api/coding/paas/v4` · pay-as-you-go: `https://api.z.ai/api/paas/v4` (материк: `https://open.bigmodel.cn/api/paas/v4`) | `glm-5.2` (reasoning; `glm-5.2[1m]` — 1M) | thinking off; **не перепутать эндпоинт** (иначе `Insufficient balance`); для pr-agent нужны `custom_model_max_tokens`+`duplicate_examples` |
| **LM Studio** (офлайн) | `http://localhost:1234/v1` | id загруженной модели | ключ любой непустой (`lm-studio`); сначала Developer → Start Server; для pr-agent нужны `custom_model_max_tokens`+`duplicate_examples` |
| **OpenAI** | `https://api.openai.com/v1` | `gpt-5.5` | `use_anthropic=false` |
| **Anthropic** | `https://api.anthropic.com/v1/messages` | `claude-opus-4-8` | `use_anthropic=true` |

3. **Блок «Нюанс GLM-эндпоинта»** (важно, вынести отдельно): Coding Plan биллится с подписки → coding-эндпоинт; pay-as-you-go → обычный. Перепутал → `RateLimitError: Insufficient balance or no resource package`.
4. **Блок «Reasoning-модели»**: `glm-5.2`, `deepseek-reasoner` тратят токены на thinking; при своих тестах поднимать `max_tokens`; для отключения thinking у ocr — `llm.extra_body '{"thinking":{"type":"disabled"}}'`.
5. **Ссылка вперёд:** «Как подключить провайдера к конкретному ревьюеру — см. `reviewers/<name>/local.md`.»

- [ ] **Step 2: Verify** — VT-LINKS (внутренние ссылки), проверка что файл непустой и содержит все 5 провайдеров:

```bash
grep -c -E 'DeepSeek|GLM|LM Studio|OpenAI|Anthropic' docs/providers.md   # ожидаемо >=5
```

- [ ] **Step 3: Commit**

```bash
git add docs/providers.md
git commit -m "docs: общий справочник провайдеров"
```

---

## Task 3: Модуль pr-agent (docs + скрипты + CI)

Самодостаточная папка `reviewers/pr-agent/`. Порядок шагов: сначала code-файлы (шаблон + 4 CI-файла) с проверкой, потом prose (`local.md`, `ci.md`, `README.md`), потом локальная проверка ссылок и коммит.

**Files:**
- Create: `reviewers/pr-agent/setup/config.env.template`
- Create: `reviewers/pr-agent/ci/github-actions.yml`, `.../gitlab-ci.yml`, `.../bitbucket-pipelines.yml`, `.../Jenkinsfile`
- Create: `reviewers/pr-agent/local.md`, `.../ci.md`, `.../README.md`

**Interfaces:**
- Consumes: `reviewers/pr-agent/setup/central-setup.sh` (Task 1), `docs/providers.md` (Task 2).
- Produces: ссылки-цели для корневого README (`reviewers/pr-agent/README.md`, `local.md`, `ci.md`).

- [ ] **Step 1: `setup/config.env.template`** (эталон конфига; тот же контент, что генерирует `central-setup.sh`)

```bash
# ~/.config/pr-agent-review/config.env
# Конфиг локального AI-ревьюера. Раскомментирован РОВНО ОДИН провайдер.
# Файл chmod 600 — храни ключи только здесь, не в проектах.

# Глобальный кап на размер ВХОДА (все провайдеры). Дефолт pr-agent = 32000,
# режет через min(max_model_tokens, custom_model_max_tokens). Раскомментируй и
# подними, чтобы использовать большой контекст модели (0 = снять кап).
# export CONFIG__MAX_MODEL_TOKENS=1000000

# --- DeepSeek (по умолчанию) ---
export CONFIG__MODEL="deepseek/deepseek-chat"
export CONFIG__FALLBACK_MODELS='["deepseek/deepseek-chat"]'
export DEEPSEEK__KEY="ВСТАВЬ_СЮДА_DEEPSEEK_KEY"

# --- GLM (z.ai) ---
# export CONFIG__MODEL="openai/glm-5.2"
# export CONFIG__FALLBACK_MODELS='["openai/glm-5.2"]'
# export CONFIG__CUSTOM_MODEL_MAX_TOKENS=1000000
# export CONFIG__DUPLICATE_EXAMPLES=true
# # Coding Plan -> /api/coding/paas/v4 ; pay-as-you-go -> /api/paas/v4
# export OPENAI__API_BASE="https://api.z.ai/api/coding/paas/v4"
# export OPENAI__KEY="ВСТАВЬ_СЮДА_GLM_KEY"

# --- LM Studio (локально; сначала Start Server) ---
# export CONFIG__MODEL="openai/qwen/qwen3-coder-next"
# export CONFIG__FALLBACK_MODELS='["openai/qwen/qwen3-coder-next"]'
# export CONFIG__CUSTOM_MODEL_MAX_TOKENS=32768
# export CONFIG__DUPLICATE_EXAMPLES=true
# export OPENAI__API_BASE="http://localhost:1234/v1"
# export OPENAI__KEY="lm-studio"
```

- [ ] **Step 2: `ci/github-actions.yml`** — авто-ревью на PR (нативный режим pr-agent, комментит PR)

```yaml
# Автоматическое AI-ревью на каждый PR через pr-agent (комментит PR).
# Секреты репозитория (Settings → Secrets → Actions): DEEPSEEK_KEY (или ключ вашего провайдера).
# ВЕРИФИЦИРОВАТЬ перед прод-использованием: актуальный ref экшена и имена env — по докам pr-agent.
name: pr-agent review
on:
  pull_request:
    types: [opened, reopened, ready_for_review, synchronize]
permissions:
  contents: read
  pull-requests: write
  issues: write
jobs:
  pr_agent:
    if: ${{ github.event.sender.type != 'Bot' }}
    runs-on: ubuntu-latest
    steps:
      - name: PR Agent
        uses: qodo-ai/pr-agent@v0.36     # зафиксируй проверенный тег
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          CONFIG__MODEL: "deepseek/deepseek-chat"
          CONFIG__FALLBACK_MODELS: '["deepseek/deepseek-chat"]'
          DEEPSEEK__KEY: ${{ secrets.DEEPSEEK_KEY }}
```

- [ ] **Step 3: `ci/gitlab-ci.yml`** — авто-ревью на MR (CLI в job, комментит MR)

```yaml
# Авто AI-ревью на MR через pr-agent. Переменные CI/CD (Settings → CI/CD → Variables, masked):
#   DEEPSEEK_KEY, GITLAB_TOKEN (scope api, право комментить MR).
# ВЕРИФИЦИРОВАТЬ: точный вызов CLI/имена env — по докам pr-agent (git_provider=gitlab).
pr_agent_review:
  image: python:3.12-slim
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  variables:
    CONFIG__GIT_PROVIDER: "gitlab"
    CONFIG__MODEL: "deepseek/deepseek-chat"
    CONFIG__FALLBACK_MODELS: '["deepseek/deepseek-chat"]'
  script:
    - pip install "pr-agent==0.36.1"
    - export DEEPSEEK__KEY="$DEEPSEEK_KEY"
    - export GITLAB__PERSONAL_ACCESS_TOKEN="$GITLAB_TOKEN"
    - python -m pr_agent.cli --pr_url "${CI_PROJECT_URL}/-/merge_requests/${CI_MERGE_REQUEST_IID}" review
```

- [ ] **Step 4: `ci/bitbucket-pipelines.yml`** — авто-ревью на PR

```yaml
# Авто AI-ревью через pr-agent в Bitbucket Pipelines.
# Repository variables (secured): DEEPSEEK_KEY, BITBUCKET_TOKEN (app password с правом на PR).
# ВЕРИФИЦИРОВАТЬ: имена env для bitbucket-провайдера — по докам pr-agent.
pipelines:
  pull-requests:
    '**':
      - step:
          name: pr-agent review
          image: python:3.12-slim
          script:
            - pip install "pr-agent==0.36.1"
            - export CONFIG__GIT_PROVIDER="bitbucket"
            - export CONFIG__MODEL="deepseek/deepseek-chat"
            - export CONFIG__FALLBACK_MODELS='["deepseek/deepseek-chat"]'
            - export DEEPSEEK__KEY="$DEEPSEEK_KEY"
            - export BITBUCKET__BEARER_TOKEN="$BITBUCKET_TOKEN"
            - python -m pr_agent.cli --pr_url "https://bitbucket.org/$BITBUCKET_WORKSPACE/$BITBUCKET_REPO_SLUG/pull-requests/$BITBUCKET_PR_ID" review
```

- [ ] **Step 5: `ci/Jenkinsfile`** — авто-ревью (обобщённый рецепт «CLI на раннере»)

```groovy
// Авто AI-ревью через pr-agent на Jenkins. Credentials (Secret text):
//   DEEPSEEK_KEY, и токен провайдера git (напр. GITLAB_TOKEN) при постинге в MR/PR.
// ВЕРИФИЦИРОВАТЬ: git_provider и pr_url под вашу систему по докам pr-agent.
pipeline {
  agent { docker { image 'python:3.12-slim' } }
  environment {
    DEEPSEEK__KEY        = credentials('DEEPSEEK_KEY')
    CONFIG__MODEL        = 'deepseek/deepseek-chat'
    CONFIG__FALLBACK_MODELS = '["deepseek/deepseek-chat"]'
  }
  stages {
    stage('pr-agent review') {
      steps {
        sh 'pip install "pr-agent==0.36.1"'
        sh 'python -m pr_agent.cli --pr_url "$CHANGE_URL" review'   // CHANGE_URL = URL PR/MR
      }
    }
  }
}
```

- [ ] **Step 6: Verify code-файлов** — VT-YAML на три `.yml`, VT-SHELL/визуальная проверка Jenkinsfile (Groovy линтуется только Jenkins'ом — достаточно валидного YAML у остальных и ручного просмотра):

```bash
python3 - reviewers/pr-agent/ci/github-actions.yml reviewers/pr-agent/ci/gitlab-ci.yml reviewers/pr-agent/ci/bitbucket-pipelines.yml <<'PY'
import sys, yaml
for f in sys.argv[1:]:
    yaml.safe_load(open(f, encoding="utf-8")); print("OK", f)
PY
command -v actionlint >/dev/null && actionlint reviewers/pr-agent/ci/github-actions.yml || echo "actionlint пропущен"
```

- [ ] **Step 7: `local.md`** — локальный гайд (центральная установка)

Источник для адаптации: `draft-notes/pr-agent/DEVELOPER_GUIDE.md` (раздел «Способ A»), `draft-notes/pr-agent/README.md` (§2 «Запуск ревью», §3 «Переключение провайдера», «Подводные камни», «Обслуживание»). Обязательные секции:

1. **Что это** — pr-agent локально диффит ветку против базовой → `review.md`, без PR/токена; провайдер переключаемый (LiteLLM). Ссылка на `../../docs/providers.md`.
2. **Установка (один раз):** `bash reviewers/pr-agent/setup/central-setup.sh` → ставит `uv`, pr-agent==0.36.1 как глобальный uv-tool (без клона), конфиг `~/.config/pr-agent-review/config.env` (chmod 600), команду `pr_agent_review` в `~/.local/bin`. Идемпотентно.
3. **Конфиг:** вписать ключ в `~/.config/pr-agent-review/config.env` (шаблон — `setup/config.env.template`, раскомментирован один провайдер). Маппинг провайдеров в env — таблицей: DeepSeek (`CONFIG__MODEL="deepseek/deepseek-chat"` + `DEEPSEEK__KEY`), GLM (`openai/glm-5.2` + `OPENAI__API_BASE` + `OPENAI__KEY` + `CUSTOM_MODEL_MAX_TOKENS` + `DUPLICATE_EXAMPLES`), LM Studio (аналогично, `api_base=http://localhost:1234/v1`). Факты про эндпоинты — ссылка на `providers.md`, не дублировать.
4. **Запуск:** `pr_agent_review [база] [команда]` (дефолт `master review`); на ветке с коммитами и **чистым деревом** (wrapper авто-стэшит tracked-правки и возвращает). Команды: `review`, `describe`, `improve`, `ask "вопрос"`, `reflect`. Вывод — `review.md`/`description.md` в корне.
5. **Подводные камни** (перечислить все 5 из README): пустой diff; чистое дерево; размер диффа vs контекст; `custom_model_max_tokens`+`duplicate_examples` обязательны для GLM/LM Studio; не работает в `git worktree`; кап `max_model_tokens=32000` (поднять `CONFIG__MAX_MODEL_TOKENS`).
6. **Обслуживание:** `uv tool upgrade pr-agent`; удаление (`uv tool uninstall pr-agent` + чистка `~/.local/bin/pr_agent_review` и `~/.config/pr-agent-review/`). Почему Python 3.12.

- [ ] **Step 8: `ci.md`** — интеграция в CI

Новый контент (в заметках CI не было). Обязательные секции:

1. **Ключевое отличие от локали:** в CI pr-agent работает в **нативном режиме — комментит PR/MR** (нужен git-токен + ключ модели в secrets), в отличие от локального файлового `review.md`. Таблица «локально vs CI».
2. **Секреты** (по платформам): ключ провайдера (`DEEPSEEK_KEY`/…) + git-токен (GitHub — встроенный `GITHUB_TOKEN` c `pull-requests: write`; GitLab — PAT scope `api`; Bitbucket — app password).
3. **Готовые файлы:** ссылки на `ci/github-actions.yml`, `ci/gitlab-ci.yml`, `ci/bitbucket-pipelines.yml`, `ci/Jenkinsfile` + для каждой платформы 1–2 строки «куда положить и какие переменные завести».
4. **Верификация:** явно предупредить, что ref экшена/имена env стоит сверить с актуальными доками pr-agent (быстро дрейфует).
5. **Замечание про режим «по комментарию»:** для «тегнуть бота → тогда ревью» см. отдельный модуль `bot/` (SP2), это другой режим.

- [ ] **Step 9: `README.md` модуля** — обзор + навигация

Короткий (обзор в 3–4 строки: что такое pr-agent, кому подходит — богатые команды, дифф ветки против базовой) + навигация: ссылки на `local.md`, `ci.md`, `setup/`, `../../docs/providers.md`, `../../README.md` (наверх).

- [ ] **Step 10: Verify модуля** — структура + локальные ссылки:

```bash
find reviewers/pr-agent -type f | sort
# все относительные ссылки из файлов pr-agent резолвятся (полный чек — Task 6)
grep -rEo '\]\([^)]+\)' reviewers/pr-agent/*.md | head -50
```
Ожидаемо: 9 файлов; ссылки на `local.md`/`ci.md`/`setup/…`/`ci/…`/`providers.md` — на существующие пути.

- [ ] **Step 11: Commit**

```bash
git add reviewers/pr-agent
git commit -m "feat(pr-agent): модуль — локальный гайд, CI-конфиги (4 платформы), шаблон конфига"
```

---

## Task 4: Модуль open-code-review (docs + конфиги + CI)

Самодостаточная папка `reviewers/open-code-review/`. Тот же порядок: code-файлы → prose → verify → commit.

**Files:**
- Create: `reviewers/open-code-review/setup/config.example.json`, `.../setup/rule.example.json`
- Create: `reviewers/open-code-review/ci/github-actions.yml`, `.../gitlab-ci.yml`, `.../bitbucket-pipelines.yml`, `.../Jenkinsfile`
- Create: `reviewers/open-code-review/local.md`, `.../ci.md`, `.../README.md`

**Interfaces:**
- Consumes: `docs/providers.md` (Task 2).
- Produces: ссылки-цели для корневого README.

**Источник:** `draft-notes/opencodereview.md` (весь), `draft-notes/models.md`.

- [ ] **Step 1: `setup/config.example.json`** — эталон `~/.opencodereview/config.json` (DeepSeek по умолчанию)

```json
{
  "llm": {
    "url": "https://api.deepseek.com/chat/completions",
    "auth_token": "ВСТАВЬ_СЮДА_DEEPSEEK_KEY",
    "model": "deepseek-chat",
    "use_anthropic": false
  }
}
```

- [ ] **Step 2: `setup/rule.example.json`** — пример своих правил (из `opencodereview.md`)

```json
{
  "rules": [
    { "path": "**/*.sql", "rule": "Проверяй SQL на инъекции" },
    { "path": "**/*.py",  "rule": "Требуй типизацию и докстринги у публичных функций" }
  ],
  "exclude": ["**/generated/**", "**/*.lock"]
}
```

- [ ] **Step 3: `ci/github-actions.yml`** — авто-ревью на PR (CLI на раннере + коммент через `gh`)

```yaml
# Авто AI-ревью на PR через open-code-review (ocr): CLI на раннере, результат — комментом.
# Секреты: DEEPSEEK_KEY (или ключ вашего провайдера).
# ВЕРИФИЦИРОВАТЬ: поддерживаемые --format/--audience — по докам ocr.
name: open-code-review
on:
  pull_request:
    types: [opened, reopened, synchronize]
permissions:
  contents: read
  pull-requests: write
jobs:
  ocr:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: npm install -g @alibaba-group/open-code-review
      - name: Настроить провайдера
        env: { DEEPSEEK_KEY: "${{ secrets.DEEPSEEK_KEY }}" }
        run: |
          ocr config set llm.url https://api.deepseek.com/chat/completions
          ocr config set llm.auth_token "$DEEPSEEK_KEY"
          ocr config set llm.model deepseek-chat
          ocr config set llm.use_anthropic false
      - name: Ревью
        run: ocr review --from "origin/${{ github.base_ref }}" --to "${{ github.event.pull_request.head.sha }}" --audience agent | tee review.md
      - name: Комментарий в PR
        env: { GH_TOKEN: "${{ secrets.GITHUB_TOKEN }}" }
        run: gh pr comment "${{ github.event.pull_request.number }}" --body-file review.md
```

- [ ] **Step 4: `ci/gitlab-ci.yml`** — авто-ревью на MR (CLI + коммент через `glab`)

```yaml
# Авто AI-ревью на MR через ocr. Переменные CI/CD (masked): DEEPSEEK_KEY, GITLAB_TOKEN (api).
ocr_review:
  image: node:20
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  script:
    - npm install -g @alibaba-group/open-code-review
    - ocr config set llm.url https://api.deepseek.com/chat/completions
    - ocr config set llm.auth_token "$DEEPSEEK_KEY"
    - ocr config set llm.model deepseek-chat
    - ocr config set llm.use_anthropic false
    - ocr review --from "origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME" --to "$CI_COMMIT_SHA" --audience agent | tee review.md
    - |
      curl -sS --request POST --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
        --data-urlencode "body@review.md" \
        "$CI_API_V4_URL/projects/$CI_PROJECT_ID/merge_requests/$CI_MERGE_REQUEST_IID/notes"
```

- [ ] **Step 5: `ci/bitbucket-pipelines.yml`** — авто-ревью на PR (CLI; результат в лог/артефакт)

```yaml
# Авто AI-ревью через ocr в Bitbucket Pipelines. Repository variables (secured): DEEPSEEK_KEY.
# Коммент в PR — опционально через Bitbucket REST API + app password (см. ci.md).
pipelines:
  pull-requests:
    '**':
      - step:
          name: open-code-review
          image: node:20
          script:
            - npm install -g @alibaba-group/open-code-review
            - ocr config set llm.url https://api.deepseek.com/chat/completions
            - ocr config set llm.auth_token "$DEEPSEEK_KEY"
            - ocr config set llm.model deepseek-chat
            - ocr config set llm.use_anthropic false
            - ocr review --from "origin/$BITBUCKET_PR_DESTINATION_BRANCH" --to "$BITBUCKET_COMMIT" --audience agent | tee review.md
          artifacts:
            - review.md
```

- [ ] **Step 6: `ci/Jenkinsfile`** — обобщённый рецепт

```groovy
// Авто AI-ревью через ocr на Jenkins. Credentials (Secret text): DEEPSEEK_KEY.
pipeline {
  agent { docker { image 'node:20' } }
  environment { DEEPSEEK_KEY = credentials('DEEPSEEK_KEY') }
  stages {
    stage('open-code-review') {
      steps {
        sh 'npm install -g @alibaba-group/open-code-review'
        sh 'ocr config set llm.url https://api.deepseek.com/chat/completions'
        sh 'ocr config set llm.auth_token "$DEEPSEEK_KEY"'
        sh 'ocr config set llm.model deepseek-chat'
        sh 'ocr config set llm.use_anthropic false'
        sh 'ocr review --from "origin/$CHANGE_TARGET" --to "$GIT_COMMIT" --audience agent | tee review.md'
      }
    }
  }
  post { always { archiveArtifacts artifacts: 'review.md', allowEmptyArchive: true } }
}
```

- [ ] **Step 7: Verify code-файлов** — VT-JSON на два json, VT-YAML на три yml:

```bash
python3 -m json.tool reviewers/open-code-review/setup/config.example.json >/dev/null && echo "config OK"
python3 -m json.tool reviewers/open-code-review/setup/rule.example.json  >/dev/null && echo "rule OK"
python3 - reviewers/open-code-review/ci/github-actions.yml reviewers/open-code-review/ci/gitlab-ci.yml reviewers/open-code-review/ci/bitbucket-pipelines.yml <<'PY'
import sys, yaml
for f in sys.argv[1:]:
    yaml.safe_load(open(f, encoding="utf-8")); print("OK", f)
PY
```

- [ ] **Step 8: `local.md`** — локальный гайд

Источник: `draft-notes/opencodereview.md`. Обязательные секции:

1. **Что это** — быстрый CLI-ревьюер: незакоммиченное / диапазоны / один коммит; свои правила; JSON-вывод. Ссылка на `../../docs/providers.md`.
2. **Установка (глобально):** `npm install -g @alibaba-group/open-code-review`, `ocr version`. (Опц. блок про `~/.npm-global` и PATH из заметок.) Упомянуть альтернативу «как плагин Claude Code» (ссылка на репо).
3. **Конфиг провайдера:** `ocr config set llm.url|auth_token|model|use_anthropic …` (один раз в `~/.opencodereview/config.json`; эталон — `setup/config.example.json`). Для thinking-моделей — `ocr config set llm.extra_body '{"thinking":{"type":"disabled"}}'`. Факты про эндпоинты — ссылка на `providers.md`.
4. **Запуск:** `ocr review` (незакоммиченное), `--from main --to HEAD`, `--commit abc123`, `--preview`, `--format json`. Флаги: `--concurrency N` (деф. 8), `--audience human|agent`, `--model`, `--rule`. Русский вывод: `ocr review --audience human --background "ревью проведи на русском языке"`.
5. **Свои правила:** `.opencodereview/rule.json` (эталон — `setup/rule.example.json`); приоритет `--rule` > `./.opencodereview/rule.json` > `~/.opencodereview/rule.json` > дефолты.
6. **Ссылки:** репо `https://github.com/alibaba/open-code-review`, флаги ревью, установка как CC-плагин.

- [ ] **Step 9: `ci.md`** — интеграция в CI

Обязательные секции:

1. **Модель работы в CI:** ocr — это CLI, нативного PR-commenting нет → паттерн «CLI на раннере»: прогнать `ocr review --from $BASE --to $HEAD`, вывод в лог/артефакт **или** коммент через API платформы (`gh`, `glab`/REST). Таблица «локально vs CI».
2. **Секреты:** ключ провайдера (`DEEPSEEK_KEY`/…); для постинга коммента — токен платформы (GitHub `GITHUB_TOKEN`; GitLab PAT `api`; Bitbucket app password).
3. **Готовые файлы:** ссылки на 4 файла в `ci/` + по строке «куда положить, какие переменные». Отметить: GitHub/GitLab примеры **постят коммент**, Bitbucket/Jenkins — кладут `review.md` в артефакты (коммент — опционально, как расширить).
4. **Верификация:** сверить поддерживаемые `--format/--audience` и точные CI-переменные ветки с актуальными доками ocr.

- [ ] **Step 10: `README.md` модуля** — обзор (что такое ocr, кому: быстрый CLI, свои правила, диапазоны) + навигация (`local.md`, `ci.md`, `setup/`, `../../docs/providers.md`, наверх).

- [ ] **Step 11: Verify модуля**

```bash
find reviewers/open-code-review -type f | sort   # ожидаемо 9 файлов
```

- [ ] **Step 12: Commit**

```bash
git add reviewers/open-code-review
git commit -m "feat(open-code-review): модуль — локальный гайд, CI-конфиги (4 платформы), примеры конфигов"
```

---

## Task 5: `docs/add-a-reviewer.md` (расширяемость)

**Files:**
- Create: `docs/add-a-reviewer.md`

**Interfaces:**
- Consumes: структура `reviewers/pr-agent/` как образец.
- Produces: ссылка-цель для корневого README.

- [ ] **Step 1: Написать гайд «Как добавить ревьюера №3»**

Обязательное содержимое:

1. **Принцип:** каждый ревьюер — самодостаточная папка `reviewers/<name>/`; добавление не трогает существующих.
2. **Шаги:**
   - Создать `reviewers/<name>/` со структурой: `README.md` (обзор+навигация), `local.md`, `ci.md`, `setup/` (скрипты/шаблоны конфигов), `ci/` (файлы под платформы).
   - Заполнить по образцу `reviewers/pr-agent/` (дать явную ссылку как на референс).
   - Провайдеры не дублировать — ссылаться на `../../docs/providers.md`, показывать только маппинг в конфиг своего инструмента.
   - Добавить строку в таблицу-навигатор корневого `README.md` (что делает / стек / кому / ссылки Локально·CI·По комментарию).
3. **Чек-лист готовности:** файлы на месте; скрипты проходят `bash -n`/`shellcheck`; CI-YAML валиден; относительные ссылки резолвятся (VT-LINKS); строка в README добавлена.
4. **Про бота (SP2):** чтобы новый ревьюер вызывался и «по комментарию», в боте добавляется адаптер + строка в реестре (ссылка на `../bot/README.md`, когда появится).

- [ ] **Step 2: Verify** — VT-LINKS + наличие ссылки на образец:

```bash
grep -q "reviewers/pr-agent" docs/add-a-reviewer.md && echo "референс на месте"
```

- [ ] **Step 3: Commit**

```bash
git add docs/add-a-reviewer.md
git commit -m "docs: гайд по добавлению нового ревьюера"
```

---

## Task 6: Разводящая страница (корневой `README.md`) + сквозная проверка навигации

Капстоун: все цели ссылок уже существуют (Tasks 2–5), поэтому здесь пишем роутер и прогоняем полный линк-чек.

**Files:**
- Modify: `README.md` (сейчас заглушка)

**Interfaces:**
- Consumes: все файлы из `reviewers/*` и `docs/*`.

- [ ] **Step 1: Переписать `README.md` как роутер**

Обязательное содержимое:

1. **Заголовок + одна строка:** «`llm-review-agents` — набор независимо подключаемых AI-ревьюеров кода: локально и в CI.»
2. **Таблица-навигатор:**

| Ревьюер | Что делает | Стек | Кому | Локально | CI |
|---|---|---|---|---|---|
| **pr-agent** | Дифф ветки против базовой; `review/describe/improve/ask` | Python/uv | Богатые команды, глубокое ревью | [local](reviewers/pr-agent/local.md) | [ci](reviewers/pr-agent/ci.md) |
| **open-code-review** | Быстрый CLI; диапазоны/коммиты; свои правила; JSON | Node/npm | Быстро, правила, скриптинг | [local](reviewers/open-code-review/local.md) | [ci](reviewers/open-code-review/ci.md) |

3. **«Как выбрать»:** 3–5 строк pr-agent vs ocr (глубина/команды vs скорость/правила/JSON).
4. **Быстрый старт:** самый короткий путь (ocr: `npm i -g …` → `ocr config set …` → `ocr review`; либо pr-agent: `bash reviewers/pr-agent/setup/central-setup.sh` → вписать ключ → `pr_agent_review master review`).
5. **Общие темы:** ссылки на [Провайдеры](docs/providers.md) и [Добавить ревьюера](docs/add-a-reviewer.md).
6. **Третий режим (по комментарию):** строка-заглушка «Ревью по тегу бота в PR — модуль `bot/` (см. SP2), появится отдельно» (без битой ссылки, пока `bot/` нет — обычный текст, не markdown-ссылка).
7. **Структура репозитория:** короткое дерево `reviewers/` + `docs/`.

- [ ] **Step L: Сквозной линк-чек (VT-LINKS)** — все относительные ссылки во всех .md резолвятся:

```bash
python3 <<'PY'
import re, pathlib, sys
root = pathlib.Path(".")
bad = []
for md in root.rglob("*.md"):
    if "draft-notes" in md.parts or ".git" in md.parts:
        continue
    text = md.read_text(encoding="utf-8")
    for m in re.finditer(r'\]\(([^)]+)\)', text):
        link = m.group(1).split('#')[0].strip()
        if not link or link.startswith(('http://','https://','mailto:')):
            continue
        target = (md.parent / link).resolve()
        if not target.exists():
            bad.append(f"{md}: -> {link}")
print("БИТЫЕ ССЫЛКИ:" if bad else "Все ссылки OK")
print("\n".join(bad))
sys.exit(1 if bad else 0)
PY
```
Ожидаемо: `Все ссылки OK`, exit 0. Битые — починить и перезапустить.

- [ ] **Step 2: Verify структуры целиком**

```bash
find README.md docs reviewers -type f | sort
```
Ожидаемо: корневой README + `docs/providers.md` + `docs/add-a-reviewer.md` + по 9 файлов в каждом ревьюере.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: разводящая страница (роутер) + сквозная навигация"
```

---

## Self-Review (выполнено при написании плана)

**Покрытие спека SP1:**
- §4 структура → Task 1 (скелет) + Tasks 3–6 (файлы). ✓
- §5 разводящая страница → Task 6. ✓
- §6 pr-agent (central-only, команды, подводные камни, CI native) → Task 3. ✓
- §7 open-code-review (CLI, правила, флаги, CI «CLI на раннере») → Task 4. ✓
- §8 providers.md (5 провайдеров, GLM-эндпоинт, thinking) → Task 2. ✓
- §9 add-a-reviewer → Task 5. ✓
- §10 открытые техвопросы → вшиты как «ВЕРИФИЦИРОВАТЬ» в Tasks 3–4 (ref экшенов, env, format) и нормализация имён моделей в Global Constraints + Task 2. ✓
- Global: draft-notes не трогаем (Task 1 — `cp`, не `mv`); pr-agent central-only (нет setup.sh/review.sh); RU-язык. ✓

**Placeholder-скан:** prose-файлы заданы конкретными контент-спеками (секции+факты+источник), не «TBD». CI-файлы даны полным содержимым; помечены точечные «ВЕРИФИЦИРОВАТЬ» — это осознанные проверки актуального синтаксиса, не заглушки.

**Согласованность типов/имён:** пути файлов и имена (`central-setup.sh`, `config.env.template`, `config.example.json`, `rule.example.json`, `CONFIG__MODEL`, `deepseek-chat`, `glm-5.2`) консистентны между Tasks 1–6 и спеком.
