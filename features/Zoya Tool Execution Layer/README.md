# Zoya Tool Execution Layer v1

This is the **policy boundary** between Zoya Brain/orchestration and the existing `app.tools.ToolRegistry`.

It does **not** connect or modify `app/core`, chat, providers, research, memory, scheduler, or frontend.

## What it adds

- `ToolExecutionRequest` — normalized request envelope
- `ToolExecutionPolicy` — allow/deny policy for permissions, network, and timeouts
- `ToolExecutionResult` — normalized gateway result with explicit status
- `ToolExecutor` — single gateway that Brain/orchestration should call instead of invoking the registry directly

## Execution flow

```text
Zoya Brain / Orchestrator
            |
            v
       ToolExecutor
            |
     Policy checks
     - permission
     - network
     - timeout
     - confirmation
            |
            v
       ToolRegistry
            |
            v
       ZoyaTool
            |
            v
       ToolResult
```

## Statuses

- `executed` — tool ran and returned success
- `confirmation_required` — execution was intentionally paused before the tool ran
- `blocked` — policy rejected the execution
- `failed` — tool was missing or the tool returned a failure

## Default policy

The default policy allows `local_read` and `local_write`, blocks network tools, and does not require confirmation for ImageMagick because the current ImageMagick manifest is marked as a local-only non-confirmation capability.

Future higher-risk tools can opt into confirmation through their manifest or a stricter policy without changing the Brain interface.

## Installation

The package assumes **Zoya Tool System v1 is already installed** and adds only the execution layer files.

From:

```text
C:\Users\Ayan\Zoya
```

run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\features\Zoya Tool Execution Layer\APPLY_TOOL_EXECUTION_V1.ps1"
```

Then verify with:

```powershell
powershell -ExecutionPolicy Bypass -File ".\features\Zoya Tool Execution Layer\VERIFY_TOOL_EXECUTION_V1.ps1"
```
