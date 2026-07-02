import subprocess
from pathlib import Path


class OcrAdapter:
    key = "ocr"

    def __init__(self, timeout: int = 900) -> None:
        self._timeout = timeout

    def run(self, checkout_dir: Path, base_ref: str, head_ref: str) -> str:
        r = subprocess.run(
            ["ocr", "review", "--from", f"origin/{base_ref}", "--to", head_ref,
             "--audience", "agent"],
            cwd=str(checkout_dir), check=True, capture_output=True, text=True,
            timeout=self._timeout,
        )
        return r.stdout.strip() or "_ocr: пустой вывод ревью_"
