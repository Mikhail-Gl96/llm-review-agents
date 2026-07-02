from pathlib import Path

from review_bot.reviewers.ocr import OcrAdapter


def test_run_builds_command_and_returns_stdout(monkeypatch):
    calls = {}

    class R:
        stdout = "## Ревью\nвсё ок"

    def fake_run(cmd, cwd, check, capture_output, text, timeout=None):
        calls["cmd"] = cmd
        calls["cwd"] = cwd
        return R()

    monkeypatch.setattr("review_bot.reviewers.ocr.subprocess.run", fake_run)
    out = OcrAdapter().run(Path("/tmp/x"), "main", "feature")
    assert out.strip().startswith("## Ревью")
    assert calls["cmd"][:2] == ["ocr", "review"]
    assert "--from" in calls["cmd"] and "origin/main" in calls["cmd"]
    assert "feature" in calls["cmd"]
    assert calls["cwd"] == "/tmp/x"


def test_empty_output_has_placeholder(monkeypatch):
    class R:
        stdout = "   "

    monkeypatch.setattr("review_bot.reviewers.ocr.subprocess.run", lambda *a, **k: R())
    out = OcrAdapter().run(Path("/tmp/x"), "main", "feature")
    assert out  # непустой плейсхолдер
