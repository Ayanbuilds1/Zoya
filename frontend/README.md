# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and Oxlint's TypeScript related rules in your project.
# Zoya Frontend — Part 2

## Files

- `App.jsx` — updated app shell with responsive sidebar, conversation list, chat switching, New Chat, mobile drawer, and existing Memory/Research UI preserved.
- `App.css.part2.append.css` — append this file to the **bottom of your existing `frontend/src/App.css`**. It intentionally overrides the old shell/layout without replacing the existing Memory/Research/Markdown styles.
- `index.css` — replace `frontend/src/index.css` with this version.

## Apply

1. Replace `frontend/src/App.jsx` with `App.jsx`.
2. Append `App.css.part2.append.css` to the bottom of `frontend/src/App.css`.
3. Replace `frontend/src/index.css` with `index.css`.
4. Start the backend and frontend normally.

The sidebar requests:
`GET /api/chat/conversations?user_id=1`

The chat loader requests:
`GET /api/chat/history?user_id=1&conversation_id=<id>`

If the conversation-list endpoint is unavailable, the UI keeps working and simply shows no saved chats.
