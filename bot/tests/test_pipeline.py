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
        self.updated = []
        self._next_id = 100

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
        self._next_id += 1
        self.posted.append(md)
        return str(self._next_id)

    def update_comment(self, ctx, cid, md):
        self.updated.append((cid, md))


class FakeReviewer:
    key = "ocr"

    def run(self, d, base, head):
        return "## Ревью от ocr"


def _reg(reviewer=None):
    r = Registry()
    r.register("ocr", reviewer or FakeReviewer())
    return r


def _patch_checkout(monkeypatch):
    monkeypatch.setattr("review_bot.pipeline.checkout_pr", lambda *a, **k: Path("/tmp/x"))
    monkeypatch.setattr("review_bot.pipeline.cleanup", lambda d: None)


def _call(platform, monkeypatch, allowlist=None, reviewer=None):
    _patch_checkout(monkeypatch)
    s = Settings()
    s.allowlist = allowlist or []
    return handle_comment(platform=platform, payload={}, headers={}, raw_body=b"{}",
                          settings=s, reviewers=_reg(reviewer), seen=SeenEvents())


def test_happy_path_acks_then_updates_with_review(monkeypatch):
    p = FakePlatform(IncomingComment("1", "alice", "@review.ocr", False))
    assert _call(p, monkeypatch) == "reviewed"
    # сначала «взял в работу», потом тот же коммент обновлён ревью
    assert len(p.posted) == 1 and "Взял в работу" in p.posted[0]
    assert p.updated == [("101", "## Ревью от ocr")]


def test_no_mention(monkeypatch):
    p = FakePlatform(IncomingComment("1", "alice", "обычный текст", False))
    assert _call(p, monkeypatch) == "no-mention"
    assert p.posted == [] and p.updated == []


def test_bot_author_ignored(monkeypatch):
    p = FakePlatform(IncomingComment("1", "bot", "@review", True))
    assert _call(p, monkeypatch) == "ignored-bot"
    assert p.posted == []


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
    assert p.updated == []


def test_allowlist_restricts(monkeypatch):
    p = FakePlatform(IncomingComment("1", "alice", "@review", False), authz=True)
    assert _call(p, monkeypatch, allowlist=["bob"]) == "unauthorized"


def test_error_updates_comment_and_redacts_token(monkeypatch):
    class BoomReviewer:
        key = "ocr"

        def run(self, d, base, head):
            raise RuntimeError("clone failed: https://oauth2:SECRET123@gitlab.com/x.git")

    p = FakePlatform(IncomingComment("1", "alice", "@review.ocr", False))
    assert _call(p, monkeypatch, reviewer=BoomReviewer()) == "error"
    assert len(p.posted) == 1 and "Взял в работу" in p.posted[0]
    assert p.updated and "Ошибка ревью" in p.updated[0][1]
    # токен из URL отредактирован
    assert "SECRET123" not in p.updated[0][1] and "://***@" in p.updated[0][1]
