from dataclasses import dataclass


@dataclass(frozen=True)
class IncomingComment:
    event_id: str
    author: str
    body: str
    is_bot: bool


@dataclass(frozen=True)
class PRContext:
    platform: str
    repo: str
    project_id: str
    pr_number: int
    base_ref: str
    head_ref: str
    head_sha: str
    clone_url: str
    author: str
