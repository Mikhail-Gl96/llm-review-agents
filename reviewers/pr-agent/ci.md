# pr-agent — интеграция в CI

В CI pr-agent работает в **нативном режиме — комментирует PR/MR** (в отличие от
локального файлового `review.md`). Для этого нужен git-токен (право писать комментарии)
и ключ модели — оба кладутся в secrets CI.

## Локально vs CI

| | Локально | В CI |
|---|---|---|
| git-провайдер | `local` | `github` / `gitlab` / `bitbucket` |
| Результат | файл `review.md` | комментарий в PR/MR |
| Токен git | не нужен | нужен (право на комментарий) |
| Триггер | руками `pr_agent_review` | событие PR/MR |

## Секреты

- **Ключ провайдера** — `DEEPSEEK_KEY` (или ключ вашего провайдера из [справочника](../../docs/providers.md)).
- **Git-токен:**
  - GitHub — встроенный `GITHUB_TOKEN` с правом `pull-requests: write` (задаётся в workflow).
  - GitLab — Personal/Project Access Token, scope `api`.
  - Bitbucket — app password с доступом к PR.

## Готовые файлы

| Платформа | Файл | Куда положить | Переменные |
|---|---|---|---|
| GitHub Actions | [`ci/github-actions.yml`](ci/github-actions.yml) | `.github/workflows/` | `DEEPSEEK_KEY` (secret); `GITHUB_TOKEN` — встроенный |
| GitLab CI | [`ci/gitlab-ci.yml`](ci/gitlab-ci.yml) | включить в `.gitlab-ci.yml` | `DEEPSEEK_KEY`, `GITLAB_TOKEN` (masked) |
| Bitbucket | [`ci/bitbucket-pipelines.yml`](ci/bitbucket-pipelines.yml) | `bitbucket-pipelines.yml` | `DEEPSEEK_KEY`, `BITBUCKET_TOKEN` (secured) |
| Jenkins | [`ci/Jenkinsfile`](ci/Jenkinsfile) | корень репо / pipeline job | credentials `DEEPSEEK_KEY` (+ git-токен) |

Провайдера меняешь заменой `CONFIG__MODEL`/ключа в env файла (аналогично локальному
конфигу — см. [local.md](local.md)).

## Верификация перед прод-использованием

Экшены и имена переменных pr-agent **дрейфуют между версиями**. Перед боевым запуском
сверь с актуальной докой pr-agent:

- ref GitHub Action (`qodo-ai/pr-agent@<tag>`) — зафиксируй проверенный тег;
- точные имена env для `git_provider` (`GITLAB__PERSONAL_ACCESS_TOKEN`,
  `BITBUCKET__BEARER_TOKEN` и т.п.) и формат `--pr_url`.

## Режим «по комментарию»

Если нужно, чтобы ревью стартовало **только когда тегнешь бота в комментарии PR**
(`@review.pr.agent`) — это отдельный режим (бот-диспетчер), см. модуль `bot/`
(подпроект SP2), а не этот авто-режим.

---

Локальный запуск — [local.md](local.md) · обзор — [README.md](README.md) · [все ревьюеры](../../README.md).
