import os
from dataclasses import dataclass, field


def _csv(name: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, "").split(",") if x.strip()]


@dataclass
class Settings:
    default_engine: str = "ocr"
    enabled_engines: list[str] = field(default_factory=lambda: ["ocr", "pr.agent"])
    allowlist: list[str] = field(default_factory=list)
    review_timeout: int = 900
    github_token: str = ""
    github_webhook_secret: str = ""
    github_bot_login: str = ""
    github_api_base: str = "https://api.github.com"
    gitlab_token: str = ""
    gitlab_webhook_secret: str = ""
    gitlab_bot_username: str = ""
    gitlab_api_base: str = "https://gitlab.com/api/v4"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            default_engine=os.getenv("DEFAULT_ENGINE", "ocr"),
            enabled_engines=_csv("ENABLED_ENGINES") or ["ocr", "pr.agent"],
            allowlist=_csv("ALLOWLIST"),
            review_timeout=int(os.getenv("REVIEW_TIMEOUT", "900")),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            github_webhook_secret=os.getenv("GITHUB_WEBHOOK_SECRET", ""),
            github_bot_login=os.getenv("GITHUB_BOT_LOGIN", ""),
            github_api_base=os.getenv("GITHUB_API_BASE", "https://api.github.com"),
            gitlab_token=os.getenv("GITLAB_TOKEN", ""),
            gitlab_webhook_secret=os.getenv("GITLAB_WEBHOOK_SECRET", ""),
            gitlab_bot_username=os.getenv("GITLAB_BOT_USERNAME", ""),
            gitlab_api_base=os.getenv("GITLAB_API_BASE", "https://gitlab.com/api/v4"),
        )
