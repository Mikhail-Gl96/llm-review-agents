# Бот-диспетчер ревью по комментарию (SP2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Центральный webhook-сервис, который на упоминание `@review[.движок]` в комментарии PR/MR запускает выбранного ревьюера на чекауте PR и постит результат ответным комментом.

**Architecture:** FastAPI-сервис в модуле `bot/`. Конвейер: verify подписи → parse события → дедуп/анти-loop → парсинг `@review[.движок]` → авторизация (платформа + allowlist) → checkout PR во временную папку → reviewer-адаптер гоняет движок в локальном режиме → markdown → пост коммента. Две точки расширения: реестр ревьюеров (`ocr`, `pr.agent`) и реестр платформ (`github`, `gitlab`).

**Tech Stack:** Python 3.10+, FastAPI, httpx (исходящие API + `httpx.MockTransport` в тестах), pytest. Ревьюеры вызываются как внешние CLI (`ocr`, `pr-agent`) через subprocess. Деплой — Docker (python+node+git).

**Спецификация:** [SP2 design](../specs/2026-07-02-comment-triggered-review-bot-design.md).

## Global Constraints

- **Модуль `bot/`**, пакет `review_bot`, самодостаточный Python-проект (`bot/pyproject.toml`, `bot/.venv`).
- **Платформы v1:** `github` + `gitlab`. Bitbucket — позже через тот же интерфейс платформ-адаптера (не в этом плане).
- **Маршрутизация:** парсинг текста коммента на `@review` + опциональный `.<движок>`; ключи реестра — `ocr` и `pr.agent`; **дефолт — `ocr`** (нет суффикса / неизвестный суффикс → дефолт; нет `@review` → не триггерим).
- **Один бот-app на платформу**; `@review.ocr` — это парсинг текста, не отдельный аккаунт.
- **Reviewer-адаптер:** интерфейс `run(checkout_dir: Path, base_ref: str, head_ref: str) -> str` (markdown).
- **Единый постинг:** адаптер возвращает markdown; постит диспетчер через платформ-адаптер.
- **Безопасность (с старта):** verify подписи вебхука; allowlist (платформенная проверка прав + опциональный список логинов); анти-loop (игнор комментов самого бота); дедуп по id события; таймаут ревью.
- **Переиспользуем локальный режим SP1** (те же CLI `ocr`/`pr-agent` на чекауте).
- **Пользовательские строки (комменты бота) — на русском.**
- **Команды тестов:** `bot/.venv/bin/python -m pytest <путь> -v`.

---

## File Structure

```
bot/
  pyproject.toml            # проект review-bot + deps (Task 1)
  .gitignore                # .venv, __pycache__, .pytest_cache, review-*/
  .env.example              # шаблон конфигурации (Task 11)
  Dockerfile                # python+node+git+ocr+pr-agent (Task 11)
  README.md                 # деплой, регистрация вебхуков, конфиг (Task 11)
  review_bot/
    __init__.py
    config.py               # Settings.from_env()                     (Task 1)
    models.py               # IncomingComment, PRContext              (Task 1)
    registry.py             # Registry                                (Task 2)
    router.py               # resolve_engine()                        (Task 2)
    dedup.py                # SeenEvents                              (Task 2)
    checkout.py             # checkout_pr(), cleanup()                (Task 3)
    reviewers/
      __init__.py
      base.py               # ReviewerAdapter Protocol               (Task 1)
      ocr.py                # OcrAdapter                              (Task 4)
      pr_agent.py           # PrAgentAdapter                         (Task 9)
    platforms/
      __init__.py
      base.py               # PlatformAdapter Protocol               (Task 1)
      github.py             # GitHubAdapter                          (Tasks 5,6)
      gitlab.py             # GitLabAdapter                          (Task 10)
    pipeline.py             # handle_comment()                       (Task 7)
    main.py                 # FastAPI app + routes + wiring          (Tasks 8,10,11)
  tests/
    conftest.py
    test_config.py test_models.py test_router.py test_registry.py test_dedup.py
    test_checkout.py test_ocr.py test_github_verify.py test_github_api.py
    test_pipeline.py test_app.py test_pr_agent.py test_gitlab.py
```

## Before you start

```bash
git switch -c feature/review-bot
```

---

## Task 1: Проект, конфиг, модели, протоколы

**Files:**
- Create: `bot/pyproject.toml`, `bot/.gitignore`, `bot/review_bot/__init__.py`,
  `bot/review_bot/config.py`, `bot/review_bot/models.py`,
  `bot/review_bot/reviewers/__init__.py`, `bot/review_bot/reviewers/base.py`,
  `bot/review_bot/platforms/__init__.py`, `bot/review_bot/platforms/base.py`,
  `bot/tests/conftest.py`, `bot/tests/test_config.py`, `bot/tests/test_models.py`

**Interfaces:**
- Produces: `Settings` (dataclass, `from_env()`); `IncomingComment(event_id,author,body,is_bot)`;
  `PRContext(platform,repo,project_id,pr_number,base_ref,head_ref,head_sha,clone_url,author)`;
  `ReviewerAdapter` Protocol (`key: str`, `run(checkout_dir,base_ref,head_ref)->str`);
  `PlatformAdapter` Protocol (`name`, `verify`, `parse_event`, `get_pr_context`, `check_authz`, `checkout_token`, `post_comment`).

- [ ] **Step 1: Скелет проекта**

`bot/pyproject.toml`:
```toml
[project]
name = "review-bot"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["fastapi>=0.110", "uvicorn[standard]>=0.29", "httpx>=0.27"]

[project.optional-dependencies]
dev = ["pytest>=8"]

[tool.setuptools.packages.find]
include = ["review_bot*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`bot/.gitignore`:
```
.venv/
__pycache__/
.pytest_cache/
review-*/
*.egg-info/
```

Пустые: `bot/review_bot/__init__.py`, `bot/review_bot/reviewers/__init__.py`,
`bot/review_bot/platforms/__init__.py`, `bot/tests/conftest.py`.

- [ ] **Step 2: venv + установка**

```bash
python3 -m venv bot/.venv
bot/.venv/bin/pip install -e "./bot[dev]"
bot/.venv/bin/python -c "import fastapi, httpx, pytest; print('deps OK')"
```
Expected: `deps OK`.

- [ ] **Step 3: Failing test — config + models**

`bot/tests/test_config.py`:
```python
import os
from review_bot.config import Settings

def test_defaults(monkeypatch):
    for k in ("DEFAULT_ENGINE","ENABLED_ENGINES","ALLOWLIST"):
        monkeypatch.delenv(k, raising=False)
    s = Settings.from_env()
    assert s.default_engine == "ocr"
    assert s.enabled_engines == ["ocr", "pr.agent"]
    assert s.allowlist == []

def test_env_overrides(monkeypatch):
    monkeypatch.setenv("DEFAULT_ENGINE", "pr.agent")
    monkeypatch.setenv("ALLOWLIST", "alice, bob")
    s = Settings.from_env()
    assert s.default_engine == "pr.agent"
    assert s.allowlist == ["alice", "bob"]
```

`bot/tests/test_models.py`:
```python
from review_bot.models import IncomingComment, PRContext

def test_models_construct():
    c = IncomingComment(event_id="1", author="alice", body="@review", is_bot=False)
    assert c.author == "alice" and c.is_bot is False
    ctx = PRContext(platform="github", repo="o/r", project_id="o/r", pr_number=7,
                    base_ref="main", head_ref="feat", head_sha="abc",
                    clone_url="https://x/o/r.git", author="alice")
    assert ctx.pr_number == 7 and ctx.base_ref == "main"
```

- [ ] **Step 4: Run — verify fail**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_config.py bot/tests/test_models.py -v`
Expected: FAIL (`ModuleNotFoundError: review_bot.config`).

- [ ] **Step 5: Implement**

`bot/review_bot/models.py`:
```python
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
```

`bot/review_bot/config.py`:
```python
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
```

`bot/review_bot/reviewers/base.py`:
```python
from pathlib import Path
from typing import Protocol, runtime_checkable

@runtime_checkable
class ReviewerAdapter(Protocol):
    key: str
    def run(self, checkout_dir: Path, base_ref: str, head_ref: str) -> str: ...
```

`bot/review_bot/platforms/base.py`:
```python
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
```

- [ ] **Step 6: Run — verify pass**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_config.py bot/tests/test_models.py -v`
Expected: PASS (4 passed).

- [ ] **Step 7: Commit**

```bash
git add bot
git commit -m "feat(bot): проект, конфиг, модели, протоколы адаптеров" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" -- bot
```

---

## Task 2: Ядро — роутер упоминаний, реестр, дедуп

**Files:**
- Create: `bot/review_bot/router.py`, `bot/review_bot/registry.py`, `bot/review_bot/dedup.py`,
  `bot/tests/test_router.py`, `bot/tests/test_registry.py`, `bot/tests/test_dedup.py`

**Interfaces:**
- Produces: `resolve_engine(text, *, default, known) -> str | None`;
  `Registry` (`register(key,item)`, `get(key)`, `keys()->set`);
  `SeenEvents(capacity=1024)` (`seen(event_id)->bool`).

- [ ] **Step 1: Failing tests**

`bot/tests/test_router.py`:
```python
from review_bot.router import resolve_engine

KNOWN = {"ocr", "pr.agent"}

def test_bare_mention_defaults():
    assert resolve_engine("привет @review посмотри", default="ocr", known=KNOWN) == "ocr"

def test_named_engines():
    assert resolve_engine("@review.ocr", default="ocr", known=KNOWN) == "ocr"
    assert resolve_engine("@review.pr.agent go", default="ocr", known=KNOWN) == "pr.agent"

def test_unknown_suffix_falls_back_to_default():
    assert resolve_engine("@review.foobar", default="ocr", known=KNOWN) == "ocr"

def test_no_mention_returns_none():
    assert resolve_engine("обычный коммент", default="ocr", known=KNOWN) is None
    assert resolve_engine("@reviewer не бот", default="ocr", known=KNOWN) is None
```

`bot/tests/test_registry.py`:
```python
from review_bot.registry import Registry

def test_register_and_get():
    r = Registry()
    r.register("ocr", object())
    assert r.get("ocr") is not None
    assert r.get("missing") is None
    assert r.keys() == {"ocr"}
```

`bot/tests/test_dedup.py`:
```python
from review_bot.dedup import SeenEvents

def test_first_unseen_then_seen():
    s = SeenEvents()
    assert s.seen("e1") is False
    assert s.seen("e1") is True

def test_capacity_evicts_oldest():
    s = SeenEvents(capacity=2)
    s.seen("a"); s.seen("b"); s.seen("c")   # 'a' вытеснен
    assert s.seen("a") is False
```

- [ ] **Step 2: Run — verify fail**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_router.py bot/tests/test_registry.py bot/tests/test_dedup.py -v`
Expected: FAIL (модули не найдены).

- [ ] **Step 3: Implement**

`bot/review_bot/router.py`:
```python
import re

_MENTION = re.compile(r"@review(?:\.([\w.\-]+))?\b")

def resolve_engine(text: str, *, default: str, known: set[str]) -> str | None:
    m = _MENTION.search(text or "")
    if not m:
        return None
    suffix = m.group(1)
    if not suffix:
        return default
    return suffix if suffix in known else default
```

`bot/review_bot/registry.py`:
```python
class Registry:
    def __init__(self) -> None:
        self._items: dict[str, object] = {}

    def register(self, key: str, item: object) -> None:
        self._items[key] = item

    def get(self, key: str):
        return self._items.get(key)

    def keys(self) -> set[str]:
        return set(self._items)
```

`bot/review_bot/dedup.py`:
```python
from collections import OrderedDict

class SeenEvents:
    def __init__(self, capacity: int = 1024) -> None:
        self._cap = capacity
        self._d: "OrderedDict[str, None]" = OrderedDict()

    def seen(self, event_id: str) -> bool:
        if event_id in self._d:
            return True
        self._d[event_id] = None
        if len(self._d) > self._cap:
            self._d.popitem(last=False)
        return False
```

- [ ] **Step 4: Run — verify pass**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_router.py bot/tests/test_registry.py bot/tests/test_dedup.py -v`
Expected: PASS (все зелёные).

- [ ] **Step 5: Commit**

```bash
git add bot/review_bot bot/tests
git commit -m "feat(bot): роутер @review, реестр адаптеров, дедуп событий" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" -- bot/review_bot bot/tests
```

---

## Task 3: Checkout PR (git)

**Files:**
- Create: `bot/review_bot/checkout.py`, `bot/tests/test_checkout.py`

**Interfaces:**
- Produces: `checkout_pr(clone_url, base_ref, head_ref, token=None) -> Path`; `cleanup(path) -> None`.

- [ ] **Step 1: Failing test (герметичный, на локальном bare-репо)**

`bot/tests/test_checkout.py`:
```python
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
        assert (d / "feat.txt").exists()   # head-ветка выкачана
        assert (d / "base.txt").exists()
    finally:
        cleanup(d)
    assert not d.exists()
```

- [ ] **Step 2: Run — verify fail**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_checkout.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

`bot/review_bot/checkout.py`:
```python
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
```

- [ ] **Step 4: Run — verify pass**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_checkout.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/review_bot/checkout.py bot/tests/test_checkout.py
git commit -m "feat(bot): checkout PR во временную папку + cleanup" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" -- bot/review_bot/checkout.py bot/tests/test_checkout.py
```

---

## Task 4: ocr reviewer-адаптер (дефолт)

**Files:**
- Create: `bot/review_bot/reviewers/ocr.py`, `bot/tests/test_ocr.py`

**Interfaces:**
- Consumes: `ReviewerAdapter` protocol (Task 1).
- Produces: `OcrAdapter` (`key="ocr"`, `run(checkout_dir,base_ref,head_ref)->str`).

- [ ] **Step 1: Failing test (subprocess замокан)**

`bot/tests/test_ocr.py`:
```python
from pathlib import Path
from review_bot.reviewers.ocr import OcrAdapter

def test_run_builds_command_and_returns_stdout(monkeypatch):
    calls = {}
    class R: stdout = "## Ревью\nвсё ок"
    def fake_run(cmd, cwd, check, capture_output, text, timeout=None):
        calls["cmd"] = cmd; calls["cwd"] = cwd
        return R()
    monkeypatch.setattr("review_bot.reviewers.ocr.subprocess.run", fake_run)
    out = OcrAdapter().run(Path("/tmp/x"), "main", "feature")
    assert out.strip().startswith("## Ревью")
    assert calls["cmd"][:2] == ["ocr", "review"]
    assert "--from" in calls["cmd"] and "origin/main" in calls["cmd"]
    assert "feature" in calls["cmd"]
    assert calls["cwd"] == "/tmp/x"

def test_empty_output_has_placeholder(monkeypatch):
    class R: stdout = "   "
    monkeypatch.setattr("review_bot.reviewers.ocr.subprocess.run",
                        lambda *a, **k: R())
    out = OcrAdapter().run(Path("/tmp/x"), "main", "feature")
    assert out  # непустой плейсхолдер
```

- [ ] **Step 2: Run — verify fail**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_ocr.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

`bot/review_bot/reviewers/ocr.py`:
```python
import subprocess
from pathlib import Path

class OcrAdapter:
    key = "ocr"

    def __init__(self, timeout: int = 900) -> None:
        self._timeout = timeout

    def run(self, checkout_dir: Path, base_ref: str, head_ref: str) -> str:
        r = subprocess.run(
            ["ocr", "review", "--from", f"origin/{base_ref}", "--to", head_ref,
             "--audience", "agent"],
            cwd=str(checkout_dir), check=True, capture_output=True, text=True,
            timeout=self._timeout,
        )
        return r.stdout.strip() or "_ocr: пустой вывод ревью_"
```

- [ ] **Step 4: Run — verify pass**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_ocr.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/review_bot/reviewers/ocr.py bot/tests/test_ocr.py
git commit -m "feat(bot): ocr reviewer-адаптер" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" -- bot/review_bot/reviewers/ocr.py bot/tests/test_ocr.py
```

---

## Task 5: GitHub-адаптер — verify + parse_event

**Files:**
- Create: `bot/review_bot/platforms/github.py`, `bot/tests/test_github_verify.py`

**Interfaces:**
- Consumes: `IncomingComment`, `PRContext` (Task 1).
- Produces: `GitHubAdapter(token, webhook_secret, api_base, bot_login, client=None)` с методами
  `verify(headers, body)`, `parse_event(payload)`; остальные методы — в Task 6.

- [ ] **Step 1: Failing test**

`bot/tests/test_github_verify.py`:
```python
import hashlib
import hmac
import json
from review_bot.platforms.github import GitHubAdapter

SECRET = "s3cret"

def _sig(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()

def _adapter():
    return GitHubAdapter(token="t", webhook_secret=SECRET, api_base="https://api.github.com")

def test_verify_ok_and_bad():
    a = _adapter()
    body = b'{"x":1}'
    assert a.verify({"x-hub-signature-256": _sig(body)}, body) is True
    assert a.verify({"x-hub-signature-256": "sha256=deadbeef"}, body) is False

def test_parse_pr_comment():
    payload = {
        "action": "created",
        "issue": {"number": 7, "pull_request": {"url": "..."},
                  "user": {"login": "author"}},
        "comment": {"id": 42, "body": "@review.ocr", "user": {"login": "alice", "type": "User"}},
        "repository": {"full_name": "o/r", "clone_url": "https://github.com/o/r.git"},
    }
    c = _adapter().parse_event(payload)
    assert c.event_id == "42" and c.author == "alice" and c.is_bot is False
    assert c.body == "@review.ocr"

def test_parse_ignores_non_pr_and_non_created():
    a = _adapter()
    assert a.parse_event({"action": "created", "issue": {"number": 1}, "comment": {}}) is None
    assert a.parse_event({"action": "edited", "issue": {"pull_request": {}}}) is None

def test_parse_flags_bot_author():
    payload = {"action": "created",
               "issue": {"number": 1, "pull_request": {}, "user": {"login": "a"}},
               "comment": {"id": 1, "body": "hi", "user": {"login": "bot", "type": "Bot"}}}
    assert a_parse(payload).is_bot is True

def a_parse(payload):
    return _adapter().parse_event(payload)
```

- [ ] **Step 2: Run — verify fail**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_github_verify.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement (verify + parse; заглушки прочих методов — заполнятся в Task 6)**

`bot/review_bot/platforms/github.py`:
```python
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
```

- [ ] **Step 4: Run — verify pass**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_github_verify.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/review_bot/platforms/github.py bot/tests/test_github_verify.py
git commit -m "feat(bot): GitHub-адаптер — verify подписи + parse события" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" -- bot/review_bot/platforms/github.py bot/tests/test_github_verify.py
```

---

## Task 6: GitHub-адаптер — API (context, authz, post)

**Files:**
- Modify: `bot/review_bot/platforms/github.py`
- Create: `bot/tests/test_github_api.py`

**Interfaces:**
- Produces: `GitHubAdapter.get_pr_context(payload)->PRContext`,
  `check_authz(ctx, author)->bool`, `post_comment(ctx, markdown)->None`.
- Consumes: `httpx.MockTransport` в тестах.

- [ ] **Step 1: Failing test (httpx.MockTransport)**

`bot/tests/test_github_api.py`:
```python
import httpx
from review_bot.platforms.github import GitHubAdapter
from review_bot.models import PRContext

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
    ctx = PRContext("github","o/r","o/r",7,"main","feature","abc","url","author")
    assert a.check_authz(ctx, "alice") is True

def test_check_authz_false_for_read_or_404():
    a_read = GitHubAdapter("t","s",client=_client(lambda r: httpx.Response(200, json={"permission":"read"})))
    a_404 = GitHubAdapter("t","s",client=_client(lambda r: httpx.Response(404, json={})))
    ctx = PRContext("github","o/r","o/r",7,"main","feature","abc","url","author")
    assert a_read.check_authz(ctx, "bob") is False
    assert a_404.check_authz(ctx, "bob") is False

def test_post_comment():
    seen = {}
    def handler(req):
        seen["path"] = req.url.path
        import json as _j; seen["body"] = _j.loads(req.content)["body"]
        return httpx.Response(201, json={"id": 1})
    a = GitHubAdapter("t", "s", client=_client(handler))
    ctx = PRContext("github","o/r","o/r",7,"main","feature","abc","url","author")
    a.post_comment(ctx, "## Ревью")
    assert seen["path"] == "/repos/o/r/issues/7/comments"
    assert seen["body"] == "## Ревью"
```

- [ ] **Step 2: Run — verify fail**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_github_api.py -v`
Expected: FAIL (`AttributeError: get_pr_context`).

- [ ] **Step 3: Implement (дописать методы в GitHubAdapter)**

Добавить в класс `GitHubAdapter`:
```python
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

    def post_comment(self, ctx: PRContext, markdown: str) -> None:
        r = self._client.post(
            f"{self._api}/repos/{ctx.repo}/issues/{ctx.pr_number}/comments",
            headers=self._auth(), json={"body": markdown})
        r.raise_for_status()
```

- [ ] **Step 4: Run — verify pass (весь github)**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_github_verify.py bot/tests/test_github_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/review_bot/platforms/github.py bot/tests/test_github_api.py
git commit -m "feat(bot): GitHub-адаптер — PR-контекст, авторизация, постинг коммента" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" -- bot/review_bot/platforms/github.py bot/tests/test_github_api.py
```

---

## Task 7: Конвейер (оркестрация)

**Files:**
- Create: `bot/review_bot/pipeline.py`, `bot/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `PlatformAdapter`, `Registry`, `SeenEvents`, `resolve_engine`, `checkout_pr`/`cleanup`, `Settings`.
- Produces: `handle_comment(*, platform, payload, headers, raw_body, settings, reviewers, seen) -> str`
  (коды: `invalid-signature`, `ignored`, `ignored-bot`, `duplicate`, `no-mention`, `unauthorized`, `reviewed`).

- [ ] **Step 1: Failing test (на фейках, checkout замокан)**

`bot/tests/test_pipeline.py`:
```python
from pathlib import Path
from review_bot.pipeline import handle_comment
from review_bot.registry import Registry
from review_bot.dedup import SeenEvents
from review_bot.config import Settings
from review_bot.models import IncomingComment, PRContext

CTX = PRContext("github","o/r","o/r",7,"main","feature","abc","url","author")

class FakePlatform:
    name = "github"
    def __init__(self, comment, authz=True):
        self._c = comment; self._authz = authz; self.posted = []
    def verify(self, headers, body): return True
    def parse_event(self, payload): return self._c
    def get_pr_context(self, payload): return CTX
    def check_authz(self, ctx, author): return self._authz
    def checkout_token(self): return None
    def post_comment(self, ctx, md): self.posted.append(md)

class FakeReviewer:
    key = "ocr"
    def run(self, d, base, head): return "## Ревью от ocr"

def _reg():
    r = Registry(); r.register("ocr", FakeReviewer()); return r

def _patch_checkout(monkeypatch):
    monkeypatch.setattr("review_bot.pipeline.checkout_pr", lambda *a, **k: Path("/tmp/x"))
    monkeypatch.setattr("review_bot.pipeline.cleanup", lambda d: None)

def _call(platform, monkeypatch, allowlist=None):
    _patch_checkout(monkeypatch)
    s = Settings(); s.allowlist = allowlist or []
    return handle_comment(platform=platform, payload={}, headers={}, raw_body=b"{}",
                          settings=s, reviewers=_reg(), seen=SeenEvents())

def test_happy_path_posts_review(monkeypatch):
    p = FakePlatform(IncomingComment("1","alice","@review.ocr",False))
    assert _call(p, monkeypatch) == "reviewed"
    assert p.posted == ["## Ревью от ocr"]

def test_no_mention(monkeypatch):
    p = FakePlatform(IncomingComment("1","alice","обычный текст",False))
    assert _call(p, monkeypatch) == "no-mention"
    assert p.posted == []

def test_bot_author_ignored(monkeypatch):
    p = FakePlatform(IncomingComment("1","bot","@review",True))
    assert _call(p, monkeypatch) == "ignored-bot"

def test_duplicate(monkeypatch):
    _patch_checkout(monkeypatch)
    p = FakePlatform(IncomingComment("dup","alice","@review",False))
    seen = SeenEvents(); s = Settings()
    a = handle_comment(platform=p, payload={}, headers={}, raw_body=b"{}", settings=s, reviewers=_reg(), seen=seen)
    b = handle_comment(platform=p, payload={}, headers={}, raw_body=b"{}", settings=s, reviewers=_reg(), seen=seen)
    assert a == "reviewed" and b == "duplicate"

def test_unauthorized_posts_notice(monkeypatch):
    p = FakePlatform(IncomingComment("1","stranger","@review",False), authz=False)
    assert _call(p, monkeypatch) == "unauthorized"
    assert p.posted and "прав" in p.posted[0]

def test_allowlist_restricts(monkeypatch):
    p = FakePlatform(IncomingComment("1","alice","@review",False), authz=True)
    assert _call(p, monkeypatch, allowlist=["bob"]) == "unauthorized"
```

- [ ] **Step 2: Run — verify fail**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_pipeline.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

`bot/review_bot/pipeline.py`:
```python
from review_bot.checkout import checkout_pr, cleanup
from review_bot.router import resolve_engine

_UNAUTHORIZED = "🔒 Ревью не запущено: у вас нет прав на этот репозиторий (или вы не в allowlist)."

def handle_comment(*, platform, payload, headers, raw_body, settings, reviewers, seen) -> str:
    if not platform.verify(headers, raw_body):
        return "invalid-signature"
    comment = platform.parse_event(payload)
    if comment is None:
        return "ignored"
    if comment.is_bot:
        return "ignored-bot"
    if seen.seen(comment.event_id):
        return "duplicate"
    engine = resolve_engine(comment.body, default=settings.default_engine, known=reviewers.keys())
    if engine is None:
        return "no-mention"

    ctx = platform.get_pr_context(payload)
    authorized = platform.check_authz(ctx, comment.author)
    if settings.allowlist:
        authorized = authorized and comment.author in settings.allowlist
    if not authorized:
        platform.post_comment(ctx, _UNAUTHORIZED)
        return "unauthorized"

    adapter = reviewers.get(engine)
    workdir = checkout_pr(ctx.clone_url, ctx.base_ref, ctx.head_ref, platform.checkout_token())
    try:
        markdown = adapter.run(workdir, ctx.base_ref, ctx.head_ref)
    finally:
        cleanup(workdir)
    platform.post_comment(ctx, markdown)
    return "reviewed"
```

- [ ] **Step 4: Run — verify pass**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_pipeline.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add bot/review_bot/pipeline.py bot/tests/test_pipeline.py
git commit -m "feat(bot): конвейер оркестрации (verify→parse→authz→checkout→review→post)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" -- bot/review_bot/pipeline.py bot/tests/test_pipeline.py
```

---

## Task 8: FastAPI-приложение + GitHub-роут + healthz (walking skeleton)

**Files:**
- Create: `bot/review_bot/main.py`, `bot/tests/test_app.py`

**Interfaces:**
- Consumes: `Settings`, `GitHubAdapter`, `OcrAdapter`, `Registry`, `SeenEvents`, `handle_comment`.
- Produces: `create_app(settings=None) -> FastAPI` с `GET /healthz`, `POST /webhook/github`;
  фабрики `build_reviewers(settings)`, `build_platforms(settings)`.

- [ ] **Step 1: Failing test (TestClient + валидная подпись)**

`bot/tests/test_app.py`:
```python
import hashlib
import hmac
import json
from fastapi.testclient import TestClient
from review_bot.main import create_app
from review_bot.config import Settings

SECRET = "hooksecret"

def _client():
    s = Settings()
    s.github_webhook_secret = SECRET
    s.github_token = "t"
    return TestClient(create_app(s))

def test_healthz():
    assert _client().get("/healthz").json() == {"status": "ok"}

def test_github_webhook_rejects_bad_signature():
    r = _client().post("/webhook/github", content=b"{}",
                       headers={"x-hub-signature-256": "sha256=bad",
                                "x-github-event": "issue_comment"})
    assert r.json()["result"] == "invalid-signature"

def test_github_webhook_ignores_non_mention(monkeypatch):
    # реальный API не дёргаем: коммент без @review отсеивается до вызовов сети
    payload = {"action": "created",
               "issue": {"number": 1, "pull_request": {}, "user": {"login": "a"}},
               "comment": {"id": 5, "body": "просто коммент", "user": {"login": "alice", "type": "User"}},
               "repository": {"full_name": "o/r", "clone_url": "https://github.com/o/r.git"}}
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    r = _client().post("/webhook/github", content=body,
                       headers={"x-hub-signature-256": sig, "x-github-event": "issue_comment"})
    assert r.json()["result"] == "no-mention"
```

- [ ] **Step 2: Run — verify fail**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_app.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

`bot/review_bot/main.py`:
```python
import json
from fastapi import FastAPI, Request

from review_bot.config import Settings
from review_bot.registry import Registry
from review_bot.dedup import SeenEvents
from review_bot.pipeline import handle_comment
from review_bot.reviewers.ocr import OcrAdapter
from review_bot.platforms.github import GitHubAdapter

def build_reviewers(settings: Settings) -> Registry:
    reg = Registry()
    if "ocr" in settings.enabled_engines:
        reg.register("ocr", OcrAdapter(timeout=settings.review_timeout))
    # pr.agent регистрируется в Task 9
    return reg

def build_platforms(settings: Settings) -> dict:
    return {
        "github": GitHubAdapter(
            token=settings.github_token,
            webhook_secret=settings.github_webhook_secret,
            api_base=settings.github_api_base,
            bot_login=settings.github_bot_login,
        ),
        # gitlab добавляется в Task 10
    }

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="review-bot")
    reviewers = build_reviewers(settings)
    platforms = build_platforms(settings)
    seen = SeenEvents()

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.post("/webhook/github")
    async def github_webhook(request: Request):
        body = await request.body()
        headers = {k.lower(): v for k, v in request.headers.items()}
        payload = json.loads(body or b"{}")
        result = handle_comment(
            platform=platforms["github"], payload=payload, headers=headers,
            raw_body=body, settings=settings, reviewers=reviewers, seen=seen)
        return {"result": result}

    return app

app = create_app()
```

- [ ] **Step 4: Run — verify pass**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_app.py -v`
Expected: PASS.

- [ ] **Step 5: Smoke-запуск сервера (ручная проверка)**

```bash
GITHUB_WEBHOOK_SECRET=x bot/.venv/bin/python -c "from review_bot.main import create_app; from fastapi.testclient import TestClient; print(TestClient(create_app()).get('/healthz').json())"
```
Expected: `{'status': 'ok'}`.

- [ ] **Step 6: Commit**

```bash
git add bot/review_bot/main.py bot/tests/test_app.py
git commit -m "feat(bot): FastAPI-приложение, GitHub-вебхук, healthz (GitHub+ocr сквозной путь)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" -- bot/review_bot/main.py bot/tests/test_app.py
```

> **Веха:** после Task 8 работает сквозной путь GitHub + ocr (дефолт). Дальше — расширение.

---

## Task 9: pr-agent reviewer-адаптер

**Files:**
- Create: `bot/review_bot/reviewers/pr_agent.py`, `bot/tests/test_pr_agent.py`
- Modify: `bot/review_bot/main.py:build_reviewers` (зарегистрировать `pr.agent`)

**Interfaces:**
- Produces: `PrAgentAdapter` (`key="pr.agent"`, `run(...)->str`, читает `review.md` из чекаута).

- [ ] **Step 1: Failing test (subprocess замокан, review.md создаётся)**

`bot/tests/test_pr_agent.py`:
```python
from review_bot.reviewers.pr_agent import PrAgentAdapter

def test_run_returns_review_md(monkeypatch, tmp_path):
    (tmp_path / "review.md").write_text("## PR-Agent\nнашёл баг", encoding="utf-8")
    calls = {}
    def fake_run(cmd, cwd, check, capture_output, text, timeout=None, env=None):
        calls["cmd"] = cmd
        class R: stdout = ""
        return R()
    monkeypatch.setattr("review_bot.reviewers.pr_agent.subprocess.run", fake_run)
    out = PrAgentAdapter().run(tmp_path, "master", "feature")
    assert "PR-Agent" in out
    assert calls["cmd"][0] == "pr-agent" and "review" in calls["cmd"]

def test_run_placeholder_when_no_file(monkeypatch, tmp_path):
    monkeypatch.setattr("review_bot.reviewers.pr_agent.subprocess.run",
                        lambda *a, **k: type("R", (), {"stdout": ""})())
    out = PrAgentAdapter().run(tmp_path, "master", "feature")
    assert out  # непустой плейсхолдер
```

- [ ] **Step 2: Run — verify fail**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_pr_agent.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

`bot/review_bot/reviewers/pr_agent.py`:
```python
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
```

Изменить `bot/review_bot/main.py` — в `build_reviewers` добавить перед `return reg`:
```python
    if "pr.agent" in settings.enabled_engines:
        from review_bot.reviewers.pr_agent import PrAgentAdapter
        reg.register("pr.agent", PrAgentAdapter(timeout=settings.review_timeout))
```

- [ ] **Step 4: Run — verify pass**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_pr_agent.py bot/tests/test_app.py -v`
Expected: PASS (адаптер + приложение).

- [ ] **Step 5: Commit**

```bash
git add bot/review_bot/reviewers/pr_agent.py bot/tests/test_pr_agent.py bot/review_bot/main.py
git commit -m "feat(bot): pr-agent reviewer-адаптер + регистрация в реестре" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" -- bot/review_bot/reviewers/pr_agent.py bot/tests/test_pr_agent.py bot/review_bot/main.py
```

---

## Task 10: GitLab-адаптер + роут

**Files:**
- Create: `bot/review_bot/platforms/gitlab.py`, `bot/tests/test_gitlab.py`
- Modify: `bot/review_bot/main.py` (`build_platforms` + `POST /webhook/gitlab`)

**Interfaces:**
- Produces: `GitLabAdapter(token, webhook_secret, api_base, bot_username, client=None)` — тот же
  `PlatformAdapter`-интерфейс, что у GitHub. Note-hook на MR; verify по `X-Gitlab-Token`.

- [ ] **Step 1: Failing test**

`bot/tests/test_gitlab.py`:
```python
import httpx
from review_bot.platforms.gitlab import GitLabAdapter
from review_bot.models import PRContext

def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://gitlab.com/api/v4")

NOTE = {
    "object_kind": "note",
    "user": {"username": "alice"},
    "object_attributes": {"id": 99, "note": "@review.ocr", "noteable_type": "MergeRequest"},
    "merge_request": {"iid": 3, "source_branch": "feature", "target_branch": "main",
                      "last_commit": {"id": "sha9"}},
    "project": {"id": 12, "git_http_url": "https://gitlab.com/o/r.git",
                "path_with_namespace": "o/r"},
}

def _a(client=None):
    return GitLabAdapter(token="t", webhook_secret="s", api_base="https://gitlab.com/api/v4",
                         bot_username="bot", client=client)

def test_verify_token():
    a = _a()
    assert a.verify({"x-gitlab-token": "s"}, b"{}") is True
    assert a.verify({"x-gitlab-token": "nope"}, b"{}") is False

def test_parse_note_on_mr():
    c = _a().parse_event(NOTE)
    assert c.event_id == "99" and c.author == "alice" and c.body == "@review.ocr"
    assert c.is_bot is False

def test_parse_ignores_non_mr_note():
    n = {"object_kind": "note", "object_attributes": {"noteable_type": "Issue"}}
    assert _a().parse_event(n) is None

def test_parse_flags_bot_author():
    n = {**NOTE, "user": {"username": "bot"}}
    assert _a().parse_event(n).is_bot is True

def test_get_pr_context():
    ctx = _a().get_pr_context(NOTE)
    assert ctx.platform == "gitlab" and ctx.project_id == "12" and ctx.pr_number == 3
    assert ctx.base_ref == "main" and ctx.head_ref == "feature"
    assert ctx.clone_url.endswith("o/r.git")

def test_check_authz_by_access_level():
    ok = _a(_client(lambda r: httpx.Response(200, json={"access_level": 30})))   # >=30 developer
    low = _a(_client(lambda r: httpx.Response(200, json={"access_level": 10})))
    ctx = PRContext("gitlab","o/r","12",3,"main","feature","sha","url","alice")
    assert ok.check_authz(ctx, "alice") is True
    assert low.check_authz(ctx, "alice") is False

def test_post_comment():
    seen = {}
    def handler(req):
        seen["path"] = req.url.path
        import json as _j; seen["body"] = _j.loads(req.content)["body"]
        return httpx.Response(201, json={"id": 1})
    ctx = PRContext("gitlab","o/r","12",3,"main","feature","sha","url","alice")
    _a(_client(handler)).post_comment(ctx, "## Ревью")
    assert seen["path"] == "/api/v4/projects/12/merge_requests/3/notes"
    assert seen["body"] == "## Ревью"
```

- [ ] **Step 2: Run — verify fail**

Run: `bot/.venv/bin/python -m pytest bot/tests/test_gitlab.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

`bot/review_bot/platforms/gitlab.py`:
```python
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
        # user id по username → members/all/{id} access_level (>=30 developer)
        ur = self._client.get(f"{self._api}/users", params={"username": author},
                              headers=self._auth())
        if ur.status_code != 200 or not ur.json():
            # если lookup недоступен — пробуем прямой members-запрос по username недоступен;
            # безопасный дефолт: отказ
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
```

> Примечание к тесту `test_check_authz_by_access_level`: он использует единый handler,
> отвечающий и на `/users`, и на `/members/all/{id}`. Обнови фикстуру, если разнесёшь:
> handler должен вернуть `[{"id": 1}]` на `/users` и `{"access_level": N}` на members.
> (Проще: в тесте `_client` отвечает на любой путь нужным телом — для `access_level`
> достаточно вернуть `{"id":1,"access_level":N}` и список `[{"id":1,...}]` — см. ниже.)

Скорректируй `test_check_authz_by_access_level` под два запроса:
```python
def test_check_authz_by_access_level():
    def make(level):
        def handler(req):
            if req.url.path.endswith("/users"):
                return httpx.Response(200, json=[{"id": 1}])
            return httpx.Response(200, json={"access_level": level})
        return _a(_client(handler))
    ctx = PRContext("gitlab","o/r","12",3,"main","feature","sha","url","alice")
    assert make(30).check_authz(ctx, "alice") is True
    assert make(10).check_authz(ctx, "alice") is False
```

Изменить `bot/review_bot/main.py`:
```python
# импорт вверху:
from review_bot.platforms.gitlab import GitLabAdapter
# в build_platforms добавить ключ:
        "gitlab": GitLabAdapter(
            token=settings.gitlab_token,
            webhook_secret=settings.gitlab_webhook_secret,
            api_base=settings.gitlab_api_base,
            bot_username=settings.gitlab_bot_username,
        ),
# новый роут рядом с github_webhook:
    @app.post("/webhook/gitlab")
    async def gitlab_webhook(request: Request):
        body = await request.body()
        headers = {k.lower(): v for k, v in request.headers.items()}
        payload = json.loads(body or b"{}")
        result = handle_comment(
            platform=platforms["gitlab"], payload=payload, headers=headers,
            raw_body=body, settings=settings, reviewers=reviewers, seen=seen)
        return {"result": result}
```

- [ ] **Step 4: Run — verify pass (вся сюита)**

Run: `bot/.venv/bin/python -m pytest bot/tests -v`
Expected: PASS (все тесты).

- [ ] **Step 5: Commit**

```bash
git add bot/review_bot/platforms/gitlab.py bot/tests/test_gitlab.py bot/review_bot/main.py
git commit -m "feat(bot): GitLab-адаптер (note-hook, authz, постинг) + роут" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" -- bot/review_bot/platforms/gitlab.py bot/tests/test_gitlab.py bot/review_bot/main.py
```

---

## Task 11: Docker, конфиг-шаблон, README (капстоун)

**Files:**
- Create: `bot/Dockerfile`, `bot/.env.example`, `bot/README.md`

**Interfaces:**
- Consumes: весь пакет `review_bot`.

- [ ] **Step 1: `bot/.env.example`**

```bash
# Общее
DEFAULT_ENGINE=ocr
ENABLED_ENGINES=ocr,pr.agent
ALLOWLIST=            # пусто = любой с правами на репозиторий; иначе список логинов через запятую
REVIEW_TIMEOUT=900

# GitHub (App/PAT + секрет вебхука)
GITHUB_TOKEN=
GITHUB_WEBHOOK_SECRET=
GITHUB_BOT_LOGIN=
GITHUB_API_BASE=https://api.github.com

# GitLab (token + секрет вебхука)
GITLAB_TOKEN=
GITLAB_WEBHOOK_SECRET=
GITLAB_BOT_USERNAME=
GITLAB_API_BASE=https://gitlab.com/api/v4

# Ключи LLM-провайдера (см. ../docs/providers.md) — нужны движкам ocr/pr-agent
DEEPSEEK_KEY=
```

- [ ] **Step 2: `bot/Dockerfile`** (python + node + git + оба движка)

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Движки-ревьюеры (те же, что в SP1)
RUN npm install -g @alibaba-group/open-code-review \
    && pip install --no-cache-dir "pr-agent==0.36.1"

WORKDIR /app
COPY pyproject.toml ./
COPY review_bot ./review_bot
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "review_bot.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: `bot/README.md`** — деплой и эксплуатация

Обязательные секции:
1. **Что это** — центральный бот: тегаешь `@review[.движок]` в PR/MR → ревью ответным комментом. Дефолт `@review` → ocr. Ссылка на [спеку SP2](../docs/superpowers/specs/2026-07-02-comment-triggered-review-bot-design.md) и [провайдеров](../docs/providers.md).
2. **Конфигурация** — таблица env из `.env.example` (движки, allowlist, токены/секреты платформ, ключ LLM).
3. **Запуск локально:** `pip install -e ".[dev]"`, `uvicorn review_bot.main:app --reload`; `GET /healthz`.
4. **Docker:** `docker build -t review-bot bot/ && docker run --env-file bot/.env -p 8000:8000 review-bot`.
5. **Регистрация вебхуков:**
   - GitHub: создать App/использовать PAT с правами `contents:read`, `pull_requests:write`; webhook на события *Issue comments* → `https://<host>/webhook/github`, secret = `GITHUB_WEBHOOK_SECRET`.
   - GitLab: Project/Group webhook на *Comments* → `https://<host>/webhook/gitlab`, Secret token = `GITLAB_WEBHOOK_SECRET`; токен бота scope `api`.
6. **Как звать:** `@review` (дефолт ocr), `@review.ocr`, `@review.pr.agent`.
7. **Безопасность:** verify подписи; allowlist; анти-loop (игнор своих комментов); дедуп; таймаут.
8. **Расширяемость:** новый ревьюер = адаптер `run(checkout,base,head)->markdown` + `reg.register(...)` в `build_reviewers`; новая платформа = адаптер интерфейса `PlatformAdapter` + роут. Ссылка на [docs/add-a-reviewer.md](../docs/add-a-reviewer.md).
9. **Ограничения v1:** Bitbucket не поддержан (задел); ревью — весь PR (без под-команд/флагов).

- [ ] **Step 4: Verify**

```bash
# Dockerfile синтаксис (если есть hadolint — иначе просто наличие ключевых строк)
grep -q "uvicorn" bot/Dockerfile && grep -q "pr-agent" bot/Dockerfile && echo "Dockerfile OK"
# финальная сюита
bot/.venv/bin/python -m pytest bot/tests -q
# ссылки README (относительные)
python3 - <<'PY'
import re, pathlib, sys
md = pathlib.Path("bot/README.md"); bad=[]
for m in re.finditer(r'\]\(([^)]+)\)', md.read_text(encoding="utf-8")):
    l=m.group(1).split('#')[0].strip()
    if l and not l.startswith(("http","mailto:")) and not (md.parent/l).resolve().exists(): bad.append(l)
print("BROKEN:",bad) if bad else print("README links OK"); sys.exit(1 if bad else 0)
PY
```
Expected: `Dockerfile OK`, все тесты passed, `README links OK`.

- [ ] **Step 5: Commit**

```bash
git add bot/Dockerfile bot/.env.example bot/README.md
git commit -m "feat(bot): Dockerfile, .env.example, README (деплой и эксплуатация)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" -- bot/Dockerfile bot/.env.example bot/README.md
```

- [ ] **Step 6: Связать с корневым README (навигация тулкита)**

В корневом `README.md` в разделе «Режимы запуска» пункт «По комментарию» пометить готовым и дать ссылку на `bot/README.md`. Заменить строку `*(в разработке)*` на ссылку `[bot/](bot/README.md)`. Затем прогнать линк-чек гайда (как в SP1) и закоммитить:
```bash
git add README.md
git commit -m "docs: подключить модуль bot/ в навигацию корневого README" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" -- README.md
```

---

## Self-Review (выполнено при написании плана)

**Покрытие спека SP2:**
- §5 конвейер (verify→parse→дедуп/loop→маршрут→authz→checkout→run→post) → Task 7 (+ роуты Tasks 8,10). ✓
- §6 приём вебхуков (GitHub sig, GitLab token, дедуп, анти-loop) → Tasks 5,7,10. ✓
- §7 роутер `@review[.движок]`, дефолт ocr → Task 2. ✓
- §8 авторизация (платформа + allowlist) → Tasks 6,7,10. ✓
- §9 reviewer-адаптеры (ocr, pr-agent), единый постинг → Tasks 4,9,7. ✓
- §10 платформенные адаптеры (github, gitlab) → Tasks 5,6,10. ✓
- §11 стек/деплой (FastAPI, Docker python+node+git) → Tasks 8,11. ✓
- §12 безопасность (verify, allowlist, anti-loop, timeout) → Tasks 5,7 + config. ✓
- §13 расширяемость (реестры, интерфейсы) → Tasks 2,4,9,10 + README §8. ✓
- §15 этапы → порядок Tasks 1–11 (walking skeleton на Task 8). ✓
- §16 связь с корневым README → Task 11 Step 6. ✓

**Placeholder-скан:** реального кода/тестов достаточно в каждом шаге. Открытые техвопросы спека §14 (точные права токенов, формат payload, лимиты длины) закрыты конкретными реализациями с тестами; точные значения (scope токенов, `access_level>=30`) стоит сверить с доками платформ при регистрации — помечено в README Task 11.

**Согласованность типов/имён:** `ReviewerAdapter.run(checkout_dir,base_ref,head_ref)->str`, `PlatformAdapter` (`verify/parse_event/get_pr_context/check_authz/checkout_token/post_comment`), `handle_comment(...)` коды, ключи реестра `ocr`/`pr.agent`, `PRContext`/`IncomingComment` поля — консистентны между Tasks 1–11.

**Замечание по исполнению:** venv/pip и тесты требуют сети для установки зависимостей; движки `ocr`/`pr-agent` в юнит-тестах замоканы (реальный прогон — в Docker при деплое).
