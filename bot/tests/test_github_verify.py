import hashlib
import hmac

from review_bot.platforms.github import GitHubAdapter

SECRET = "s3cret"


def _sig(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def _adapter():
    return GitHubAdapter(token="t", webhook_secret=SECRET, api_base="https://api.github.com")


def test_verify_ok_and_bad():
    a = _adapter()
    body = b'{"x":1}'
    assert a.verify({"x-hub-signature-256": _sig(body)}, body) is True
    assert a.verify({"x-hub-signature-256": "sha256=deadbeef"}, body) is False


def test_parse_pr_comment():
    payload = {
        "action": "created",
        "issue": {"number": 7, "pull_request": {"url": "..."},
                  "user": {"login": "author"}},
        "comment": {"id": 42, "body": "@review.ocr", "user": {"login": "alice", "type": "User"}},
        "repository": {"full_name": "o/r", "clone_url": "https://github.com/o/r.git"},
    }
    c = _adapter().parse_event(payload)
    assert c.event_id == "42" and c.author == "alice" and c.is_bot is False
    assert c.body == "@review.ocr"


def test_parse_ignores_non_pr_and_non_created():
    a = _adapter()
    assert a.parse_event({"action": "created", "issue": {"number": 1}, "comment": {}}) is None
    assert a.parse_event({"action": "edited", "issue": {"pull_request": {}}}) is None


def test_parse_flags_bot_author():
    payload = {"action": "created",
               "issue": {"number": 1, "pull_request": {}, "user": {"login": "a"}},
               "comment": {"id": 1, "body": "hi", "user": {"login": "bot", "type": "Bot"}}}
    assert _adapter().parse_event(payload).is_bot is True
