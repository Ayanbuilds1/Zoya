# Zoya Tool Result Intelligence v1

This is the response-formatting layer above ToolExecutor.

Flow:

User -> Brain -> ToolExecutor -> Tool -> structured ToolResult -> ToolResultPresenter -> user

Scope:
- Centralizes user-facing tool result formatting.
- Preserves confirmation, blocked, failed and executed states.
- Surfaces output file paths from structured tool data.
- Does not call an AI model and does not modify ToolExecutor policy.
- Keeps the existing ImageMagick adapter and Brain decision logic intact.

The installer backs up `app/core/chat.py` and adds `app/tools/result_presentation.py` plus isolated contract tests.
