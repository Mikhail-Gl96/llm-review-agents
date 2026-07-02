import subprocess
from pathlib import Path

from review_bot.checkout import checkout_pr, cleanup


def _run(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


def _make_repo(tmp_path: Path) -> str:
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    _run("git", "init", "--bare", str(origin))
    _run("git", "clone", str(origin), str(work))
    _run("git", "-C", str(work), "config", "user.email", "t@t")
    _run("git", "-C", str(work), "config", "user.name", "t")
    (work / "base.txt").write_text("base")
    _run("git", "-C", str(work), "add", "-A")
    _run("git", "-C", str(work), "commit", "-m", "base")
    _run("git", "-C", str(work), "branch", "-M", "main")
    _run("git", "-C", str(work), "checkout", "-b", "feature")
    (work / "feat.txt").write_text("feat")
    _run("git", "-C", str(work), "add", "-A")
    _run("git", "-C", str(work), "commit", "-m", "feat")
    _run("git", "-C", str(work), "push", "origin", "main", "feature")
    return origin.as_uri()  # file:// URL


def test_checkout_gets_head(tmp_path):
    url = _make_repo(tmp_path)
    d = checkout_pr(url, "main", "feature")
    try:
        assert (d / "feat.txt").exists()  # head-ветка выкачана
        assert (d / "base.txt").exists()
    finally:
        cleanup(d)
    assert not d.exists()
