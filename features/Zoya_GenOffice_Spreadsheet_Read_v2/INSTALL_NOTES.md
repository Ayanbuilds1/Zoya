# Install Notes

Apply this package after GenOffice CLI is installed and `genoffice --version` works in a fresh PowerShell.

The package is intentionally small and patches only:

- `app/tools/genoffice.py`
- `app/core/brain.py`

The apply script creates a timestamped backup under:

`_genoffice_spreadsheet_read_v2_backups\<timestamp>`
