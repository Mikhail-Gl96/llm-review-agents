from pathlib import Path

from review_bot.pipeline import handle_comment
from review_bot.registry import Registry
from review_bot.dedup import SeenEvents
from review_bot.config import Settings
from review_bot.models import IncomingComment, PRContext

CTX = PRContext("github", "o/r", "o/r", 7, "main", "feature", "abc", "url", "author")


class FakePlatform:
    name = "github"

    def __init__(self, comment, authz=True):
        self._c = comment
        self._authz = authz
        self.posted = []

    def verify(self, headers, body):
        return True

    def parse_event(self, payload):
        return self._c

    def get_pr_context(self, payload):
        return CTX

    def check_authz(self, ctx, author):
        return self._authz

    def checkout_token(self):
        return None

    def post_comment(self, ctx, md):
        self.posted.append(md)


class FakeReviewer:
    key = "ocr"

    def run(self, d, base, head):
        return "## Ревью от ocr"


def _reg():
    r = Registry()
    r.register("ocr", FakeReviewer())
    return r


def _patch_checkout(monkeypatch):
    monkeypatch.setattr("review_bot.pipeline.checkout_pr", lambda *a, **k: Path("/tmp/x"))
    monkeypatch.setattr("review_bot.pipeline.cleanup", lambda d: None)


def _call(platform, monkeypatch, allowlist=None):
    _patch_checkout(monkeypatch)
    s = Settings()
    s.allowlist = allowlist or []
    return handle_comment(platform=platform, payload={}, headers={}, raw_body=b"{}",
                          settings=s, reviewers=_reg(), seen=SeenEvents())


def test_happy_path_posts_review(monkeypatch):
    p = FakePlatform(IncomingComment("1", "alice", "@review.ocr", False))
    assert _call(p, monkeypatch) == "reviewed"
    assert p.posted == ["## Ревью от ocr"]


def test_no_mention(monkeypatch):
    p = FakePlatform(IncomingComment("1", "alice", "обычный текст", False))
    assert _call(p, monkeypatch) == "no-mention"
    assert p.posted == []


def test_bot_author_ignored(monkeypatch):
    p = FakePlatform(IncomingComment("1", "bot", "@review", True))
    assert _call(p, monkeypatch) == "ignored-bot"


def test_duplicate(monkeypatch):
    _patch_checkout(monkeypatch)
    p = FakePlatform(IncomingComment("dup", "alice", "@review", False))
    seen = SeenEvents()
    s = Settings()
    a = handle_comment(platform=p, payload={}, headers={}, raw_body=b"{}", settings=s, reviewers=_reg(), seen=seen)
    b = handle_comment(platform=p, payload={}, headers={}, raw_body=b"{}", settings=s, reviewers=_reg(), seen=seen)
    assert a == "reviewed" and b == "duplicate"


def test_unauthorized_posts_notice(monkeypatch):
    p = FakePlatform(IncomingComment("1", "stranger", "@review", False), authz=False)
    assert _call(p, monkeypatch) == "unauthorized"
    assert p.posted and "прав" in p.posted[0]


def test_allowlist_restricts(monkeypatch):
    p = FakePlatform(IncomingComment("1", "alice", "@review", False), authz=True)
    assert _call(p, monkeypatch, allowlist=["bob"]) == "unauthorized"
