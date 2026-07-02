#!/usr/bin/env python3
"""Convert open-code-review JSON output to a beautiful GitHub-flavored markdown PR comment.

Reads review.json from stdin or first argument, writes markdown to stdout.

Top-level JSON schema (ocr review --format json):
{
  "status": "success" | "completed_with_warnings" | "completed_with_errors" | "skipped",
  "message": "...",
  "summary": {
    "files_reviewed": 1, "comments": 5,
    "total_tokens": 31796, "input_tokens": 28529, "output_tokens": 3267,
    "cache_read_tokens": 0,  "cache_write_tokens": 0,
    "elapsed": "48s"
  },
  "comments": [
    {
      "path": "test_review.py",
      "content": "text of the finding",
      "existing_code": "old lines",     // omitempty
      "suggestion_code": "new lines",   // omitempty
      "start_line": 6,
      "end_line": 11,
      "thinking": "..."                 // omitempty
    }
  ],
  "warnings": [...],
  "tool_calls": {"total": 10, "by_tool": {"read": 5}},
  "project_summary": "..."
}
"""

import json
import sys
import textwrap
from pathlib import Path


STATUS_EMOJI = {
    "success": "✅",
    "completed_with_warnings": "⚠️",
    "completed_with_errors": "❌",
    "skipped": "⏭️",
}


def fmt_tokens(n: int) -> str:
    """Format token count: 31796 → '32K'."""
    if n >= 1000:
        return f"{n / 1000:.0f}K"
    return str(n)


def format_summary_table(summary: dict) -> str:
    """Render the summary as a compact markdown table."""
    files = summary.get("files_reviewed", 0)
    comments = summary.get("comments", 0)
    total_t = fmt_tokens(summary.get("total_tokens", 0))
    input_t = fmt_tokens(summary.get("input_tokens", 0))
    output_t = fmt_tokens(summary.get("output_tokens", 0))
    elapsed = summary.get("elapsed", "?")

    return textwrap.dedent(f"""\
        | Files | Findings | Tokens (in → out) | Time |
        |-------|----------|-------------------|------|
        | {files} | {comments} | {input_t} → {output_t} ({total_t} total) | {elapsed} |""")


def format_comment(idx: int, comment: dict, base_url: str = "") -> str:
    """Render a single review comment as a markdown section."""
    path = comment["path"]
    start = comment.get("start_line", 0)
    end = comment.get("end_line", 0)
    content = comment.get("content", "").strip()
    existing = comment.get("existing_code", "").strip()
    suggestion = comment.get("suggestion_code", "").strip()

    # File header with link to GitHub source
    if base_url and start:
        # GitHub URLs for specific line ranges: blob/<ref>/path#L1-L10
        range_str = f"#L{start}" if start == end else f"#L{start}-L{end}"
        header = f"### `{path}:{start}-{end}` [↗]({base_url}/{path}{range_str})"
    else:
        header = f"### `{path}:{start}-{end}`"

    lines = [header, "", content]

    # Render diff if we have code
    if existing or suggestion:
        lines.append("")
        # Strip trailing newlines for clean diff rendering
        lines.append("```diff")
        for line in existing.split("\n"):
            lines.append(f"-{line}" if line else "-")
        for line in suggestion.split("\n"):
            lines.append(f"+{line}" if line else "+")
        lines.append("```")

    return "\n".join(lines)


def render(data: dict, base_url: str = "") -> str:
    """Convert parsed JSON into a complete markdown PR comment."""
    status = data.get("status", "success")
    emoji = STATUS_EMOJI.get(status, "📋")
    message = data.get("message", "")
    summary = data.get("summary")
    comments = data.get("comments", [])

    parts = [f"## {emoji} AI Code Review"]

    if message:
        parts.append(f"> {message}")
        parts.append("")

    if summary:
        parts.append(format_summary_table(summary))
        parts.append("")

    if not comments:
        parts.append("*No findings.*")
        return "\n".join(parts)

    # Group comments by file
    by_file: dict[str, list[dict]] = {}
    for c in comments:
        by_file.setdefault(c["path"], []).append(c)

    parts.append(
        f"<details open>\n"
        f"<summary>📋 {len(comments)} finding(s) in {len(by_file)} file(s)</summary>"
    )
    parts.append("")

    for path, file_comments in by_file.items():
        for i, comment in enumerate(file_comments, 1):
            parts.append(format_comment(i, comment, base_url))
            parts.append("")

    parts.append("</details>")
    return "\n".join(parts)


def main() -> None:
    # Read from file argument or stdin
    if len(sys.argv) > 1:
        raw = Path(sys.argv[1]).read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()

    data = json.loads(raw)

    # Optional: base URL for clickable file links (GitHub blob URL)
    base_url = sys.argv[2] if len(sys.argv) > 2 else ""

    print(render(data, base_url))


if __name__ == "__main__":
    main()
