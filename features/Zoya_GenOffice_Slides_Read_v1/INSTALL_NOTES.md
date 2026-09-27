# Install Notes — GenOffice Slides Read v1

Prerequisite: the project already has **GenOffice Spreadsheet Read v2** installed and verified.

This package is intentionally additive: its source files are built from the verified Spreadsheet Read v2 baseline and add only `slides_read` behavior.

The GenOffice CLI supports:

```text
genoffice slides read deck.pptx --full --json
```

The `--full` form is used so the adapter can receive full slide text, tables, and notes when available. citeturn707059search0
