import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse, urlunparse


def _with_token(url: str, token: str | None) -> str:
    if not token or not url.startswith("https://"):
        return url
    p = urlparse(url)
    return urlunparse(p._replace(netloc=f"x-access-token:{token}@{p.netloc}"))


def checkout_pr(clone_url: str, base_ref: str, head_ref: str, token: str | None = None) -> Path:
    d = Path(tempfile.mkdtemp(prefix="review-"))
    url = _with_token(clone_url, token)
    subprocess.run(["git", "clone", "--no-tags", url, str(d)],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(d), "fetch", "origin", base_ref, head_ref],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(d), "checkout", head_ref],
                   check=True, capture_output=True)
    return d


def cleanup(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
