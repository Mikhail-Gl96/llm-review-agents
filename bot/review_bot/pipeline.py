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
