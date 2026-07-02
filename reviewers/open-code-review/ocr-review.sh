#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ocr-review.sh — локальный запуск open-code-review с двумя режимами вывода
#
# Режимы:
#   консоль (по умолчанию) — ANSI-вывод прямо в терминал, как раньше
#   markdown (--markdown)  — JSON → красивый markdown-файл с бейджами
#   json (--json)          — сырой JSON для своих скриптов
#
# Примеры:
#   ./ocr-review.sh                           # консоль, незакоммиченные изменения
#   ./ocr-review.sh --from main --to HEAD     # консоль, диапазон коммитов
#   ./ocr-review.sh --markdown                # markdown в review.md
#   ./ocr-review.sh --markdown --output out.md
#   ./ocr-review.sh --json                    # сырой JSON в review.json
#   ./ocr-review.sh --commit abc123           # один коммит (любой режим)
#   ./ocr-review.sh --preview                 # показать, что попадёт в ревью (без LLM)
# ---------------------------------------------------------------------------
set -euo pipefail

# ── repo root (2 уровня вверх от reviewers/open-code-review/) ──────────
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONVERTER="$REPO_ROOT/.github/scripts/ocr-json-to-markdown.py"

# ── defaults ────────────────────────────────────────────────────────────
MODE="console"
OUTPUT="review.md"
FROM=""
TO=""
COMMIT=""
PREVIEW=false
CONCURRENCY=""
AUDIENCE="human"
EXTRA_FLAGS=()

# ── usage ───────────────────────────────────────────────────────────────
usage() {
  sed -n '2,13s/^# //p' "$0"
  exit 0
}

# ── ensure ocr is installed ─────────────────────────────────────────────
ensure_ocr() {
  if command -v ocr &>/dev/null; then
    return
  fi
  echo "⚠️  open-code-review не найден."
  read -rp "Установить глобально через npm? [Y/n] " answer
  if [[ "$answer" =~ ^[Nn] ]]; then
    echo "Установи вручную: npm install -g @alibaba-group/open-code-review"
    exit 1
  fi
  echo "Устанавливаю @alibaba-group/open-code-review..."
  npm install -g @alibaba-group/open-code-review
  echo "✓ установлен"
}

# ── parse args ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --markdown)  MODE="markdown"; shift ;;
    --json)      MODE="json"; shift ;;
    --from)      FROM="$2"; shift 2 ;;
    --to)        TO="$2"; shift 2 ;;
    --commit)    COMMIT="$2"; shift 2 ;;
    --output)    OUTPUT="$2"; shift 2 ;;
    --preview)   PREVIEW=true; shift ;;
    --concurrency) CONCURRENCY="$2"; shift 2 ;;
    --help|-h)   usage ;;
    *)           EXTRA_FLAGS+=("$1"); shift ;;
  esac
done

# ── main ────────────────────────────────────────────────────────────────
ensure_ocr

# Сборка команды ocr review
OCR_ARGS=()
[[ -n "$FROM" ]]    && OCR_ARGS+=("--from" "$FROM")
[[ -n "$TO" ]]      && OCR_ARGS+=("--to" "$TO")
[[ -n "$COMMIT" ]]  && OCR_ARGS+=("--commit" "$COMMIT")
[[ "$PREVIEW" == true ]] && OCR_ARGS+=("--preview")
[[ -n "$CONCURRENCY" ]]  && OCR_ARGS+=("--concurrency" "$CONCURRENCY")

# Добавляем оставшиеся флаги
OCR_ARGS+=("${EXTRA_FLAGS[@]}")

case $MODE in
  # ── консоль: ANSI-вывод в терминал ────────────────────────────────
  console)
    if [[ "$PREVIEW" != true ]]; then
      OCR_ARGS+=("--audience" "$AUDIENCE")
    fi
    echo "▶ Консольный режим (ANSI)"
    echo ""
    exec ocr review "${OCR_ARGS[@]}"
    ;;

  # ── json: сырой JSON в файл ───────────────────────────────────────
  json)
    JSON_FILE="${OUTPUT%.md}.json"
    OCR_ARGS+=("--format" "json")
    echo "▶ JSON-режим → $JSON_FILE"
    ocr review "${OCR_ARGS[@]}" > "$JSON_FILE"
    echo "✓ Сохранено: $JSON_FILE"
    ;;

  # ── markdown: JSON → конвертер → красивый .md ─────────────────────
  markdown)
    JSON_TMP="$(mktemp)"
    OCR_ARGS+=("--format" "json")
    echo "▶ Markdown-режим → $OUTPUT"

    if [[ ! -f "$CONVERTER" ]]; then
      echo "✗ Конвертер не найден: $CONVERTER"
      echo "  Убедись, что файл .github/scripts/ocr-json-to-markdown.py есть в репо."
      exit 1
    fi

    ocr review "${OCR_ARGS[@]}" > "$JSON_TMP"
    python3 "$CONVERTER" "$JSON_TMP" > "$OUTPUT"
    rm -f "$JSON_TMP"
    echo "✓ Сохранено: $OUTPUT"
    ;;
esac
