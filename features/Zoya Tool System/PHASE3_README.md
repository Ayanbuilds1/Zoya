# Zoya Tool System v1 — Phase 3 foundation

## What this package does

This is the first **additive** Tool System foundation for Zoya. It does not modify Zoya's existing Brain, chat, provider, research, memory, scheduler, or frontend code.

It introduces:

- `ZoyaTool` — stable tool interface
- `ToolManifest` — machine-readable capability metadata
- `ToolResult` — normalized structured result envelope
- `ToolRegistry` — discovery + controlled execution registry
- `ImageMagickTool` — first real local tool adapter
- `build_default_registry()` — initial registry builder
- stdlib-only contract tests and a PowerShell verifier

## Architecture

```text
Zoya Brain / future orchestrator
              |
              v
       ToolRegistry
              |
       +------+------+
       |             |
       v             v
  ToolManifest   Tool.execute()
                     |
                     v
               ToolResult
```

The first tool is intentionally ImageMagick because it is local, low-risk, API-key free, and easy to verify.

## Important boundary

This package **does not yet connect ToolRegistry to `ZoyaChatService` or Brain**. The next integration step should only happen after these contracts are verified in the user's real Zoya checkout.

## ImageMagick behavior

Supported operations are deliberately allow-listed:

- `convert`
- `resize`
- `crop`

Arbitrary ImageMagick flags are not accepted from user input.

Paths are constrained to a configured workspace root. This is a foundation for the later tool permission/sandbox layer.

## Dependencies

No new Python dependency is required. The verifier uses the Python standard library's `unittest`.

ImageMagick itself is an external local dependency and is checked at execution time. The package does not auto-install it.

## Verification

Extract this package anywhere, copy its `app/tools` and `tests` into the Zoya root, then run the verifier from the Zoya root **only after you decide to apply the additive Tool System files**:

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_PHASE3.ps1
```

The verifier prefers `C:\Users\Ayan\Zoya\.venv\Scripts\python.exe` and does not require pytest.
