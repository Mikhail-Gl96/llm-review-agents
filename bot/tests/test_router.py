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
