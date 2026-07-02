from review_bot.models import IncomingComment, PRContext


def test_models_construct():
    c = IncomingComment(event_id="1", author="alice", body="@review", is_bot=False)
    assert c.author == "alice" and c.is_bot is False
    ctx = PRContext(platform="github", repo="o/r", project_id="o/r", pr_number=7,
                    base_ref="main", head_ref="feat", head_sha="abc",
                    clone_url="https://x/o/r.git", author="alice")
    assert ctx.pr_number == 7 and ctx.base_ref == "main"
