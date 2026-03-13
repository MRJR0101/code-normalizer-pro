# VERIFY.md - code-normalizer-pro

Run these commands to confirm the project is healthy after install or changes.

---

## 1. Install (dev mode)

```
cd C:\Dev\PROJECTS\00_PyToolbelt\02_Scanners\Code-Normalizer-Pro
uv venv --python 3.11
uv pip install -e ".[dev]"
```

Expected: no errors, package installs with tqdm and pytest.

---

## 2. CLI smoke test

```
python main.py --help
python code_normalizer_pro/code_normalizer_pro.py --help
```

Expected: usage/help text printed, exit code 0.

---

## 3. Entry point (post-install)

```
code-normalizer-pro --help
```

Expected: same help text as above. Confirms console_scripts wiring is correct.

---

## 4. Dry-run on a real file

```
python main.py code_normalizer_pro/code_normalizer_pro.py --dry-run -e .py
```

Expected: "already normalized" or "Would normalize" output, no file changes, exit 0.

---

## 5. Run tests

```
python -m pytest tests/ -v
```

Expected: all tests pass, 0 failures.

---

## 6. Build package artifacts

```
uv pip install build
python -m build --sdist --wheel
```

Expected: dist/ contains a .whl and .tar.gz with no errors.

---

## 7. Git status check

```
git status
git log --oneline -5
```

Expected: working tree clean after commit, history shows clean initial release.

---

## Known issues

None at v3.0.1.
