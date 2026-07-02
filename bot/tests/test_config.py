from review_bot.config import Settings


def test_defaults(monkeypatch):
    for k in ("DEFAULT_ENGINE", "ENABLED_ENGINES", "ALLOWLIST"):
        monkeypatch.delenv(k, raising=False)
    s = Settings.from_env()
    assert s.default_engine == "ocr"
    assert s.enabled_engines == ["ocr", "pr.agent"]
    assert s.allowlist == []


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("DEFAULT_ENGINE", "pr.agent")
    monkeypatch.setenv("ALLOWLIST", "alice, bob")
    s = Settings.from_env()
    assert s.default_engine == "pr.agent"
    assert s.allowlist == ["alice", "bob"]
