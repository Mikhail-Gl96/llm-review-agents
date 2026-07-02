# Справочник LLM-провайдеров

Единый справочник провайдеров для всех ревьюеров тулкита — канонические факты
(эндпоинты, id моделей, нюансы). Каждый ревьюер в своём `local.md` показывает, как
вписать выбранного провайдера в **его** формат конфига (pr-agent — переменные
окружения `CONFIG__*`; open-code-review — `~/.opencodereview/config.json`).

## Провайдеры

| Провайдер | Эндпоинт | Модель | Нюансы |
|---|---|---|---|
| **DeepSeek** | `https://api.deepseek.com` (chat: `/chat/completions`) | `deepseek-v4-pro` (дефолт) · `deepseek-reasoner` | `use_anthropic=false`; для pr-agent доп. настроек не нужно — самый простой старт |
| **GLM (z.ai)** | Coding Plan: `https://api.z.ai/api/coding/paas/v4`<br>pay-as-you-go: `https://api.z.ai/api/paas/v4`<br>материк: `https://open.bigmodel.cn/api/paas/v4` | `glm-5.2` (reasoning) · `glm-5.2[1m]` — 1M контекст | thinking off; **не перепутать эндпоинт** (см. ниже); для pr-agent обязательны `custom_model_max_tokens` + `duplicate_examples` |
| **LM Studio** (офлайн) | `http://localhost:1234/v1` | id загруженной модели | ключ — любая непустая строка (напр. `lm-studio`); сначала LM Studio → Developer → Start Server; для pr-agent обязательны `custom_model_max_tokens` + `duplicate_examples` |
| **OpenAI** | `https://api.openai.com/v1` | `gpt-5.5` | `use_anthropic=false` |
| **Anthropic** | `https://api.anthropic.com/v1/messages` | `claude-opus-4-8` | `use_anthropic=true` |

## Нюанс GLM-эндпоинта (важно)

У z.ai два типа доступа с **разными** эндпоинтами:

- **GLM Coding Plan** (подписка для кодинг-агентов) → `https://api.z.ai/api/coding/paas/v4`.
  Биллится с подписки.
- **Pay-as-you-go API** (оплата по токенам) → `https://api.z.ai/api/paas/v4`
  (материковый Китай: `https://open.bigmodel.cn/api/paas/v4`).

Если взять `/api/paas/v4` с ключом от Coding Plan — получишь
`RateLimitError: Insufficient balance or no resource package` (обычный эндпоинт смотрит
на pay-as-you-go баланс, а не на подписку).

## Reasoning-модели (thinking)

`glm-5.2` и `deepseek-reasoner` тратят часть токенов на «размышление». В полном ревью
pr-agent выделяет достаточно; при своих тестах поднимай `max_tokens`. Отключить thinking:

- **open-code-review:**
  ```bash
  # отключить
  ocr config set llm.extra_body '{"thinking": {"type": "disabled"}}'
  # включить обратно
  ocr config delete llm.extra_body
  ```
- **pr-agent:** через параметры модели LiteLLM (см. доку провайдера).

## Как подключить к ревьюеру

Маппинг провайдера в конфиг конкретного инструмента — в его `local.md`:
`reviewers/pr-agent/local.md` (переменные `CONFIG__*`) и
`reviewers/open-code-review/local.md` (`~/.opencodereview/config.json`).
