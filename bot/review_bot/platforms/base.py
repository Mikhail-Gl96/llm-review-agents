from typing import Protocol, runtime_checkable

from review_bot.models import IncomingComment, PRContext


@runtime_checkable
class PlatformAdapter(Protocol):
    name: str

    def verify(self, headers: dict, body: bytes) -> bool: ...

    def parse_event(self, payload: dict) -> IncomingComment | None: ...

    def get_pr_context(self, payload: dict) -> PRContext: ...

    def check_authz(self, ctx: PRContext, author: str) -> bool: ...

    def checkout_token(self) -> str | None: ...

    def post_comment(self, ctx: PRContext, markdown: str) -> None: ...
