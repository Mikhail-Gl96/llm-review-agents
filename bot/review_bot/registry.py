class Registry:
    def __init__(self) -> None:
        self._items: dict[str, object] = {}

    def register(self, key: str, item: object) -> None:
        self._items[key] = item

    def get(self, key: str):
        return self._items.get(key)

    def keys(self) -> set[str]:
        return set(self._items)
