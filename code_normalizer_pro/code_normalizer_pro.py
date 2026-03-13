#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Code Normalizer Pro - Production-Grade Code Normalization Tool
================================================================

High-Impact Features:
- Parallel Processing (multi-core performance)
- Pre-Commit Hook Generation
- Incremental Processing (hash-based caching)
- Multi-Language Syntax Checking
- Interactive Mode (file-by-file approval)

Plus all v2.0 features:
- Dry-run mode, In-place editing, Automatic backups
- Progress tracking, Detailed statistics, Error handling

Author: MR
Date: 2026-02-09
Version: 3.0 Pro
"""

import argparse
import subprocess
import sys
import os
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Set
from dataclasses import dataclass, asdict
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Optional dependencies
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

COMMON_ENCODINGS = [
    "utf-8",
    "utf-8-sig",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
    "windows-1252",
    "latin-1",
    "iso-8859-1",
]

# Multi-language syntax checkers
SYNTAX_CHECKERS = {
    ".py": {
        "command": [sys.executable, "-m", "py_compile"],
        "stdin": False,
        "file_arg": True,
    },
    ".js": {
        "command": ["node", "--check"],
        "stdin": False,
        "file_arg": True,
    },
    ".ts": {
        "command": ["tsc", "--noEmit"],
        "stdin": False,
        "file_arg": True,
    },
    ".go": {
        "command": ["gofmt", "-e"],
        "stdin": True,
        "file_arg": False,
    },
    ".rs": {
        "command": ["rustc", "--crate-type", "lib", "-"],
        "stdin": True,
        "file_arg": False,
    },
    ".c": {
        "command": ["gcc", "-fsyntax-only", "-x", "c"],
        "stdin": False,
        "file_arg": True,
    },
    ".cpp": {
        "command": ["g++", "-fsyntax-only", "-x", "c++"],
        "stdin": False,
        "file_arg": True,
    },
    ".java": {
        "command": ["javac", "-Xstdout"],
        "stdin": False,
        "file_arg": True,
    },
}

CACHE_FILE = ".normalize-cache.json"


@dataclass
class FileCache:
    """Cache entry for a file"""
    path: str
    hash: str
    last_normalized: str
    size: int


@dataclass
class ProcessStats:
    """Statistics for processing session"""
    total_files: int = 0
    processed: int = 0
    skipped: int = 0
    cached: int = 0
    errors: int = 0
    encoding_changes: int = 0
    newline_fixes: int = 0
    whitespace_fixes: int = 0
    syntax_checks_passed: int = 0
    syntax_checks_failed: int = 0
    bytes_removed: int = 0


class CacheManager:
    """Manages file hash cache for incremental processing"""

    def __init__(self, cache_path: Optional[Path] = None):
        self.cache_path = cache_path or Path(CACHE_FILE)
        self.cache: Dict[str, FileCache] = {}
        self.load()

    def load(self):
        """Load cache from disk"""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cache = {
                        k: FileCache(**v) for k, v in data.items()
                    }
            except Exception as e:
                print(f"Warning: Could not load cache: {e}")
                self.cache = {}

    def save(self):
        """Save cache to disk"""
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                data = {k: asdict(v) for k, v in self.cache.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save cache: {e}")

    def get_file_hash(self, path: Path) -> str:
        """Calculate SHA256 hash of file"""
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def is_cached(self, path: Path) -> bool:
        """Check if file is in cache and unchanged"""
        path_str = str(path)
        if path_str not in self.cache:
            return False

        cached = self.cache[path_str]

        # Check if file still exists
        if not path.exists():
            return False

        # Check size first (fast check)
        if path.stat().st_size != cached.size:
            return False

        # Check hash (slower but accurate)
        current_hash = self.get_file_hash(path)
        return current_hash == cached.hash

    def update(self, path: Path):
        """Update cache entry for file"""
        path_str = str(path)
        self.cache[path_str] = FileCache(
            path=path_str,
            hash=self.get_file_hash(path),
            last_normalized=datetime.now().isoformat(),
            size=path.stat().st_size
        )


class CodeNormalizer:
    """Production-grade code normalizer with advanced features"""

    def __init__(self,
                 dry_run: bool = False,
                 verbose: bool = False,
                 in_place: bool = False,
                 create_backup: bool = True,
                 use_cache: bool = True,
                 interactive: bool = False,
                 parallel: bool = False,
                 max_workers: Optional[int] = None,
                 cache_path: Optional[Path] = None):
        self.dry_run = dry_run
        self.verbose = verbose
        self.in_place = in_place
        self.create_backup = create_backup
        self.use_cache = use_cache
        self.interactive = interactive
        self.parallel = parallel
        self.max_workers = max_workers or max(1, cpu_count() - 1)
        self.cache_path_override = cache_path
        self.stats = ProcessStats()
        self.errors: List[Tuple[Path, str]] = []
        self.cache = CacheManager(cache_path) if use_cache and cache_path else None

    def _resolve_cache_path(self, target: Path) -> Path:
        """Place cache beside the project or file being processed."""
        if self.cache_path_override:
            return self.cache_path_override
        base = target if target.is_dir() else target.parent
        return base / CACHE_FILE

    def _ensure_cache_manager(self, target: Path) -> None:
        """Bind cache storage to the current processing target."""
        if not self.use_cache:
            return

        desired_path = self._resolve_cache_path(target)
        if self.cache is None or self.cache.cache_path != desired_path:
            self.cache = CacheManager(desired_path)

    def _should_show_progress(self) -> bool:
        """Avoid tqdm collisions with verbose per-file output."""
        return HAS_TQDM and not self.interactive and not self.verbose

    def _looks_like_utf16_text(self, data: bytes) -> bool:
        """Best-effort check for UTF-16 text before binary rejection."""
        if not data:
            return False

        # BOM signatures
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            return True

        sample = data[:256]
        if len(sample) < 4:
            return False

        for enc in ("utf-16-le", "utf-16-be"):
            try:
                decoded = sample.decode(enc)
            except UnicodeDecodeError:
                continue

            if not decoded:
                continue

            printable = sum(1 for ch in decoded if ch.isprintable() or ch in "\r\n\t")
            alpha = sum(1 for ch in decoded if ch.isalpha())
            printable_ratio = printable / len(decoded)

            # Require mostly printable content and at least some alphabetic text.
            if printable_ratio >= 0.85 and alpha >= max(1, len(decoded) // 20):
                return True

        return False

    def guess_and_read(self, path: Path) -> Tuple[str, str]:
        """Detect encoding and read file"""
        data = path.read_bytes()

        if b"\x00" in data and not self._looks_like_utf16_text(data):
            raise ValueError(f"File appears to be binary")

        last_error = None
        for enc in COMMON_ENCODINGS:
            try:
                text = data.decode(enc)
                return enc, text
            except UnicodeDecodeError as e:
                last_error = e
                continue

        raise UnicodeError(
            f"Could not decode with common encodings"
        ) from last_error

    def normalize_text(self, text: str) -> Tuple[str, dict]:
        """Normalize text and track changes"""
        changes = {
            'newline_fixes': 0,
            'whitespace_fixes': 0,
            'bytes_removed': 0,
            'final_newline_added': False
        }

        original = text
        original_size = len(text.encode('utf-8'))

        # Normalize newlines
        if '\r\n' in text or '\r' in text:
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            changes['newline_fixes'] = original.count('\r\n') + original.count('\r')

        # Strip trailing whitespace
        lines = text.split("\n")
        stripped_lines = [line.rstrip() for line in lines]

        whitespace_removed = sum(
            len(orig) - len(stripped)
            for orig, stripped in zip(lines, stripped_lines)
        )
        changes['whitespace_fixes'] = whitespace_removed

        text = "\n".join(stripped_lines)

        # Ensure final newline
        if not text.endswith("\n"):
            text += "\n"
            changes['final_newline_added'] = True

        # Calculate bytes removed
        new_size = len(text.encode('utf-8'))
        changes['bytes_removed'] = original_size - new_size

        return text, changes

    def _run_syntax_check(self, path: Path, content: Optional[str] = None) -> Tuple[bool, str]:
        """Run a syntax checker against a file or normalized text buffer."""
        ext = path.suffix.lower()

        if ext not in SYNTAX_CHECKERS:
            return True, "No checker available"

        checker = SYNTAX_CHECKERS[ext]
        cmd = checker['command'].copy()
        temp_path: Optional[Path] = None

        try:
            if checker['file_arg']:
                target_path = path
                if content is not None:
                    with tempfile.NamedTemporaryFile(
                        "w",
                        encoding="utf-8",
                        newline="\n",
                        suffix=path.suffix,
                        delete=False,
                    ) as tmp:
                        tmp.write(content)
                        temp_path = Path(tmp.name)
                    target_path = temp_path

                cmd.append(str(target_path))
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=10,
                    text=True
                )
            else:
                # Read file and pass via stdin
                if content is None:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                result = subprocess.run(
                    cmd,
                    input=content,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=10,
                    text=True
                )

            if result.returncode == 0:
                return True, "OK"
            else:
                return False, result.stderr.strip()[:100]

        except FileNotFoundError:
            return True, f"{checker['command'][0]} not installed"
        except subprocess.TimeoutExpired:
            return False, "Timeout"
        except Exception as e:
            return False, str(e)[:100]
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink(missing_ok=True)

    def syntax_check(self, path: Path, language: Optional[str] = None) -> Tuple[bool, str]:
        """Run syntax check on file - multi-language support"""
        return self._run_syntax_check(path)

    def syntax_check_text(self, path: Path, text: str) -> Tuple[bool, str]:
        """Syntax check normalized content without writing it to the real file."""
        return self._run_syntax_check(path, content=text)

    def create_backup_file(self, path: Path) -> Path:
        """Create timestamped backup"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = path.with_suffix(f".backup_{timestamp}{path.suffix}")
        backup_path.write_bytes(path.read_bytes())
        return backup_path

    def get_output_path(self, input_path: Path, output_path: Optional[Path]) -> Path:
        """Determine output path"""
        if output_path:
            return output_path
        if self.in_place:
            return input_path
        return input_path.with_name(input_path.stem + "_clean" + input_path.suffix)

    def show_diff(self, path: Path, original: str, normalized: str) -> bool:
        """Show diff and get user approval (interactive mode)"""
        print(f"\n{'='*70}")
        print(f"File: {path}")
        print(f"{'='*70}")

        # Simple line-by-line diff
        orig_lines = original.split('\n')
        norm_lines = normalized.split('\n')

        changes = []
        for i, (orig, norm) in enumerate(zip(orig_lines, norm_lines), 1):
            if orig != norm:
                changes.append((i, orig, norm))

        # Show first 10 changes
        for line_num, orig, norm in changes[:10]:
            print(f"\nLine {line_num}:")
            print(f"  - {repr(orig)}")
            print(f"  + {repr(norm)}")

        if len(changes) > 10:
            print(f"\n... and {len(changes) - 10} more changes")

        print(f"\n{'='*70}")

        # Get user input
        while True:
            choice = input("Apply changes? [y]es / [n]o / [d]iff all / [q]uit: ").lower()

            if choice in ('y', 'yes'):
                return True
            elif choice in ('n', 'no'):
                return False
            elif choice in ('d', 'diff'):
                # Show all changes
                for line_num, orig, norm in changes:
                    print(f"\nLine {line_num}:")
                    print(f"  - {repr(orig)}")
                    print(f"  + {repr(norm)}")
            elif choice in ('q', 'quit'):
                print("Quitting...")
                sys.exit(0)
            else:
                print("Invalid choice. Please enter y, n, d, or q.")

    def process_file(self, path: Path, output_path: Optional[Path] = None,
                    check_syntax: bool = False) -> bool:
        """Process a single file"""
        self.stats.total_files += 1

        try:
            self._ensure_cache_manager(path)

            # Check cache first (incremental processing)
            if self.use_cache and self.cache and self.cache.is_cached(path):
                if self.verbose:
                    print(f"⊙ CACHED {path.name} - unchanged since last run")
                self.stats.cached += 1
                self.stats.skipped += 1
                return True

            # Read and detect encoding
            enc, text = self.guess_and_read(path)

            # Normalize
            normalized, changes = self.normalize_text(text)

            # Determine output
            out_path = self.get_output_path(path, output_path)

            needs_encoding_fix = enc != "utf-8"
            needs_content_fix = text != normalized

            # Check if any normalization work is needed
            if not needs_content_fix and not needs_encoding_fix:
                if self.verbose:
                    print(f"⊗ SKIP {path.name} - already normalized")
                self.stats.skipped += 1

                # Update cache even for unchanged files
                if self.use_cache and self.cache:
                    self.cache.update(path)

                return True

            # Interactive mode
            if self.interactive and not self.dry_run:
                if not self.show_diff(path, text, normalized):
                    print(f"⊗ SKIP {path.name} - user declined")
                    self.stats.skipped += 1
                    return True

            # Dry run mode
            if self.dry_run:
                print(f"[DRY RUN] Would normalize: {path}")
                if enc != "utf-8":
                    print(f"  Encoding: {enc} → utf-8")
                    self.stats.encoding_changes += 1
                if changes['newline_fixes'] > 0:
                    print(f"  Newlines: {changes['newline_fixes']} fixes")
                    self.stats.newline_fixes += 1
                if changes['whitespace_fixes'] > 0:
                    print(f"  Whitespace: {changes['whitespace_fixes']} chars removed")
                    self.stats.whitespace_fixes += 1
                if changes['final_newline_added']:
                    print(f"  Final newline: added")

                if check_syntax:
                    ok, reason = self.syntax_check_text(path, normalized)
                    status = "✓ OK" if ok else f"✗ {reason}"
                    print(f"  Syntax: {status}")
                    if ok:
                        self.stats.syntax_checks_passed += 1
                    else:
                        self.stats.syntax_checks_failed += 1

                self.stats.bytes_removed += changes['bytes_removed']
                self.stats.processed += 1
                return True

            # Create backup if needed
            backup_created = None
            if self.in_place and self.create_backup:
                backup_created = self.create_backup_file(path)

            # Write normalized version
            out_path.write_text(normalized, encoding="utf-8", newline="\n")

            # Update stats
            self.stats.processed += 1
            self.stats.bytes_removed += changes['bytes_removed']
            if enc != "utf-8":
                self.stats.encoding_changes += 1
            if changes['newline_fixes'] > 0:
                self.stats.newline_fixes += 1
            if changes['whitespace_fixes'] > 0:
                self.stats.whitespace_fixes += 1

            # Report
            if self.in_place:
                msg = f"✓ {path.name} (in-place)"
            else:
                msg = f"✓ {path.name} → {out_path.name}"

            if enc != "utf-8":
                msg += f" [{enc}→utf-8]"

            print(msg)

            if backup_created:
                print(f"  Backup: {backup_created.name}")

            # Syntax check
            if check_syntax:
                ok, reason = self.syntax_check(out_path)
                status = "✓ OK" if ok else f"✗ {reason}"
                print(f"  Syntax: {status}")

                if ok:
                    self.stats.syntax_checks_passed += 1
                else:
                    self.stats.syntax_checks_failed += 1

            # Update cache
            if self.use_cache and self.cache:
                self.cache.update(path)

            return True

        except Exception as e:
            self.stats.errors += 1
            self.errors.append((path, str(e)))
            print(f"✗ ERROR {path.name}: {e}")
            return False

    def walk_and_process(self, root: Path, exts: List[str],
                        check_syntax: bool = False) -> None:
        """Process all files in directory tree"""
        self._ensure_cache_manager(root)

        # Collect files
        files = []
        for ext in exts:
            files.extend(root.rglob(f"*{ext}"))

        files = [f for f in files if f.is_file()]

        if not files:
            print(f"No files with extensions {exts} found in {root}")
            return

        files_to_process = files
        if self.use_cache and self.cache:
            uncached_files = []
            cached_hits = 0
            for file_path in files:
                if self.cache.is_cached(file_path):
                    cached_hits += 1
                    self.stats.cached += 1
                    self.stats.skipped += 1
                    self.stats.total_files += 1
                    if self.verbose:
                        print(f"⊙ CACHED {file_path.name} - unchanged since last run")
                else:
                    uncached_files.append(file_path)
            files_to_process = uncached_files

            if cached_hits and self.verbose:
                print(f"⊙ Cache prefilter skipped {cached_hits} unchanged file(s)")

        print(f"\n📁 Found {len(files)} file(s) to process")
        print(f"   Extensions: {', '.join(exts)}")
        mode_desc = "DRY RUN" if self.dry_run else "IN-PLACE" if self.in_place else "CLEAN COPY"
        if self.parallel:
            mode_desc += f" (PARALLEL {self.max_workers} workers)"
        if self.use_cache:
            mode_desc += " (CACHED)"
        if self.interactive:
            mode_desc += " (INTERACTIVE)"
        print(f"   Mode: {mode_desc}")

        if not files_to_process:
            print("All discovered files were unchanged and skipped by cache.")
            return

        # Confirmation
        if not self.dry_run and self.in_place and not self.interactive:
            response = input(
                f"\n⚠️  In-place editing will scan {len(files_to_process)} file(s) "
                "and modify only files that need changes. Continue? (y/N): "
            )
            if response.lower() != 'y':
                print("Cancelled")
                return

        # Process files

        if self.parallel and not self.interactive:
            self._process_parallel(files_to_process, check_syntax)
        else:
            self._process_sequential(files_to_process, check_syntax)

        # Save cache
        if self.use_cache and self.cache and not self.dry_run:
            self.cache.save()

    def _process_sequential(self, files: List[Path], check_syntax: bool):
        """Process files sequentially"""
        iterator = tqdm(files, desc="Processing") if self._should_show_progress() else files

        for file_path in iterator:
            self.process_file(file_path, check_syntax=check_syntax)

    def _process_parallel(self, files: List[Path], check_syntax: bool):
        """Process files in parallel"""
        print(f"\n🚀 Parallel processing with {self.max_workers} workers...\n")

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(
                    process_file_worker,
                    file_path,
                    self.dry_run,
                    self.in_place,
                    self.create_backup,
                    check_syntax
                ): file_path
                for file_path in files
            }

            # Progress tracking
            iterator = as_completed(futures)
            if self._should_show_progress():
                iterator = tqdm(iterator, total=len(files), desc="Processing")

            # Collect results
            for future in iterator:
                file_path = futures[future]
                try:
                    success, stats_update, error = future.result()

                    # Update stats
                    self.stats.total_files += 1
                    if success:
                        self.stats.processed += stats_update['processed']
                        self.stats.skipped += stats_update['skipped']
                        self.stats.encoding_changes += stats_update['encoding_changes']
                        self.stats.newline_fixes += stats_update['newline_fixes']
                        self.stats.whitespace_fixes += stats_update['whitespace_fixes']
                        self.stats.bytes_removed += stats_update['bytes_removed']
                        self.stats.syntax_checks_passed += stats_update['syntax_checks_passed']
                        self.stats.syntax_checks_failed += stats_update['syntax_checks_failed']
                        if self.use_cache and self.cache and not self.dry_run:
                            self.cache.update(file_path)
                    else:
                        self.stats.errors += 1
                        self.errors.append((file_path, error))

                except Exception as e:
                    self.stats.errors += 1
                    self.errors.append((file_path, str(e)))

    def print_summary(self):
        """Print processing summary"""
        print("\n" + "="*70)
        print("PROCESSING SUMMARY")
        print("="*70)
        print(f"  Total files: {self.stats.total_files}")
        print(f"  ✓ Processed: {self.stats.processed}")
        print(f"  ⊗ Skipped: {self.stats.skipped}")
        if self.use_cache:
            print(f"  ⊙ Cached hits: {self.stats.cached}")
        print(f"  ✗ Errors: {self.stats.errors}")
        print()
        print(f"  Encoding changes: {self.stats.encoding_changes}")
        print(f"  Newline fixes: {self.stats.newline_fixes}")
        print(f"  Whitespace fixes: {self.stats.whitespace_fixes}")
        print(f"  Bytes removed: {self.stats.bytes_removed:,}")

        if self.stats.syntax_checks_passed > 0 or self.stats.syntax_checks_failed > 0:
            print()
            print(f"  Syntax checks passed: {self.stats.syntax_checks_passed}")
            print(f"  Syntax checks failed: {self.stats.syntax_checks_failed}")

        if self.errors:
            print("\n❌ ERRORS:")
            for path, error in self.errors[:10]:
                print(f"  {path.name}: {error}")
            if len(self.errors) > 10:
                print(f"  ... and {len(self.errors) - 10} more")

        print("="*70)


def process_file_worker(file_path: Path, dry_run: bool, in_place: bool,
                       create_backup: bool, check_syntax: bool) -> Tuple[bool, dict, str]:
    """Worker function for parallel processing"""
    normalizer = CodeNormalizer(
        dry_run=dry_run,
        in_place=in_place,
        create_backup=create_backup,
        use_cache=False,  # Cache managed by main process
        interactive=False,
        parallel=False
    )

    success = normalizer.process_file(file_path, check_syntax=check_syntax)

    stats_update = {
        'processed': normalizer.stats.processed,
        'skipped': normalizer.stats.skipped,
        'encoding_changes': normalizer.stats.encoding_changes,
        'newline_fixes': normalizer.stats.newline_fixes,
        'whitespace_fixes': normalizer.stats.whitespace_fixes,
        'bytes_removed': normalizer.stats.bytes_removed,
        'syntax_checks_passed': normalizer.stats.syntax_checks_passed,
        'syntax_checks_failed': normalizer.stats.syntax_checks_failed,
    }

    error = normalizer.errors[0][1] if normalizer.errors else ""

    return success, stats_update, error


def install_git_hook(hook_type: str = "pre-commit") -> bool:
    """Install pre-commit hook for automatic normalization"""
    git_dir = Path(".git")

    if not git_dir.exists():
        print("❌ Not a git repository")
        return False

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    hook_path = hooks_dir / hook_type

    normalizer_script = Path(__file__).resolve()

    # Create hook script
    hook_script = f"""#!/usr/bin/env python3
# Auto-generated by code_normalizer_pro.py
import subprocess
import sys
from pathlib import Path

def main():
    # Get staged Python files
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True
    )

    files = [
        f for f in result.stdout.strip().split('\\n')
        if f.endswith('.py') and Path(f).exists()
    ]

    if not files:
        sys.exit(0)

    print(f"🔍 Checking {{len(files)}} Python file(s)...")

    # Run normalizer in check mode, one file at a time. The CLI accepts a
    # single positional path, so passing all files at once breaks argparse.
    needs_normalization = []
    for file_path in files:
        result = subprocess.run(
            [sys.executable, r"{normalizer_script}", file_path, "--dry-run"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print("\\n❌ Normalizer execution failed")
            if result.stderr.strip():
                print(result.stderr.strip())
            sys.exit(result.returncode)

        if "Would normalize:" in result.stdout:
            needs_normalization.append(file_path)

    if needs_normalization:
        print("\\n⚠️  Some files need normalization:")
        for file_path in needs_normalization:
            print(f" - {{file_path}}")
        print("\\nRun: uv run code-normalizer-pro <file> --in-place")
        print("Or add --no-verify to skip this check")
        sys.exit(1)

    print("✅ All files are normalized")
    sys.exit(0)

if __name__ == "__main__":
    main()
"""

    # Write hook
    hook_path.write_text(hook_script, encoding="utf-8", newline="\n")
    hook_path.chmod(0o755)

    print(f"✅ Installed {hook_type} hook at {hook_path}")
    print(f"   Hook will check Python files before commit")
    print(f"   Use 'git commit --no-verify' to skip check")

    return True


def main():
    ap = argparse.ArgumentParser(
        prog="code-normalizer-pro",
        description="Code Normalizer Pro - Production-grade normalization tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run with parallel processing
  uv run code-normalizer-pro /path/to/dir --dry-run --parallel

  # Interactive mode (file-by-file approval)
  uv run code-normalizer-pro /path/to/dir --interactive

  # In-place normalization (cache is enabled by default)
  uv run code-normalizer-pro /path/to/dir -e .py --in-place

  # Multi-language syntax checking on normalized output
  uv run code-normalizer-pro /path/to/dir -e .py -e .js -e .go --check

  # Install git pre-commit hook
  uv run code-normalizer-pro --install-hook

  # Parallel processing (all cores)
  uv run code-normalizer-pro /path/to/dir --parallel --in-place
        """
    )

    ap.add_argument(
        "path",
        type=Path,
        nargs="?",
        help="File or directory to process"
    )
    ap.add_argument(
        "-e", "--ext",
        action="append",
        help="File extensions (e.g. -e .py -e .js)"
    )
    ap.add_argument(
        "-o", "--output",
        type=Path,
        help="Output file (single file mode only)"
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="Run syntax check on normalized output"
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files"
    )
    ap.add_argument(
        "--in-place",
        action="store_true",
        help="Edit files in-place"
    )
    ap.add_argument(
        "--no-backup",
        action="store_true",
        help="Don't create backups (dangerous!)"
    )
    cache_group = ap.add_mutually_exclusive_group()
    cache_group.add_argument(
        "--cache",
        action="store_true",
        help="Enable incremental processing cache (default)"
    )
    cache_group.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable incremental processing cache"
    )
    ap.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode (approve each file)"
    )
    ap.add_argument(
        "--parallel",
        action="store_true",
        help="Parallel processing (multi-core)"
    )
    ap.add_argument(
        "--workers",
        type=int,
        help=f"Number of parallel workers (default: {max(1, cpu_count() - 1)})"
    )
    ap.add_argument(
        "--install-hook",
        action="store_true",
        help="Install git pre-commit hook"
    )
    ap.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )

    args = ap.parse_args()

    # Install hook mode
    if args.install_hook:
        success = install_git_hook()
        sys.exit(0 if success else 1)

    # Validate
    if not args.path:
        ap.print_help()
        sys.exit(1)

    if args.output and args.path.is_dir():
        print("Error: --output only works with single file")
        sys.exit(1)

    if args.no_backup and not args.in_place:
        print("Warning: --no-backup has no effect without --in-place")

    if args.interactive and args.parallel:
        print("Warning: --interactive disables --parallel")
        args.parallel = False

    # Determine cache setting
    use_cache = not args.no_cache

    # Create normalizer
    normalizer = CodeNormalizer(
        dry_run=args.dry_run,
        verbose=args.verbose,
        in_place=args.in_place,
        create_backup=not args.no_backup,
        use_cache=use_cache,
        interactive=args.interactive,
        parallel=args.parallel,
        max_workers=args.workers,
        cache_path=(args.path / CACHE_FILE) if args.path and args.path.is_dir() else (args.path.parent / CACHE_FILE)
    )

    print("="*70)
    print("CODE NORMALIZER PRO v3.0")
    print("="*70)

    # Process
    try:
        if args.path.is_dir():
            exts = args.ext or [".py"]
            normalizer.walk_and_process(args.path, exts, check_syntax=args.check)
        else:
            if not args.path.exists():
                print(f"Error: File not found: {args.path}")
                sys.exit(1)

            normalizer.process_file(args.path, args.output, check_syntax=args.check)

        # Summary
        normalizer.print_summary()

        # Exit code
        sys.exit(0 if normalizer.stats.errors == 0 else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        normalizer.print_summary()
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
