import json
from pathlib import Path

from review_bot.reviewers.ocr import OcrAdapter

SAMPLE = json.dumps({
    "summary": {"files_reviewed": 1, "comments": 1, "elapsed": "5s",
                "total_tokens": 6829, "input_tokens": 6502, "output_tokens": 327},
    "comments": [{
        "path": "util.py",
        "content": "Logic bug: subtraction instead of addition.",
        "existing_code": "def add(a, b):\n    return a - b",
        "suggestion_code": "def add(a, b):\n    return a + b",
        "start_line": 1, "end_line": 2,
    }],
})


def test_run_builds_json_command_and_renders_markdown(monkeypatch):
    calls = {}

    class R:
        stdout = SAMPLE

    def fake_run(cmd, cwd, check, capture_output, text, timeout=None):
        calls["cmd"] = cmd
        calls["cwd"] = cwd
        return R()

    monkeypatch.setattr("review_bot.reviewers.ocr.subprocess.run", fake_run)
    out = OcrAdapter().run(Path("/tmp/x"), "main", "feature")
    # команда просит JSON и правильный диапазон
    assert "--format" in calls["cmd"] and "json" in calls["cmd"]
    assert "origin/main" in calls["cmd"] and "feature" in calls["cmd"]
    # рендер — markdown с заголовком, диапазоном и ```diff (без ANSI)
    assert "### 🤖 AI-ревью" in out
    assert "~6829 токенов" in out and "вход ~6502" in out and "выход ~327" in out
    assert "**строки 1–2**" in out
    assert "```diff" in out
    assert "-    return a - b" in out and "+    return a + b" in out
    assert "\x1b" not in out  # никаких ANSI-кодов


def test_empty_comments_renders_ok(monkeypatch):
    class R:
        stdout = '{"summary":{"files_reviewed":1,"comments":0},"comments":[]}'

    monkeypatch.setattr("review_bot.reviewers.ocr.subprocess.run", lambda *a, **k: R())
    out = OcrAdapter().run(Path("/tmp/x"), "main", "feature")
    assert "Замечаний нет" in out


def test_bad_json_gives_placeholder(monkeypatch):
    class R:
        stdout = "не json"

    monkeypatch.setattr("review_bot.reviewers.ocr.subprocess.run", lambda *a, **k: R())
    out = OcrAdapter().run(Path("/tmp/x"), "main", "feature")
    assert out.strip()  # непустой плейсхолдер
