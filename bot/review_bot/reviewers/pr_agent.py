import os
import subprocess
from pathlib import Path


class PrAgentAdapter:
    key = "pr.agent"

    def __init__(self, timeout: int = 900) -> None:
        self._timeout = timeout

    def run(self, checkout_dir: Path, base_ref: str, head_ref: str) -> str:
        env = dict(os.environ)
        env["CONFIG__GIT_PROVIDER"] = "local"
        subprocess.run(
            ["pr-agent", "--pr_url", base_ref, "review"],
            cwd=str(checkout_dir), check=True, capture_output=True, text=True,
            timeout=self._timeout, env=env,
        )
        review = Path(checkout_dir) / "review.md"
        if review.exists():
            return review.read_text(encoding="utf-8").strip() or "_pr-agent: пустой review.md_"
        return "_pr-agent: review.md не создан_"
