import json

import httpx

from review_bot.platforms.gitlab import GitLabAdapter
from review_bot.models import PRContext


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://gitlab.com/api/v4")


NOTE = {
    "object_kind": "note",
    "user": {"username": "alice"},
    "object_attributes": {"id": 99, "note": "@review.ocr", "noteable_type": "MergeRequest"},
    "merge_request": {"iid": 3, "source_branch": "feature", "target_branch": "main",
                      "last_commit": {"id": "sha9"}},
    "project": {"id": 12, "git_http_url": "https://gitlab.com/o/r.git",
                "path_with_namespace": "o/r"},
}


def _a(client=None):
    return GitLabAdapter(token="t", webhook_secret="s", api_base="https://gitlab.com/api/v4",
                         bot_username="bot", client=client)


def test_verify_token():
    a = _a()
    assert a.verify({"x-gitlab-token": "s"}, b"{}") is True
    assert a.verify({"x-gitlab-token": "nope"}, b"{}") is False


def test_parse_note_on_mr():
    c = _a().parse_event(NOTE)
    assert c.event_id == "99" and c.author == "alice" and c.body == "@review.ocr"
    assert c.is_bot is False


def test_parse_ignores_non_mr_note():
    n = {"object_kind": "note", "object_attributes": {"noteable_type": "Issue"}}
    assert _a().parse_event(n) is None


def test_parse_flags_bot_author():
    n = {**NOTE, "user": {"username": "bot"}}
    assert _a().parse_event(n).is_bot is True


def test_get_pr_context():
    ctx = _a().get_pr_context(NOTE)
    assert ctx.platform == "gitlab" and ctx.project_id == "12" and ctx.pr_number == 3
    assert ctx.base_ref == "main" and ctx.head_ref == "feature"
    assert ctx.clone_url.endswith("o/r.git")


def test_check_authz_by_access_level():
    def make(level):
        def handler(req):
            if req.url.path.endswith("/users"):
                return httpx.Response(200, json=[{"id": 1}])
            return httpx.Response(200, json={"access_level": level})
        return _a(_client(handler))
    ctx = PRContext("gitlab", "o/r", "12", 3, "main", "feature", "sha", "url", "alice")
    assert make(30).check_authz(ctx, "alice") is True
    assert make(10).check_authz(ctx, "alice") is False


def test_post_comment():
    seen = {}

    def handler(req):
        seen["path"] = req.url.path
        seen["body"] = json.loads(req.content)["body"]
        return httpx.Response(201, json={"id": 1})
    ctx = PRContext("gitlab", "o/r", "12", 3, "main", "feature", "sha", "url", "alice")
    nid = _a(_client(handler)).post_comment(ctx, "## Ревью")
    assert nid == "1"
    assert seen["path"] == "/api/v4/projects/12/merge_requests/3/notes"
    assert seen["body"] == "## Ревью"


def test_update_comment():
    seen = {}

    def handler(req):
        seen["method"] = req.method
        seen["path"] = req.url.path
        seen["body"] = json.loads(req.content)["body"]
        return httpx.Response(200, json={"id": 7})
    ctx = PRContext("gitlab", "o/r", "12", 3, "main", "feature", "sha", "url", "alice")
    _a(_client(handler)).update_comment(ctx, "7", "обновлено")
    assert seen["method"] == "PUT"
    assert seen["path"] == "/api/v4/projects/12/merge_requests/3/notes/7"
    assert seen["body"] == "обновлено"
