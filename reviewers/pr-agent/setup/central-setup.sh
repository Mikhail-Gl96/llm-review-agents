#!/usr/bin/env bash
# =====================================================================
#  ЦЕНТРАЛЬНАЯ установка локального AI-ревьюера (вариант «поставил один раз —
#  запускаешь в любом проекте, в коде проекта ничего не лежит»).
#
#  Что делает:
#    - ставит uv (если нет);
#    - ставит pr-agent как ИЗОЛИРОВАННЫЙ глобальный uv-tool (БЕЗ клона репы);
#    - кладёт конфиг с ключами в ~/.config/pr-agent-review/config.env (chmod 600);
#    - ставит команду `pr_agent_review` в ~/.local/bin (PATH).
#  Идемпотентно: повторный запуск не перетирает уже вписанные ключи.
#
#  Запуск:  bash tool-pr-agent/central-setup.sh
# =====================================================================
set -euo pipefail

PR_AGENT_VERSION="0.36.1"        # зафиксированная версия (проверена)
PY_VERSION="3.12"                # litellm в pr-agent требует Python <3.14
CFG_DIR="$HOME/.config/pr-agent-review"
CFG="$CFG_DIR/config.env"
BIN="$HOME/.local/bin"
WRAPPER="$BIN/pr_agent_review"

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }

# 1) uv ---------------------------------------------------------------
export PATH="$BIN:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  say "Ставлю uv…"; curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$BIN:$PATH"
fi
say "uv: $(uv --version)"

# 2) pr-agent как глобальный tool (без клона) -------------------------
say "Ставлю pr-agent==$PR_AGENT_VERSION как глобальный uv-tool…"
uv tool install --python "$PY_VERSION" "pr-agent==$PR_AGENT_VERSION" >/dev/null 2>&1 \
  || uv tool install --python "$PY_VERSION" --force "pr-agent==$PR_AGENT_VERSION" >/dev/null
say "pr-agent: $(command -v pr-agent)"

# 3) конфиг с ключами (не перетираем существующий) --------------------
mkdir -p "$CFG_DIR"
if [ ! -f "$CFG" ]; then
  cat > "$CFG" <<'EOF'
# ~/.config/pr-agent-review/config.env
# Конфиг локального AI-ревьюера. Раскомментирован РОВНО ОДИН провайдер.
# Файл chmod 600 — храни ключи только здесь, не в проектах.

# Глобальный кап на размер ВХОДА (все провайдеры). Дефолт pr-agent = 32000,
# режет через min(max_model_tokens, custom_model_max_tokens). Раскомментируй и
# подними, чтобы реально использовать большой контекст модели (0 = снять кап).
# export CONFIG__MAX_MODEL_TOKENS=1000000

# --- DeepSeek (по умолчанию) ---
export CONFIG__MODEL="deepseek/deepseek-v4-pro"          # deepseek-v4-pro/reasoner — без custom_model_max_tokens
export CONFIG__FALLBACK_MODELS='["deepseek/deepseek-v4-pro"]'
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
EOF
  chmod 600 "$CFG"
  say "Создан $CFG — ВПИШИ ключ выбранного провайдера."
else
  say "Конфиг уже есть: $CFG (не трогаю)."
fi

# 4) команда pr_agent_review ----------------------------------------------
mkdir -p "$BIN"
cat > "$WRAPPER" <<'EOF'
#!/usr/bin/env bash
# Локальное AI-ревью ТЕКУЩЕГО git-репозитория.
# Использование: pr_agent_review [базовая-ветка] [команда]   (по умолчанию: master review)
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
CFG="${PR_REVIEW_CONFIG:-$HOME/.config/pr-agent-review/config.env}"
[ -f "$CFG" ] || { echo "Нет конфига: $CFG — запусти central-setup.sh и впиши ключ."; exit 1; }
# shellcheck disable=SC1090
source "$CFG"
export CONFIG__GIT_PROVIDER=local
BASE="${1:-master}"; shift || true
CMD=( "$@" ); [ ${#CMD[@]} -eq 0 ] && CMD=(review)

git rev-parse --git-dir >/dev/null 2>&1 || { echo "Не git-репозиторий: $(pwd)"; exit 1; }
if ! git show-ref --verify --quiet "refs/heads/$BASE"; then
  echo "Локальной ветки '$BASE' нет. Доступные: $(git for-each-ref --format='%(refname:short)' refs/heads | tr '\n' ' ')"
  echo "Укажи существующую базовую ветку, напр.: pr_agent_review master review"
  exit 1
fi

# pr-agent (local) требует чистое дерево, но диффит он ТОЛЬКО коммиты (HEAD vs база),
# рабочее дерево не читает. Поэтому временно прячем ОТСЛЕЖИВАЕМЫЕ правки в stash
# (untracked не трогаем) и возвращаем после — даже при ошибке/Ctrl-C.
AUTOSTASH=0
_restore() { [ "${AUTOSTASH:-0}" = 1 ] && { git stash pop -q 2>/dev/null || true; AUTOSTASH=0; }; }
trap _restore EXIT
if ! git diff --quiet HEAD 2>/dev/null; then
  git stash push -q -m pr_agent_review-autostash && AUTOSTASH=1
fi

echo ">> repo:  $(pwd)"
echo ">> base:  $BASE | cmd: ${CMD[*]} | model: ${CONFIG__MODEL:-?}"
echo ">> вывод: review.md / description.md в корне репозитория"
[ "$AUTOSTASH" = 1 ] && echo ">> (незакоммиченные правки временно убраны в stash, вернутся после)"
echo "------------------------------------------------------------"
pr-agent --pr_url "$BASE" "${CMD[@]}"
EOF
chmod +x "$WRAPPER"
say "Команда установлена: $WRAPPER"

# 5) PATH-проверка ----------------------------------------------------
case ":$PATH:" in
  *":$BIN:"*) : ;;
  *) say "ВНИМАНИЕ: $BIN не в PATH. Добавь в ~/.zshrc:  export PATH=\"\$HOME/.local/bin:\$PATH\"  (или: uv tool update-shell)";;
esac

printf '\n\033[1;32mГотово.\033[0m\n'
cat <<'EOF'
Дальше:
  1. Впиши ключ:   ~/.config/pr-agent-review/config.env   (раскомментирован один провайдер)
  2. В любом проекте, на ветке с коммитами и чистым деревом:
       pr_agent_review master review
       cat review.md
EOF
