# Zoya GenOffice Tool v1

Adds a controlled local `genoffice` adapter to the existing Zoya Tool Registry.

## Exposed operations

- `info` — inspect a document with `genoffice info ... --json`
- `convert` — convert a file with `genoffice convert ... --json`
- `create` — create a native Office/PDF file from a source file with `genoffice create ... --json`
- `render` — render a document to PNGs with `genoffice render ... --json`

The adapter enforces Zoya's workspace boundary and verifies output creation. It does not accept arbitrary CLI flags and it deliberately does not expose GenOffice's cloud-facing `search`, `image`, or `media` commands.

GenOffice's official CLI currently exposes document/spreadsheet/presentation/PDF operations such as `info`, `convert`, `create`, `render`, `docs`, `sheet`, and `slides`; the CLI also supports MCP. See the official docs before testing against a local installation:
https://github.com/genspark-ai/genoffice/blob/main/packages/cli/README.md

## Apply

From `C:\Users\Ayan\Zoya`:

```powershell
powershell -ExecutionPolicy Bypass -File ".\features\Zoya GenOffice Tool v1\APPLY_ZOYA_GENOFFICE_TOOL_V1.ps1"
```

The installer backs up existing `app\tools\genoffice.py`, `app\tools\defaults.py`, and `app\tools\__init__.py` under `_genoffice_tool_backups`.

## Verify local GenOffice installation later

```powershell
genoffice --version
```

The Zoya adapter will return a structured `tool_unavailable` result until the `genoffice` CLI is available on the backend process PATH.
