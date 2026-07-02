# open-code-review (ocr) — локальный запуск

Быстрый CLI-ревьюер [alibaba/open-code-review](https://github.com/alibaba/open-code-review):
ревьюит незакоммиченные изменения, диапазон коммитов или один коммит; умеет свои правила
и машинный JSON-вывод. OpenAI-совместимый режим — провайдер любой (DeepSeek / GLM /
LM Studio / OpenAI / Anthropic), см. [справочник провайдеров](../../docs/providers.md).

---

## 1. Установка (глобально)

```bash
brew install node                                   # если Node ещё нет
npm install -g @alibaba-group/open-code-review
ocr version
```

> Если нет прав на глобальный npm-каталог: `npm config set prefix ~/.npm-global` и добавь
> `export PATH="$HOME/.npm-global/bin:$PATH"` в `~/.zshrc`.

```bash
brew install node
npm config set prefix ~/.npm-global
npm install -g @alibaba-group/open-code-review
echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
ocr version
```

Альтернатива — [установка как плагин Claude Code](https://github.com/alibaba/open-code-review#option-2-install-as-a-claude-code-plugin).

## 2. Конфигурация провайдера (один раз)

Настройки пишутся в `~/.opencodereview/config.json` (эталон —
[`setup/config.example.json`](setup/config.example.json)):

```bash
ocr config set llm.url https://api.deepseek.com/chat/completions
ocr config set llm.auth_token sk-***
ocr config set llm.model deepseek-v4-pro
ocr config set llm.use_anthropic false
```

Эндпоинты и id моделей других провайдеров — в [справочнике](../../docs/providers.md).
Для «думающих» моделей (`glm-5.2`, `deepseek-v4-pro`) отключить thinking:

```bash
ocr config set llm.extra_body '{"thinking": {"type": "disabled"}}'
```

## 3. Запуск ревью

```bash
ocr review                        # незакоммиченные изменения в рабочей копии
ocr review --from main --to HEAD  # диапазон: ветка против main
ocr review --commit abc123        # один коммит
ocr review --preview              # какие файлы попадут, без вызова LLM
ocr review --format json          # машинный вывод
```

Полезные флаги:

- `--concurrency N` — параллельные файлы (по умолчанию 8);
- `--audience human` (прогресс) / `agent` (только сводка);
- `--model ...` — разовый оверрайд модели;
- `--rule <файл>` — правила из указанного файла.

Ревью на русском:

```bash
ocr review --audience human --background "ревью проведи на русском языке"
```

## 4. Свои правила ревью (необязательно)

Положи в репо `.opencodereview/rule.json` (эталон —
[`setup/rule.example.json`](setup/rule.example.json)):

```json
{
  "rules": [
    { "path": "**/*.sql", "rule": "Проверяй SQL на инъекции" },
    { "path": "**/*.py",  "rule": "Требуй типизацию и докстринги у публичных функций" }
  ],
  "exclude": ["**/generated/**", "**/*.lock"]
}
```

Приоритет: флаг `--rule` > `./.opencodereview/rule.json` > `~/.opencodereview/rule.json` > дефолты.

## 5. Красивый markdown-вывод (JSON + конвертер)

Консольный режим (ANSI) хорош для быстрой проверки глазами. Если хочешь
**сохранить ревью в файл** с такой же красивой вёрсткой как в CI — враппер
[`ocr-review.sh`](ocr-review.sh):

```bash
# Обычный консольный режим (как раньше)
./ocr-review.sh

# Markdown с severity-бейджами в файл
./ocr-review.sh --markdown

# Диапазон коммитов → markdown
./ocr-review.sh --from main --to HEAD --markdown --output report.md

# Сырой JSON для своих скриптов
./ocr-review.sh --json

# Посмотреть, какие файлы попадут в ревью (без вызова LLM)
./ocr-review.sh --preview
```

Результат markdown-режима — структурированный отчёт с таблицей, severity-бейджами
(🔴 Critical / 🟡 Warning / 💡 Info), кликабельными ссылками на исходники и
diff-блоками с подсветкой. **Ровно то же, что бот постит в PR/MR.**

Если враппер не нужен — можно напрямую:

```bash
ocr review --format json > review.json
python3 .github/scripts/ocr-json-to-markdown.py review.json > review.md
```

## Ссылки

- Репозиторий: <https://github.com/alibaba/open-code-review>
- [Все флаги `ocr review`](https://github.com/alibaba/open-code-review#ocr-review-flags)

---

Встроить в пайплайн — см. [ci.md](ci.md).
Наверх — [обзор ревьюера](README.md) · [все ревьюеры](../../README.md).
