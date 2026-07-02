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
