import hmac

import httpx

from review_bot.models import IncomingComment, PRContext


class GitLabAdapter:
    name = "gitlab"

    def __init__(self, token: str, webhook_secret: str,
                 api_base: str = "https://gitlab.com/api/v4",
                 bot_username: str = "", client: httpx.Client | None = None) -> None:
        self._token = token
        self._secret = webhook_secret
        self._api = api_base.rstrip("/")
        self._bot = bot_username
        self._client = client or httpx.Client(timeout=30)

    def verify(self, headers: dict, body: bytes) -> bool:
        return hmac.compare_digest(headers.get("x-gitlab-token", ""), self._secret)

    def parse_event(self, payload: dict) -> IncomingComment | None:
        if payload.get("object_kind") != "note":
            return None
        attrs = payload.get("object_attributes") or {}
        if attrs.get("noteable_type") != "MergeRequest":
            return None
        author = (payload.get("user") or {}).get("username", "")
        return IncomingComment(
            event_id=str(attrs.get("id")),
            author=author,
            body=attrs.get("note", ""),
            is_bot=bool(self._bot) and author == self._bot,
        )

    def get_pr_context(self, payload: dict) -> PRContext:
        mr = payload["merge_request"]
        project = payload["project"]
        return PRContext(
            platform="gitlab",
            repo=project.get("path_with_namespace", ""),
            project_id=str(project["id"]),
            pr_number=int(mr["iid"]),
            base_ref=mr["target_branch"],
            head_ref=mr["source_branch"],
            head_sha=(mr.get("last_commit") or {}).get("id", ""),
            clone_url=project["git_http_url"],
            author=(payload.get("user") or {}).get("username", ""),
        )

    def check_authz(self, ctx: PRContext, author: str) -> bool:
        ur = self._client.get(f"{self._api}/users", params={"username": author},
                              headers=self._auth())
        if ur.status_code != 200 or not ur.json():
            return False
        uid = ur.json()[0]["id"]
        mr = self._client.get(f"{self._api}/projects/{ctx.project_id}/members/all/{uid}",
                              headers=self._auth())
        if mr.status_code != 200:
            return False
        return int(mr.json().get("access_level", 0)) >= 30

    def post_comment(self, ctx: PRContext, markdown: str) -> None:
        r = self._client.post(
            f"{self._api}/projects/{ctx.project_id}/merge_requests/{ctx.pr_number}/notes",
            headers=self._auth(), json={"body": markdown})
        r.raise_for_status()

    def checkout_token(self) -> str | None:
        return self._token

    def _auth(self) -> dict:
        return {"PRIVATE-TOKEN": self._token}
