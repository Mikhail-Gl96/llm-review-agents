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
