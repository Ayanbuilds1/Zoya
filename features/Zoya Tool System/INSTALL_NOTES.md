# Installation notes

This package is an **additive Tool System foundation**. It does not connect the registry to Zoya Brain/chat yet.

For the user's current layout:

```text
Zoya\
├── app\
├── tests\
└── features\
    └── Zoya Tool System\
        ├── app\tools\
        ├── tests\
        ├── APPLY_PHASE3.ps1
        └── VERIFY_PHASE3.ps1
```

From the Zoya project root, run:

```powershell
cd C:\Users\Ayan\Zoya
powershell -ExecutionPolicy Bypass -File ".\features\Zoya Tool System\APPLY_PHASE3.ps1"
```

The installer:

1. Locates the real Zoya root using `app` + `.venv`.
2. Backs up any existing `app\tools` and the targeted tool contract test under `_phase3_backups\<timestamp>`.
3. Copies only `app\tools\*` and `tests\test_tool_registry_contract.py`.
4. Runs only the Tool System contract test with the Zoya virtualenv Python.

It does **not** replace `app\core`, `app\memory`, `app\research`, `frontend`, or other existing Zoya subsystems.

After installation, verify again from the Zoya root:

```powershell
powershell -ExecutionPolicy Bypass -File ".\features\Zoya Tool System\VERIFY_PHASE3.ps1"
```
