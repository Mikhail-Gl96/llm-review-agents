# open-code-review (ocr) — интеграция в CI

ocr — это CLI, нативного PR-commenting у него нет. В CI работает по паттерну
**«CLI на раннере»**: прогнать `ocr review --from <base> --to <head>`, а результат либо
оставить в логе/артефакте, либо запостить комментом через API платформы (`gh`, `glab`/REST).

## Локально vs CI

| | Локально | В CI |
|---|---|---|
| Запуск | руками `ocr review` | job на событие PR/MR |
| Результат | вывод в терминал | лог/артефакт `review.md` **или** комментарий в PR/MR |
| Постинг коммента | — | через API платформы (`gh` / `glab` / REST) |

## Секреты

- **Ключ провайдера** — `DEEPSEEK_KEY` (или ключ вашего провайдера из [справочника](../../docs/providers.md)).
- **Токен платформы** (только если постим коммент): GitHub `GITHUB_TOKEN`; GitLab PAT scope `api`; Bitbucket app password.

## Готовые файлы

| Платформа | Файл | Куда положить | Что делает |
|---|---|---|---|
| GitHub Actions | [`ci/github-actions.yml`](ci/github-actions.yml) | `.github/workflows/` | ревью → **комментарий** в PR (`gh pr comment`) |
| GitLab CI | [`ci/gitlab-ci.yml`](ci/gitlab-ci.yml) | включить в `.gitlab-ci.yml` | ревью → **комментарий** в MR (Notes API) |
| Bitbucket | [`ci/bitbucket-pipelines.yml`](ci/bitbucket-pipelines.yml) | `bitbucket-pipelines.yml` | ревью → **артефакт** `review.md` (коммент — опционально через REST) |
| Jenkins | [`ci/Jenkinsfile`](ci/Jenkinsfile) | корень репо / pipeline job | ревью → **артефакт** `review.md` |

GitHub/GitLab-примеры постят комментарий; Bitbucket/Jenkins кладут `review.md` в артефакты
(коммент добавляется вызовом REST API платформы — по аналогии с GitLab-примером).

## Верификация перед прод-использованием

Сверь с актуальной докой ocr: поддерживаемые `--format` / `--audience`, и точные
CI-переменные ветки/коммита у твоей платформы (`CI_MERGE_REQUEST_TARGET_BRANCH_NAME`,
`BITBUCKET_PR_DESTINATION_BRANCH`, `CHANGE_TARGET` и т.п.).

---

Локальный запуск — [local.md](local.md) · обзор — [README.md](README.md) · [все ревьюеры](../../README.md).
