# review-bot — ревью по комментарию

Центральный webhook-сервис: тегаешь **`@review[.движок]`** в комментарии PR/MR — бот
запускает выбранного ревьюера на чекауте PR и постит результат ответным комментом.
Дефолт `@review` → `ocr`. Один деплой обслуживает много репозиториев.

Спека: [SP2 design](../docs/superpowers/specs/2026-07-02-comment-triggered-review-bot-design.md).
Провайдеры LLM: [../docs/providers.md](../docs/providers.md).

## Как звать бота

- `@review` — дефолтный движок (`ocr`)
- `@review.ocr` — open-code-review
- `@review.pr.agent` — pr-agent

«Тег» — это парсинг текста коммента (один бот-app на платформу), а не отдельный аккаунт на каждый движок.

## Конфигурация (env)

| Переменная | Назначение |
|---|---|
| `DEFAULT_ENGINE` | движок для голого `@review` (деф. `ocr`) |
| `ENABLED_ENGINES` | включённые движки через запятую (`ocr,pr.agent`) |
| `ALLOWLIST` | пусто = любой с правами на репо; иначе список логинов |
| `REVIEW_TIMEOUT` | таймаут одного ревью, сек |
| `GITHUB_TOKEN` / `GITHUB_WEBHOOK_SECRET` / `GITHUB_BOT_LOGIN` | доступ и верификация GitHub |
| `GITLAB_TOKEN` / `GITLAB_WEBHOOK_SECRET` / `GITLAB_BOT_USERNAME` | доступ и верификация GitLab |
| `DEEPSEEK_KEY` (и др.) | ключ LLM-провайдера для движков |

Полный список — в [`.env.example`](.env.example).

## Запуск локально

```bash
pip install -e ".[dev]"
uvicorn review_bot.main:app --reload
curl localhost:8000/healthz        # {"status":"ok"}
pytest                              # тесты
```

## Docker

```bash
docker build -t review-bot bot/
docker run --env-file bot/.env -p 8000:8000 review-bot
```

Образ содержит оба движка (`ocr` через npm, `pr-agent` через pip) + git.

## Регистрация вебхуков

- **GitHub:** App или PAT с правами `contents:read`, `pull_requests:write`. Вебхук на
  событие *Issue comments* → `https://<host>/webhook/github`, Secret = `GITHUB_WEBHOOK_SECRET`.
- **GitLab:** Project/Group webhook на *Comments* → `https://<host>/webhook/gitlab`,
  Secret token = `GITLAB_WEBHOOK_SECRET`; токен бота scope `api`.

> Точные права токенов/скоупы сверь с актуальной докой платформы при регистрации.

## Безопасность

- Verify подписи вебхука (GitHub HMAC `X-Hub-Signature-256`; GitLab `X-Gitlab-Token`).
- Авторизация: право на репозиторий (коллаборатор/участник, access_level ≥ 30) + опциональный `ALLOWLIST`.
- Анти-loop: комменты самого бота игнорируются.
- Дедуп событий по id; таймаут ревью.

## Расширяемость

- **Новый ревьюер:** класс с `key` и `run(checkout_dir, base_ref, head_ref) -> str` (markdown),
  зарегистрировать в `build_reviewers` (`review_bot/main.py`). См. также [../docs/add-a-reviewer.md](../docs/add-a-reviewer.md).
- **Новая платформа:** адаптер под интерфейс `PlatformAdapter`
  (`review_bot/platforms/base.py`) + роут в `create_app`.

## Ограничения v1

- Платформы: GitHub + GitLab (Bitbucket — задел через тот же интерфейс).
- Ревью — весь diff PR/MR (без под-команд и флагов).
