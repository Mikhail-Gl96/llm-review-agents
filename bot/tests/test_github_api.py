import json

import httpx

from review_bot.models import PRContext
from review_bot.platforms.github import GitHubAdapter


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com")


PAYLOAD = {"issue": {"number": 7, "user": {"login": "author"}},
           "repository": {"full_name": "o/r", "clone_url": "https://github.com/o/r.git"}}


def test_get_pr_context():
    def handler(req):
        assert req.url.path == "/repos/o/r/pulls/7"
        return httpx.Response(200, json={"base": {"ref": "main"},
                                         "head": {"ref": "feature", "sha": "abc123"}})
    a = GitHubAdapter("t", "s", client=_client(handler))
    ctx = a.get_pr_context(PAYLOAD)
    assert ctx.repo == "o/r" and ctx.pr_number == 7
    assert ctx.base_ref == "main" and ctx.head_ref == "feature" and ctx.head_sha == "abc123"
    assert ctx.clone_url.endswith("o/r.git")


def test_check_authz_true_for_write():
    def handler(req):
        assert req.url.path == "/repos/o/r/collaborators/alice/permission"
        return httpx.Response(200, json={"permission": "write"})
    a = GitHubAdapter("t", "s", client=_client(handler))
    ctx = PRContext("github", "o/r", "o/r", 7, "main", "feature", "abc", "url", "author")
    assert a.check_authz(ctx, "alice") is True


def test_check_authz_false_for_read_or_404():
    a_read = GitHubAdapter("t", "s", client=_client(lambda r: httpx.Response(200, json={"permission": "read"})))
    a_404 = GitHubAdapter("t", "s", client=_client(lambda r: httpx.Response(404, json={})))
    ctx = PRContext("github", "o/r", "o/r", 7, "main", "feature", "abc", "url", "author")
    assert a_read.check_authz(ctx, "bob") is False
    assert a_404.check_authz(ctx, "bob") is False


def test_post_comment():
    seen = {}

    def handler(req):
        seen["path"] = req.url.path
        seen["body"] = json.loads(req.content)["body"]
        return httpx.Response(201, json={"id": 1})
    a = GitHubAdapter("t", "s", client=_client(handler))
    ctx = PRContext("github", "o/r", "o/r", 7, "main", "feature", "abc", "url", "author")
    nid = a.post_comment(ctx, "## Ревью")
    assert nid == "1"
    assert seen["path"] == "/repos/o/r/issues/7/comments"
    assert seen["body"] == "## Ревью"


def test_update_comment():
    seen = {}

    def handler(req):
        seen["method"] = req.method
        seen["path"] = req.url.path
        seen["body"] = json.loads(req.content)["body"]
        return httpx.Response(200, json={"id": 5})
    a = GitHubAdapter("t", "s", client=_client(handler))
    ctx = PRContext("github", "o/r", "o/r", 7, "main", "feature", "abc", "url", "author")
    a.update_comment(ctx, "5", "обновлено")
    assert seen["method"] == "PATCH"
    assert seen["path"] == "/repos/o/r/issues/comments/5"
    assert seen["body"] == "обновлено"
