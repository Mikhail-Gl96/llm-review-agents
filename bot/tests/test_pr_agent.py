from review_bot.reviewers.pr_agent import PrAgentAdapter


def test_run_returns_review_md(monkeypatch, tmp_path):
    (tmp_path / "review.md").write_text("## PR-Agent\nнашёл баг", encoding="utf-8")
    calls = {}

    def fake_run(cmd, cwd, check, capture_output, text, timeout=None, env=None):
        calls["cmd"] = cmd

        class R:
            stdout = ""

        return R()

    monkeypatch.setattr("review_bot.reviewers.pr_agent.subprocess.run", fake_run)
    out = PrAgentAdapter().run(tmp_path, "master", "feature")
    assert "PR-Agent" in out
    assert calls["cmd"][0] == "pr-agent" and "review" in calls["cmd"]


def test_run_placeholder_when_no_file(monkeypatch, tmp_path):
    monkeypatch.setattr("review_bot.reviewers.pr_agent.subprocess.run",
                        lambda *a, **k: type("R", (), {"stdout": ""})())
    out = PrAgentAdapter().run(tmp_path, "master", "feature")
    assert out  # непустой плейсхолдер
