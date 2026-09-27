# Zoya — GenOffice Spreadsheet Read v2

This is a minimal upgrade on top of the already-installed GenOffice Tool v1 + ToolExecutor + Tool Brain Integration + Tool Result Intelligence stack.

## What changed

1. `GenOfficeTool` now exposes a local `sheet_read` operation backed by:
   `genoffice sheet read <file> --json`
2. `ZoyaBrain` adds deterministic routing for obvious spreadsheet-read requests involving `.xlsx`, `.xlsm`, or `.csv` files.
3. The tool result now includes structured rows and a human-readable table so the existing chat result presenter can answer data-reading requests directly.

## Important scope

- No GenOffice cloud `search`, `image`, or `media` commands are enabled.
- No frontend changes.
- No provider, research, memory, scheduler, default-registry, or ToolExecutor changes.
- Existing convert/create/render/info behavior remains available.
- The installer backs up the two modified project files before replacing them.

## Install

From the project PowerShell terminal:

```powershell
cd C:\Users\Ayan\Zoya\features\Zoya_GenOffice_Spreadsheet_Read_v2
.\APPLY_ZOYA_GENOFFICE_SPREADSHEET_READ_V2.ps1
```

If execution policy blocks the script:

```powershell
powershell -ExecutionPolicy Bypass -File .\APPLY_ZOYA_GENOFFICE_SPREADSHEET_READ_V2.ps1
```

## Test

Restart the Zoya backend after applying the patch, then send:

```text
tool_test/test-sheet.xlsx ko read karke Data sheet ka score batao.
```

Expected result should contain the sheet rows, e.g.:

```text
Name | Score
Ayan | 95
Zoya | 98
```

## Verification

```powershell
.\VERIFY_ZOYA_GENOFFICE_SPREADSHEET_READ_V2.ps1
```
