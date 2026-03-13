"""Console entry point for the code-normalizer-pro installed package."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def _find_script() -> Path:
    """Return the path to code_normalizer_pro.py."""
    pkg_dir = Path(__file__).resolve().parent
    candidate = pkg_dir / "code_normalizer_pro.py"
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"code_normalizer_pro.py not found at: {candidate}")


def main() -> None:
    script = _find_script()
    sys.argv[0] = str(script)
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
