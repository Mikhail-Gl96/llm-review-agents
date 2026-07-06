import hashlib
import hmac

import httpx

from review_bot.models import IncomingComment, PRContext


class GitHubAdapter:
    name = "github"

    def __init__(self, token: str, webhook_secret: str,
                 api_base: str = "https://api.github.com",
                 bot_login: str = "", client: httpx.Client | None = None) -> None:
        self._token = token
        self._secret = webhook_secret
        self._api = api_base.rstrip("/")
        self._bot_login = bot_login
        self._client = client or httpx.Client(timeout=30)

    def verify(self, headers: dict, body: bytes) -> bool:
        sig = headers.get("x-hub-signature-256", "")
        expected = "sha256=" + hmac.new(self._secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)

    def parse_event(self, payload: dict) -> IncomingComment | None:
        if payload.get("action") != "created":
            return None
        issue = payload.get("issue") or {}
        if "pull_request" not in issue:
            return None
        comment = payload.get("comment") or {}
        user = comment.get("user") or {}
        return IncomingComment(
            event_id=str(comment.get("id")),
            author=user.get("login", ""),
            body=comment.get("body", ""),
            is_bot=user.get("type") == "Bot",
        )

    def get_pr_context(self, payload: dict) -> PRContext:
        repo = payload["repository"]["full_name"]
        number = int(payload["issue"]["number"])
        r = self._client.get(f"{self._api}/repos/{repo}/pulls/{number}", headers=self._auth())
        r.raise_for_status()
        pr = r.json()
        return PRContext(
            platform="github", repo=repo, project_id=repo, pr_number=number,
            base_ref=pr["base"]["ref"], head_ref=pr["head"]["ref"],
            head_sha=pr["head"]["sha"], clone_url=payload["repository"]["clone_url"],
            author=(payload["issue"].get("user") or {}).get("login", ""),
        )

    def check_authz(self, ctx: PRContext, author: str) -> bool:
        r = self._client.get(
            f"{self._api}/repos/{ctx.repo}/collaborators/{author}/permission",
            headers=self._auth())
        if r.status_code != 200:
            return False
        return r.json().get("permission") in {"admin", "write", "maintain"}

    def post_comment(self, ctx: PRContext, markdown: str) -> str:
        r = self._client.post(
            f"{self._api}/repos/{ctx.repo}/issues/{ctx.pr_number}/comments",
            headers=self._auth(), json={"body": markdown})
        r.raise_for_status()
        return str(r.json().get("id", ""))

    def update_comment(self, ctx: PRContext, comment_id: str, markdown: str) -> None:
        r = self._client.patch(
            f"{self._api}/repos/{ctx.repo}/issues/comments/{comment_id}",
            headers=self._auth(), json={"body": markdown})
        r.raise_for_status()

    def checkout_token(self) -> str | None:
        return self._token

    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json"}
