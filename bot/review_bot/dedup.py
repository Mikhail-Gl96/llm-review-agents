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
