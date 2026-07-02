import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from review_bot.main import create_app
from review_bot.config import Settings

SECRET = "hooksecret"


def _client():
    s = Settings()
    s.github_webhook_secret = SECRET
    s.github_token = "t"
    return TestClient(create_app(s))


def test_healthz():
    assert _client().get("/healthz").json() == {"status": "ok"}


def test_github_webhook_rejects_bad_signature():
    r = _client().post("/webhook/github", content=b"{}",
                       headers={"x-hub-signature-256": "sha256=bad",
                                "x-github-event": "issue_comment"})
    assert r.json()["result"] == "invalid-signature"


def test_github_webhook_ignores_non_mention():
    payload = {"action": "created",
               "issue": {"number": 1, "pull_request": {}, "user": {"login": "a"}},
               "comment": {"id": 5, "body": "просто коммент", "user": {"login": "alice", "type": "User"}},
               "repository": {"full_name": "o/r", "clone_url": "https://github.com/o/r.git"}}
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    r = _client().post("/webhook/github", content=body,
                       headers={"x-hub-signature-256": sig, "x-github-event": "issue_comment"})
    assert r.json()["result"] == "no-mention"
