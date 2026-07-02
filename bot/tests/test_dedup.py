from review_bot.dedup import SeenEvents


def test_first_unseen_then_seen():
    s = SeenEvents()
    assert s.seen("e1") is False
    assert s.seen("e1") is True


def test_capacity_evicts_oldest():
    s = SeenEvents(capacity=2)
    s.seen("a")
    s.seen("b")
    s.seen("c")  # 'a' вытеснен
    assert s.seen("a") is False
