# Changelog

All notable changes to this project are documented here.

## [3.0.1] - 2026-03-13

### Added
- Clean repository setup with proper package structure
- code_normalizer_pro/ package (cli.py, code_normalizer_pro.py, __init__.py)
- main.py root entry point via runpy
- pyproject.toml with console_scripts entry point
- CI workflow (.github/workflows/ci.yml)
- VERIFY.md with install and test commands

## [3.0.0] - 2026-02-09

### Added
- Parallel processing via ProcessPoolExecutor (3-10x speedup on multi-core)
- SHA256 incremental caching (.normalize-cache.json)
- Pre-commit git hook generation (--install-hook)
- Multi-language syntax checking: Python, JS, TS, Go, Rust, C, C++, Java
- Interactive per-file approval mode with diff preview (--interactive)

## [2.0.0] - 2026-02-09

### Added
- Dry-run mode (--dry-run)
- In-place editing with timestamped backups (--in-place)
- tqdm progress bars
- Detailed processing statistics
- Windows UTF-8 stdout fix

### Fixed
- argparse flag parsing bug

## [1.0.0] - 2026-02-09

### Added
- UTF-8 encoding normalization (utf-8, utf-8-sig, utf-16, utf-16-le, utf-16-be, windows-1252, latin-1, iso-8859-1)
- CRLF to LF line ending conversion
- Trailing whitespace removal
- Final newline enforcement
- Binary file detection and skip
