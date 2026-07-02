from review_bot.registry import Registry


def test_register_and_get():
    r = Registry()
    r.register("ocr", object())
    assert r.get("ocr") is not None
    assert r.get("missing") is None
    assert r.keys() == {"ocr"}
