# Zoya Phase 2 — Contract Verification v3

Verification-only. This package does **not** modify Zoya source code.

## Why v3 exists

The earlier verifier had two problems:

1. It assumed `pytest` was installed.
2. It used plain `python`, which could resolve to a global Python instead of Zoya's `.venv`.

v3 fixes both:

- prefers `C:\Users\Ayan\Zoya\.venv\Scripts\python.exe`
- falls back to another Python only when the project venv does not exist
- uses only the Python standard library
- does not require `pytest`
- does not require activating the virtual environment
- checks source contracts with AST + `py_compile`
- verifies chat ↔ memory method signatures
- verifies conversation API route surface

## Run

From the Zoya root:

```powershell
powershell -ExecutionPolicy Bypass -File .\Phase2\VERIFY_PHASE2.ps1
```

You can run it whether or not the venv is activated.

## It does NOT

- modify source files
- install dependencies
- change `.env`
- change the database
- change provider configuration
- modify frontend files
