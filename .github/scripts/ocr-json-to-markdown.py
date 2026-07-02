#!/usr/bin/env python3
"""Convert open-code-review JSON output to a beautiful GitHub-flavored markdown PR comment.

Reads review.json from first argument (or stdin), writes markdown to stdout.

Severity tags are parsed from the beginning of each comment's `content` field:
  [CRITICAL] — security bugs, crashes, data leaks
  [WARNING]  — potential bugs, race conditions, unhandled errors
  [INFO]     — style, readability, maintainability
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

# ── severity ───────────────────────────────────────────────────────────

SEVERITY_CONFIG = {
    "CRITICAL": {"emoji": "🔴", "label": "Critical", "order": 0},
    "WARNING":  {"emoji": "🟡", "label": "Warning",  "order": 1},
    "INFO":     {"emoji": "💡", "label": "Info",     "order": 2},
}

STATUS_EMOJI = {
    "success": "✅",
    "completed_with_warnings": "⚠️",
    "completed_with_errors": "❌",
    "skipped": "⏭️",
}

_RE_SEVERITY = re.compile(r"^\[(CRITICAL|WARNING|INFO)\]\s*")


def parse_severity(content: str) -> tuple[str, str]:
    """Extract [SEVERITY] tag from content. Returns (severity, cleaned_content)."""
    m = _RE_SEVERITY.match(content)
    if m:
        return m.group(1), content[m.end():].strip()
    return "INFO", content.strip()


def severity_badge(severity: str) -> str:
    cfg = SEVERITY_CONFIG.get(severity, SEVERITY_CONFIG["INFO"])
    return f"{cfg['emoji']} **{cfg['label']}**"


# ── formatting helpers ──────────────────────────────────────────────────

def fmt_tokens(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.0f}K"
    return str(n)


def format_summary_table(summary: dict, severity_counts: Counter) -> str:
    """Compact summary with severity breakdown."""
    files = summary.get("files_reviewed", 0)
    comments = summary.get("comments", 0)
    total_t = fmt_tokens(summary.get("total_tokens", 0))
    input_t = fmt_tokens(summary.get("input_tokens", 0))
    output_t = fmt_tokens(summary.get("output_tokens", 0))
    elapsed = summary.get("elapsed", "?")

    crit = severity_counts.get("CRITICAL", 0)
    warn = severity_counts.get("WARNING", 0)
    info = severity_counts.get("INFO", 0)

    return (
        f"| 📁 Files | 🔍 Findings | 🔴 Critical | 🟡 Warning | 💡 Info | ⏱️ Time |\n"
        f"|----------|-------------|-------------|------------|---------|------|\n"
        f"| {files} | {comments} | {crit} | {warn} | {info} | {elapsed} |"
    )


def format_diff(existing: str, suggestion: str) -> str:
    """Render existing → suggestion as a diff code block."""
    if not existing and not suggestion:
        return ""

    lines = ["```diff"]
    for line in existing.split("\n"):
        lines.append(f"-{line}" if line else "-")
    for line in suggestion.split("\n"):
        lines.append(f"+{line}" if line else "+")
    lines.append("```")
    return "\n".join(lines)


def format_finding(number: int, comment: dict, severity: str, base_url: str) -> str:
    """Render a single finding as a markdown blockquote section."""
    path = comment["path"]
    start = comment.get("start_line", 0)
    end = comment.get("end_line", 0)
    content = comment.get("content", "").strip()
    existing = comment.get("existing_code", "").strip()
    suggestion = comment.get("suggestion_code", "").strip()

    badge = severity_badge(severity)

    # Clickable file:line link
    if base_url and start:
        range_str = f"#L{start}" if start == end else f"#L{start}-L{end}"
        file_link = f"[`{path}:{start}-{end}`]({base_url}/{path}{range_str})"
    else:
        file_link = f"`{path}:{start}-{end}`"

    lines = [f"**{number}.** {badge} · {file_link}", "", f"> {content}"]

    diff = format_diff(existing, suggestion)
    if diff:
        lines.append("")
        lines.append(diff)

    lines.append("")
    return "\n".join(lines)


# ── main render ────────────────────────────────────────────────────────

def render(data: dict, base_url: str = "") -> str:
    status = data.get("status", "success")
    emoji = STATUS_EMOJI.get(status, "📋")
    message = data.get("message", "")
    summary = data.get("summary")
    comments: list[dict] = data.get("comments", [])

    parts = [f"## {emoji} AI Code Review"]

    # Status message
    if message:
        parts.append(f"> {message}")
        parts.append("")

    # ── empty state ──────────────────────────────────────────────────
    if not comments:
        parts.append("")
        parts.append("### ✨ No issues found")
        parts.append("")
        parts.append("Код выглядит хорошо — замечаний нет.")
        parts.append("")
        if status == "skipped":
            parts.append("*(review skipped — no supported files changed)*")
        return "\n".join(parts)

    # ── enrich with severity ─────────────────────────────────────────
    enriched: list[dict] = []
    severity_counts: Counter[str] = Counter()

    for c in comments:
        sev, clean = parse_severity(c.get("content", ""))
        severity_counts[sev] += 1
        enriched.append({**c, "_severity": sev, "_content_clean": clean})

    # Sort by severity (critical first), then by file path, then by line
    enriched.sort(key=lambda c: (
        SEVERITY_CONFIG.get(c["_severity"], {}).get("order", 99),
        c.get("path", ""),
        c.get("start_line", 0),
    ))

    # ── summary table ────────────────────────────────────────────────
    if summary:
        parts.append(format_summary_table(summary, severity_counts))
        parts.append("")

    # ── group by file ────────────────────────────────────────────────
    by_file: dict[str, list[dict]] = {}
    for c in enriched:
        by_file.setdefault(c["path"], []).append(c)

    parts.append(
        f"<details open>\n"
        f"<summary>📋 {len(comments)} finding(s) in {len(by_file)} file(s)</summary>"
    )
    parts.append("")

    finding_num = 0

    for path, file_findings in by_file.items():
        parts.append(f"### 📄 `{path}` — {len(file_findings)} finding(s)")
        parts.append("")

        for c in file_findings:
            finding_num += 1
            parts.append(format_finding(finding_num, c, c["_severity"], base_url))

    parts.append("</details>")

    # ── footer ───────────────────────────────────────────────────────
    total_t = summary.get("total_tokens", 0) if summary else 0
    parts.append(
        f"---\n"
        f"<sub>🤖 Reviewed by [open-code-review]"
        f"(https://github.com/alibaba/open-code-review) · "
        f"{fmt_tokens(total_t)} tokens used</sub>"
    )

    return "\n".join(parts)


# ── entry point ─────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if not path.exists():
            print(f"✗ Файл не найден: {path}", file=sys.stderr)
            sys.exit(1)
        if path.stat().st_size == 0:
            print(f"✗ Файл пуст: {path}", file=sys.stderr)
            sys.exit(1)
        raw = path.read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()

    raw = raw.strip()
    if not raw:
        if len(sys.argv) > 1:
            print(f"✗ Файл содержит только пробельные символы: {path}", file=sys.stderr)
        else:
            print("✗ JSON-ввод пуст — ocr не вернул данных.", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        preview = raw[:200] if len(raw) > 200 else raw
        print(f"✗ Ошибка парсинга JSON: {e}", file=sys.stderr)
        print(f"  Содержимое (первые 200 байт): {preview}", file=sys.stderr)
        sys.exit(1)

    base_url = sys.argv[2] if len(sys.argv) > 2 else ""
    print(render(data, base_url))


if __name__ == "__main__":
    main()
