# Install notes

Extract under:

`C:\Users\Ayan\Zoya\features\Zoya_Image_Generation_v1`

Then in that directory:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\APPLY_ZOYA_IMAGE_GENERATION_V1.ps1
```

Before the real generation regression test, ensure the backend is restarted after installation and that `GEMINI_API_KEY` is available to the backend process.

The installer creates a timestamped backup under `_image_generation_v1_backups`.
