#!/usr/bin/env sh
# Конфигурит движки из env перед стартом сервиса, затем запускает CMD.
#  - ocr читает ~/.opencodereview/config.json → настраиваем через `ocr config set`.
#  - pr-agent берёт настройки из env-переменных (CONFIG__*, DEEPSEEK__KEY) напрямую.
set -e

if [ -n "${DEEPSEEK_KEY:-}" ]; then
  ocr config set llm.url "${OCR_LLM_URL:-https://api.deepseek.com/chat/completions}" >/dev/null 2>&1 || true
  ocr config set llm.auth_token "$DEEPSEEK_KEY"                                        >/dev/null 2>&1 || true
  ocr config set llm.model "${OCR_MODEL:-deepseek-v4-pro}"                             >/dev/null 2>&1 || true
  ocr config set llm.use_anthropic false                                              >/dev/null 2>&1 || true
fi

exec "$@"
