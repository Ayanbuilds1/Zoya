# Zoya Phase 2 — Contract Verification v2

This is a verification-only package. It does not modify Zoya source code.

The previous verifier incorrectly required `chat.py` to contain the
`include_always_relevant` keyword. The clean baseline no longer needs that
argument because its current memory-context path uses `MemoryManager.get_memories()`.

This v2 verifier:
- resolves the actual project root automatically from the verifier location
- validates `ZoyaChatService.list_conversations()` and `create_conversation()`
- validates `MemoryManager.list_conversations()` and `get_relevant_memories()`
- does not require an obsolete `include_always_relevant` call in `chat.py`
- runs the real Python contract tests through pytest

Run from any PowerShell directory:

    powershell -ExecutionPolicy Bypass -File .\Phase2\VERIFY_PHASE2.ps1

or, if the package is somewhere else, pass its full path.
