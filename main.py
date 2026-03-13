"""Project entry point for CLI execution."""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    script = Path(__file__).resolve().parent / "code_normalizer_pro" / "code_normalizer_pro.py"
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
