from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ReviewerAdapter(Protocol):
    key: str

    def run(self, checkout_dir: Path, base_ref: str, head_ref: str) -> str: ...
