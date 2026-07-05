import logging

from review_bot.checkout import checkout_pr, cleanup
from review_bot.router import resolve_engine

logger = logging.getLogger("review_bot.pipeline")

_UNAUTHORIZED = "🔒 Ревью не запущено: у вас нет прав на этот репозиторий (или вы не в allowlist)."


def handle_comment(*, platform, payload, headers, raw_body, settings, reviewers, seen) -> str:
    if not platform.verify(headers, raw_body):
        logger.info("[%s] invalid-signature", platform.name)
        return "invalid-signature"
    comment = platform.parse_event(payload)
    if comment is None:
        logger.info("[%s] ignored (не подходящее событие / не MR-коммент)", platform.name)
        return "ignored"
    logger.info("[%s] comment id=%s author=%s body=%r",
                platform.name, comment.event_id, comment.author, (comment.body or "")[:120])
    if comment.is_bot:
        logger.info("[%s] ignored-bot (author=%s)", platform.name, comment.author)
        return "ignored-bot"
    if seen.seen(comment.event_id):
        logger.info("[%s] duplicate id=%s", platform.name, comment.event_id)
        return "duplicate"
    engine = resolve_engine(comment.body, default=settings.default_engine, known=reviewers.keys())
    if engine is None:
        logger.info("[%s] no-mention (в тексте нет @review)", platform.name)
        return "no-mention"
    logger.info("[%s] routing -> engine=%s", platform.name, engine)

    try:
        ctx = platform.get_pr_context(payload)
        authorized = platform.check_authz(ctx, comment.author)
        if settings.allowlist:
            authorized = authorized and comment.author in settings.allowlist
        if not authorized:
            logger.info("[%s] unauthorized author=%s", platform.name, comment.author)
            platform.post_comment(ctx, _UNAUTHORIZED)
            return "unauthorized"

        adapter = reviewers.get(engine)
        logger.info("[%s] checkout url=%s base=%s head=%s",
                    platform.name, ctx.clone_url, ctx.base_ref, ctx.head_ref)
        workdir = checkout_pr(ctx.clone_url, ctx.base_ref, ctx.head_ref, platform.checkout_token())
        try:
            markdown = adapter.run(workdir, ctx.base_ref, ctx.head_ref)
        finally:
            cleanup(workdir)
        logger.info("[%s] posting review (%d chars) to %s !%s",
                    platform.name, len(markdown), ctx.repo, ctx.pr_number)
        platform.post_comment(ctx, markdown)
        logger.info("[%s] reviewed OK", platform.name)
        return "reviewed"
    except Exception:
        logger.exception("[%s] review FAILED", platform.name)
        return "error"
