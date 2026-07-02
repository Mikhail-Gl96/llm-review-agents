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

    def checkout_token(self) -> str | None:
        return self._token

    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json"}
