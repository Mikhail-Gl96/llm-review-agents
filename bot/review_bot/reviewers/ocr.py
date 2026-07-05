import json
import subprocess
from pathlib import Path


class OcrAdapter:
    key = "ocr"

    def __init__(self, timeout: int = 900) -> None:
        self._timeout = timeout

    def run(self, checkout_dir: Path, base_ref: str, head_ref: str) -> str:
        r = subprocess.run(
            ["ocr", "review", "--from", f"origin/{base_ref}", "--to", head_ref,
             "--audience", "agent", "--format", "json"],
            cwd=str(checkout_dir), check=True, capture_output=True, text=True,
            timeout=self._timeout,
        )
        return _to_markdown(r.stdout)


def _diff_block(existing: str, suggestion: str) -> str:
    lines = []
    if existing:
        lines += ["-" + ln for ln in existing.replace("\r", "").split("\n")]
    if suggestion:
        lines += ["+" + ln for ln in suggestion.replace("\r", "").split("\n")]
    if not lines:
        return ""
    return "\n```diff\n" + "\n".join(lines) + "\n```"


def _to_markdown(raw: str) -> str:
    """JSON-вывод `ocr review --format json` → аккуратный GitLab/GitHub-markdown."""
    try:
        d = json.loads(raw)
    except (ValueError, TypeError):
        return "### 🤖 AI-ревью (ocr)\n\n`не удалось разобрать JSON вывода ocr`"
    summary = d.get("summary") or {}
    comments = d.get("comments") or []
    out = ["### 🤖 AI-ревью кода (open-code-review)"]
    meta = (f"_Файлов: {summary.get('files_reviewed', '?')} · "
            f"замечаний: {summary.get('comments', len(comments))}")
    if summary.get("elapsed"):
        meta += f" · {summary['elapsed']}"
    out.append(meta + "_")

    if not comments:
        out.append("\n✅ Замечаний нет.")
        return "\n".join(out)

    by_file: dict[str, list] = {}
    for c in comments:
        by_file.setdefault(c.get("path") or "(неизвестный файл)", []).append(c)

    for path, cs in by_file.items():
        out.append("\n---\n")
        word = "замечание" if len(cs) == 1 else "замечания(-ий)"
        out.append(f"#### 📄 `{path}` — {len(cs)} {word}")
        for c in cs:
            start, end = c.get("start_line"), c.get("end_line")
            if start:
                loc = f"строки {start}" + (f"–{end}" if end and end != start else "")
            else:
                loc = "общее"
            out.append(f"\n**{loc}**\n")
            content = (c.get("content") or "").strip()
            if content:
                out.append(content)
            diff = _diff_block(c.get("existing_code") or "", c.get("suggestion_code") or "")
            if diff:
                out.append(diff)
    return "\n".join(out)
