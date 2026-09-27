# Zoya Stage 2 Image Generation Patch

Changes:
- Replaced Gemini-specific ImageGenerationTool implementation with provider-neutral ImageGenerationTool.
- Added provider-neutral request/result contracts.
- Added ImageProviderRouter with capability checks, ordered fallback, transient cooldown, and permanent configuration skip.
- Added FreeLLMAPI, Pollinations, NVIDIA, and local stable-diffusion.cpp adapters.
- Preserved tool name `imagegen`, so current Brain deterministic routing and ToolExecutor network allowlist remain compatible.
- Kept backward-compatible `GeminiImageGenerationTool = ImageGenerationTool` alias.
- Updated default registry to register ImageGenerationTool.
- Added isolated router/tool tests.

Not changed:
- brain.py
- chat.py
- execution.py
- registry.py
- types.py
- frontend
- memory/research/scheduler/database
- existing ImageMagick implementation

Real provider execution is NOT claimed by these unit tests; provider credentials/services and local stable-diffusion.cpp installation must be present for smoke tests.


## Current implementation boundary

The actual Stage 2 patch preserves the existing `imagegen` tool contract and ToolExecutor network allowlist. Brain and chat orchestration are not rewritten; only the Brain's deterministic image-request fallback gains support for natural visual prompts that omit the literal word "image".

Real provider smoke tests are environment-dependent:
- FreeLLMAPI needs a reachable self-hosted gateway and its unified key.
- Pollinations needs a current API key.
- NVIDIA needs a current API key.
- Local SD needs an installed `sd-cli` binary plus a model.

The supplied sandbox cannot directly mutate `C:\Users\Ayan\Zoya`; the PowerShell installer applies the patch there, backs up only existing changed files, then runs compile/tests.
