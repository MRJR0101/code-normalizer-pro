# code-normalizer-pro

Normalize and standardize source code across a repository.

`code-normalizer-pro` performs deterministic, non-semantic cleanup passes on
source files so repositories are easier to lint, refactor, and automate.

## What Problem It Solves

Large repositories accumulate inconsistencies over time:

- mixed encodings
- mixed line endings
- stray whitespace
- missing final newlines
- partially normalized files

These inconsistencies create noise in diffs, complicate tooling, and make
automation less reliable across editors, CI systems, and refactoring passes.

`code-normalizer-pro` provides a deterministic pass over a codebase to
normalize these issues before linting, refactoring, or automated processing.

## Features

- recursive repository scanning
- UTF-8 normalization for supported text encodings
- consistent newline normalization to LF
- trailing whitespace cleanup
- final newline enforcement
- optional extension filtering
- dry-run mode for previewing changes
- clean-copy output mode or explicit in-place editing
- hash-based incremental caching
- parallel processing
- interactive file-by-file approval
- syntax checking on normalized output
- git pre-commit hook installation

## Installation

Python `>=3.10`

```bash
pip install code-normalizer-pro
```

With `uv`:

```bash
uv tool install code-normalizer-pro
```

Optional dev install:

```bash
pip install "code-normalizer-pro[dev]"
```

## Quick Start

Preview changes without modifying files:

```bash
code-normalizer-pro . --dry-run -e .py
```

Normalize files in place:

```bash
code-normalizer-pro . --in-place -e .py
```

Normalize only Python and JavaScript files:

```bash
code-normalizer-pro . -e .py -e .js --in-place
```

Run syntax checks on normalized output:

```bash
code-normalizer-pro . --dry-run -e .py --check
```

Install the git pre-commit hook:

```bash
code-normalizer-pro --install-hook
```

By default, if you do not use `--dry-run` or `--in-place`, the tool writes
clean-copy outputs beside the originals instead of overwriting the source file.

## Example

Before normalization:

`·` marks trailing spaces.

```text
def add(a, b):····
    return a + b····
```

After normalization:

```text
def add(a, b):
    return a + b
```

The normalized file is also written with UTF-8 encoding, LF newlines, and a
final newline.

## Typical Workflow

A common workflow is:

1. run `code-normalizer-pro . --dry-run`
2. run `code-normalizer-pro . --dry-run --check` if syntax validation matters
3. run `code-normalizer-pro . --in-place`
4. run a linter or formatter
5. commit changes

This reduces formatting noise and improves deterministic tool output.

## CLI Options

| Option | Description |
|------|-------------|
| `--dry-run` | show proposed changes without writing files |
| `--in-place` | apply normalization changes to the original files |
| `-o, --output` | write a normalized copy to a specific output file in single-file mode |
| `-e, --ext` | restrict processing to specific file extensions |
| `--check` | run syntax checks on normalized output |
| `--parallel` | process files with multiple workers |
| `--workers` | set the worker count for parallel mode |
| `--interactive` | approve each file before applying changes |
| `--cache` | enable incremental cache behavior (default) |
| `--no-cache` | force a full rescan without cache |
| `--no-backup` | disable backups for in-place edits |
| `--install-hook` | install a git pre-commit hook |
| `-v, --verbose` | show detailed processing information |

## Safety

`code-normalizer-pro` is designed to be conservative.

- transformations are deterministic
- transformations do not change intended program behavior
- binary files are skipped automatically
- `--dry-run` previews changes without writing files
- `--in-place` is explicit
- in-place mode creates backups by default unless `--no-backup` is used
- syntax checks run against normalized output without rewriting the original file in dry-run mode

## When to Use

`code-normalizer-pro` is useful when:

- preparing a repository for automated refactoring
- cleaning legacy codebases
- reducing formatting noise in version control
- standardizing files before CI linting
- making source files consistent before AI-assisted tooling

## Supported Encodings

- `utf-8`
- `utf-8-sig`
- `utf-16`
- `utf-16-le`
- `utf-16-be`
- `windows-1252`
- `latin-1`
- `iso-8859-1`

## Supported Syntax Checks

- Python
- JavaScript
- TypeScript
- Go
- Rust
- C
- C++
- Java

If a checker is not installed, the tool reports that as unavailable instead of
failing the whole run.

## Design Philosophy

`code-normalizer-pro` focuses on three principles:

1. deterministic transformations
2. no semantic changes
3. automation-friendly output

## License

MIT License
