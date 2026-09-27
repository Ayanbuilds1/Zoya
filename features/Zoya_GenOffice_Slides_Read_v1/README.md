# Zoya — GenOffice Slides Read v1

## Purpose

Adds a controlled, local-only PowerPoint read capability to the already-installed **GenOffice Spreadsheet Read v2** baseline.

Supported natural-language flow:

```text
User request
   ↓
Zoya Brain
   ↓
GenOffice slides_read tool
   ↓
genoffice slides read <file> --full --json
   ↓
Structured slide data
   ↓
Zoya response
```

Example:

```text
`tool_test/test-presentation.pptx` ko read karke batao kitni slides hain aur har slide ka title kya hai.
```

## Scope

- `.pptx` read only
- slide count extraction
- slide title extraction
- structured raw slide payload preserved
- workspace escape protection
- deterministic Brain routing for obvious local presentation-read requests
- existing Spreadsheet Read v2 support preserved

Not included:

- slide editing
- slide creation
- web search
- image generation/search
- media analysis
- arbitrary CLI arguments

GenOffice documents that `genoffice slides read deck.pptx [--full] --json` returns slide structure/text suitable for agent operations. citeturn707059search0turn236915search2

## Apply

From the extracted feature directory:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\APPLY_ZOYA_GENOFFICE_SLIDES_READ_V1.ps1
```

The installer:

1. checks the feature is based on Spreadsheet Read v2,
2. backs up `app/tools/genoffice.py` and `app/core/brain.py`,
3. installs the combined slides-read patch,
4. runs Python compile checks,
5. runs adapter tests,
6. runs Brain routing tests,
7. verifies the existing ToolExecutor integration.
