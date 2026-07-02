#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# install.sh — глобальная установка ocr-review (open-code-review wrapper)
#
# Ставит: Node (если нет) → ocr CLI → враппер + конвертер
# По умолчанию в ~/.local/ (без sudo). Если /usr/local доступен — туда.
# После установки: ocr-review доступен из любого репозитория.
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/Mikhail-Gl96/llm-review-agents/main/reviewers/open-code-review/install.sh | bash
#   # или локально:
#   ./install.sh
# ---------------------------------------------------------------------------
set -euo pipefail

# Выбираем префикс: /usr/local если пишется, иначе ~/.local
if [[ -w /usr/local/bin ]] && [[ -w /usr/local/share ]] 2>/dev/null; then
  PREFIX="${PREFIX:-/usr/local}"
else
  PREFIX="${PREFIX:-$HOME/.local}"
fi
BIN_DIR="$PREFIX/bin"
SHARE_DIR="$PREFIX/share/ocr-review"
WRAPPER="ocr-review"
CONVERTER="ocr-json-to-markdown.py"

# ── цвета ───────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
ok()  { echo -e "${GREEN}✓${NC} $1"; }
warn(){ echo -e "${YELLOW}⚠${NC}  $1"; }
err() { echo -e "${RED}✗${NC} $1"; exit 1; }

echo ""
echo "═══════════════════════════════════════════"
echo "  ocr-review — глобальная установка"
echo "═══════════════════════════════════════════"
echo ""

# ── 1. Node.js ──────────────────────────────────────────────────────────
echo "▸ Проверяю Node.js..."
if command -v node &>/dev/null; then
  ok "Node $(node --version)"
else
  warn "Node.js не найден"
  if [[ "$(uname)" == "Darwin" ]]; then
    read -rp "  Установить через Homebrew? [Y/n] " ans
    [[ "$ans" =~ ^[Nn] ]] && err "Нужен Node.js. Поставь вручную: https://nodejs.org"
    brew install node
  else
    err "Установи Node.js ≥18: https://nodejs.org (или через пакетный менеджер)"
  fi
  ok "Node $(node --version)"
fi

# ── 2. open-code-review CLI ─────────────────────────────────────────────
echo "▸ Проверяю open-code-review..."
if command -v ocr &>/dev/null; then
  ok "ocr $(ocr version 2>/dev/null || echo 'OK')"
else
  warn "open-code-review не найден, устанавливаю глобально..."
  npm install -g @alibaba-group/open-code-review
  ok "ocr установлен"
fi

# ── 3. директории ───────────────────────────────────────────────────────
echo "▸ Создаю директории..."
mkdir -p "$BIN_DIR" "$SHARE_DIR"
ok "$BIN_DIR"
ok "$SHARE_DIR"

# ── 4. конвертер (копируем рядом со скриптом) ───────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONVERTER_SRC="$SCRIPT_DIR/../.github/scripts/$CONVERTER"

# Ищем конвертер: сначала локально (в этом репо), потом скачиваем
if [[ -f "$SCRIPT_DIR/../../.github/scripts/$CONVERTER" ]]; then
  CONVERTER_SRC="$SCRIPT_DIR/../../.github/scripts/$CONVERTER"
elif [[ -f "$SCRIPT_DIR/../.github/scripts/$CONVERTER" ]]; then
  CONVERTER_SRC="$SCRIPT_DIR/../.github/scripts/$CONVERTER"
fi

if [[ -f "$CONVERTER_SRC" ]]; then
  cp "$CONVERTER_SRC" "$SHARE_DIR/$CONVERTER"
  ok "Конвертер скопирован из репо"
else
  warn "Конвертер не найден локально, скачиваю из GitHub..."
  curl -sSL "https://raw.githubusercontent.com/Mikhail-Gl96/llm-review-agents/main/.github/scripts/$CONVERTER" \
    -o "$SHARE_DIR/$CONVERTER"
  ok "Конвертер скачан"
fi

# ── 5. враппер (глобальная версия) ──────────────────────────────────────
cat > "$SHARE_DIR/$WRAPPER" << 'WRAPPER_EOF'
#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ocr-review — глобальный враппер open-code-review
#
# Режимы:
#   (по умолчанию)  — консольный ANSI-вывод в терминал
#   --markdown      — JSON → красивый markdown с severity-бейджами
#   --json          — сырой JSON для своих скриптов
#
# Примеры:
#   ocr-review                           # консоль, незакоммиченные изменения
#   ocr-review --from main --to HEAD     # диапазон коммитов
#   ocr-review --markdown                # markdown → ./review.md
#   ocr-review --markdown -o report.md   # markdown в указанный файл
#   ocr-review --json                    # сырой JSON → ./review.json
#   ocr-review --commit abc123           # один коммит
#   ocr-review --preview                 # показать файлы (без LLM)
#   ocr-review --concurrency 16          # параллельные файлы
# ---------------------------------------------------------------------------
set -euo pipefail

# Определяем путь к конвертеру: лежит рядом с враппером или в share/ocr-review/
if [[ -f "$(dirname "$0")/ocr-json-to-markdown.py" ]]; then
  SHARE_DIR="$(cd "$(dirname "$0")" && pwd)"
else
  SHARE_DIR="$(cd "$(dirname "$0")/../share/ocr-review" 2>/dev/null && pwd || echo "$(dirname "$0")")"
fi
CONVERTER="$SHARE_DIR/ocr-json-to-markdown.py"

MODE="console"
OUTPUT="review.md"
FROM=""
TO=""
COMMIT=""
PREVIEW=false
CONCURRENCY=""
EXTRA_FLAGS=()

usage() {
  sed -n '4,14s/^# //p' "$0"
  exit 0
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --markdown)    MODE="markdown"; shift ;;
    --json)        MODE="json"; shift ;;
    --from)        FROM="$2"; shift 2 ;;
    --to)          TO="$2"; shift 2 ;;
    --commit)      COMMIT="$2"; shift 2 ;;
    --output|-o)   OUTPUT="$2"; shift 2 ;;
    --preview)     PREVIEW=true; shift ;;
    --concurrency) CONCURRENCY="$2"; shift 2 ;;
    --help|-h)     usage ;;
    *)             EXTRA_FLAGS+=("$1"); shift ;;
  esac
done

# Проверка: ocr установлен?
if ! command -v ocr &>/dev/null; then
  echo "✗ open-code-review не найден. Установи: npm install -g @alibaba-group/open-code-review"
  exit 1
fi

OCR_ARGS=()
[[ -n "$FROM" ]]        && OCR_ARGS+=("--from" "$FROM")
[[ -n "$TO" ]]          && OCR_ARGS+=("--to" "$TO")
[[ -n "$COMMIT" ]]      && OCR_ARGS+=("--commit" "$COMMIT")
[[ "$PREVIEW" == true ]] && OCR_ARGS+=("--preview")
[[ -n "$CONCURRENCY" ]] && OCR_ARGS+=("--concurrency" "$CONCURRENCY")
[[ ${#EXTRA_FLAGS[@]} -gt 0 ]] && OCR_ARGS+=("${EXTRA_FLAGS[@]}")

case $MODE in
  console)
    [[ "$PREVIEW" != true ]] && OCR_ARGS+=("--audience" "human")
    exec ocr review "${OCR_ARGS[@]}"
    ;;

  json)
    JSON_FILE="${OUTPUT%.md}.json"
    OCR_ARGS+=("--format" "json")
    echo "▶ JSON-режим → $JSON_FILE"
    ocr review "${OCR_ARGS[@]}" > "$JSON_FILE"
    echo "✓ Сохранено: $JSON_FILE"
    ;;

  markdown)
    if [[ ! -f "$CONVERTER" ]]; then
      echo "✗ Конвертер не найден: $CONVERTER"
      echo "  Переустанови: curl -sSL https://raw.githubusercontent.com/Mikhail-Gl96/llm-review-agents/main/reviewers/open-code-review/install.sh | bash"
      exit 1
    fi
    JSON_TMP="$(mktemp)"
    OCR_ARGS+=("--format" "json")
    echo "▶ Markdown-режим → $OUTPUT"
    ocr review "${OCR_ARGS[@]}" > "$JSON_TMP"
    python3 "$CONVERTER" "$JSON_TMP" > "$OUTPUT"
    rm -f "$JSON_TMP"
    echo "✓ Сохранено: $OUTPUT"
    ;;
esac
WRAPPER_EOF

chmod +x "$SHARE_DIR/$WRAPPER"

# ── 6. symlink в PATH ───────────────────────────────────────────────────
if [[ -L "$BIN_DIR/$WRAPPER" ]] || [[ -f "$BIN_DIR/$WRAPPER" ]]; then
  rm -f "$BIN_DIR/$WRAPPER"
fi
ln -sf "$SHARE_DIR/$WRAPPER" "$BIN_DIR/$WRAPPER"
ok "Симлинк: $BIN_DIR/$WRAPPER → $SHARE_DIR/$WRAPPER"

# ── 7. проверка PATH ────────────────────────────────────────────────────
if ! echo "$PATH" | grep -q "$BIN_DIR"; then
  warn "$BIN_DIR нет в PATH!"
  echo "  Добавь в ~/.zshrc:"
  echo ""
  echo "    export PATH=\"$BIN_DIR:\$PATH\""
  echo ""
fi

# ── финал ───────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo "  Установка завершена!"
echo ""
echo "  Префикс:  $PREFIX"
echo "  Команда:  ocr-review"
echo "  Режимы:   консоль | --markdown | --json"
echo ""
echo "  Попробуй: ocr-review --preview"
echo "═══════════════════════════════════════════"
echo ""
