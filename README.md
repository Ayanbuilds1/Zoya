# Zoya Clean Baseline v1

This is a **drop-in recovery baseline** for the current Zoya project.

Goal: restore the known-good rich frontend and align the conversation/memory API **without replacing Zoya's current AI/research core logic**.

## Files replaced

- `frontend/src/App.jsx`
- `frontend/src/App.css`
- `frontend/src/index.css`
- `backend/app/core/chat.py`
- `backend/app/memory/manager.py`
- `backend/app/api/routes/chat.py`

## What is intentionally NOT changed

- `backend/app/core/ai.py`
- `backend/app/core/brain.py`
- `backend/app/research/*`
- `backend/app/ai/*`
- `.env`
- SQLite/database files
- frontend component/hook files outside the three listed frontend files

## Restored frontend behavior

- sidebar
- recent conversations
- pinned chats
- collapse/expand sidebar
- chat search
- New Chat
- conversation switching
- rename/delete conversation
- edit user message
- copy response
- Read Aloud
- retry
- per-message sources
- existing Memory view (single sidebar entry)
- original welcome screen
- proper composer sizing
- responsive behavior

## Backend alignment

- memory retrieval supports `include_always_relevant`
- conversation listing works
- New Chat creates a real persisted conversation
- conversation rename/delete works
- active conversation state is cleared on deletion
- current chat/research/provider logic is preserved from the current chat-service snapshot

## Safety

The included `APPLY_RECOVERY.ps1` creates a timestamped backup of every file it replaces before copying anything.
It does **not** touch `.env` or the database.

## Start commands

Backend:

```powershell
uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```powershell
npm run dev
```



