from __future__ import annotations

import sys
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
from code_normalizer_pro import code_normalizer_pro as cnp


def test_guess_and_read_accepts_utf16_text(tmp_path: Path) -> None:
    sample = tmp_path / "utf16_sample.py"
    sample.write_text("print('hi')\n", encoding="utf-16")

    normalizer = cnp.CodeNormalizer(dry_run=True, use_cache=False)
    encoding, text = normalizer.guess_and_read(sample)

    assert encoding.startswith("utf-16")
    assert "print('hi')" in text


def test_in_place_rewrites_clean_utf16_to_utf8(tmp_path: Path) -> None:
    sample = tmp_path / "utf16_clean.py"
    sample.write_text("print('hi')\n", encoding="utf-16")

    normalizer = cnp.CodeNormalizer(
        in_place=True,
        create_backup=False,
        use_cache=False,
    )

    assert normalizer.process_file(sample) is True
    assert sample.read_text(encoding="utf-8") == "print('hi')\n"
    assert not sample.read_bytes().startswith((b"\xff\xfe", b"\xfe\xff"))
    assert normalizer.stats.processed == 1
    assert normalizer.stats.encoding_changes == 1


def test_dry_run_check_validates_normalized_output(tmp_path: Path, capsys) -> None:
    sample = tmp_path / "needs_fix.py"
    sample.write_bytes(b"print('hi')  \r\n")

    normalizer = cnp.CodeNormalizer(dry_run=True, use_cache=False)

    assert normalizer.process_file(sample, check_syntax=True) is True
    captured = capsys.readouterr()

    assert "Would normalize" in captured.out
    assert "Syntax: \u2713 OK" in captured.out
    assert normalizer.stats.processed == 1
    assert normalizer.stats.syntax_checks_passed == 1


def test_guess_and_read_rejects_binary_with_nuls(tmp_path: Path) -> None:
    sample = tmp_path / "blob.bin"
    sample.write_bytes(b"\x89PNG\x00\x01\x02\x03\x04\x00\x00\xff")

    normalizer = cnp.CodeNormalizer(dry_run=True, use_cache=False)

    try:
        normalizer.guess_and_read(sample)
        assert False, "Expected binary detection failure"
    except ValueError as exc:
        assert "binary" in str(exc).lower()


def test_install_git_hook_uses_current_python_and_checks_failures(tmp_path: Path, monkeypatch) -> None:
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)

    monkeypatch.chdir(tmp_path)
    installed = cnp.install_git_hook()
    assert installed is True

    hook = hooks_dir / "pre-commit"
    assert hook.exists()
    hook_text = hook.read_text(encoding="utf-8")

    assert "[sys.executable," in hook_text
    assert "for file_path in files" in hook_text
    assert 'file_path, "--dry-run"' in hook_text
    assert "result.returncode != 0" in hook_text
    assert "code_normalizer_pro.py" in hook_text


def test_install_hook_cli_exits_nonzero_outside_git_repo(tmp_path: Path) -> None:
    script = REPO_ROOT / "main.py"
    result = subprocess.run(
        [sys.executable, str(script), "--install-hook"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        cwd=tmp_path,
    )

    assert result.returncode == 1
    assert "Not a git repository" in result.stdout


def test_parallel_cache_hits_are_persisted(tmp_path: Path) -> None:
    sample_dir = tmp_path / "samples"
    sample_dir.mkdir()
    (sample_dir / "a.py").write_text("print('a')  \n", encoding="utf-8")
    (sample_dir / "b.py").write_text("print('b')\n", encoding="utf-8")

    script = REPO_ROOT / "main.py"
    cmd = [
        sys.executable,
        str(script),
        str(sample_dir),
        "-e",
        ".py",
        "--parallel",
        "--cache",
        "--in-place",
        "--no-backup",
    ]

    first = subprocess.run(
        cmd,
        input="y\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        cwd=tmp_path,
    )
    assert first.returncode == 0, first.stderr

    second = subprocess.run(
        cmd,
        input="y\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        cwd=tmp_path,
    )
    assert second.returncode == 0, second.stderr
    assert "All discovered files were unchanged and skipped by cache." in second.stdout
    assert "⊙ Cached hits: 2" in second.stdout


def test_cache_file_scoped_to_target_directory(tmp_path: Path, monkeypatch) -> None:
    sample_dir = tmp_path / "samples"
    sample_dir.mkdir()
    (sample_dir / "a.py").write_text("print('a')  \n", encoding="utf-8")

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    normalizer = cnp.CodeNormalizer(use_cache=True)
    normalizer.walk_and_process(sample_dir, [".py"])

    assert (sample_dir / cnp.CACHE_FILE).exists()
    assert not (elsewhere / cnp.CACHE_FILE).exists()
