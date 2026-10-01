# Zoya Frontend — Dependency Map (Current Uploaded Baseline)

Source of truth inspected:
- `App.jsx` — 3,595 lines
- `App.css` — 4,295 lines
- `index.css` — 15 lines
- `main.jsx` — 10 lines

No code changes were made while creating this map.

## 1. Entry / global layer

`main.jsx`
- React `StrictMode`
- `createRoot(...)`
- imports `index.css`
- renders `App.jsx`

`index.css`
- root sizing
- html background
- body min-width

`App.css`
- complete application UI styling
- chat, sidebar, memory, research, responsive, accessibility, animations

## 2. App.jsx high-level responsibility

`App.jsx` currently owns:

1. Chat state
2. Conversation state
3. Sidebar state
4. Message editing / retry / copy / speech
5. History loading
6. New-chat lifecycle
7. Streaming transport and SSE-style parsing
8. Research progress state and handlers
9. Generated-image URL handling
10. Citation UI helpers
11. Memory page orchestration
12. Almost all page JSX rendering

## 3. State map — 30 useState values

### Chat / message state
- `messages`
- `input`
- `isStreaming`
- `conversationId`
- `isLoadingHistory`
- `errorMessage`
- `editingMessageIndex`
- `readingMessageIndex`
- `copiedMessageIndex`
- `openSourcesMessageIndex`
- `openCitationUrl`
- `isNearBottom`

### Conversation / sidebar state
- `conversations`
- `isLoadingConversations`
- `isSidebarOpen`
- `isSidebarCollapsed`
- `chatSearch`
- `pinnedConversationIds`
- `openConversationMenu`
- `editingConversation`
- `conversationNameDraft`
- `isSavingConversationName`
- `conversationActionError`
- `isStartingNewChat`
- `activeView`

### Memory state
- `selectedCategory`
- `editingMemory`
- `showCreateForm`
- `memoryActionError`

### Research state
- `researchState`

## 4. Ref map — 9 useRef values

- `messagesEndRef` — bottom-of-chat anchor
- `chatContainerRef` — chat scrolling / selection auto-scroll
- `textareaRef` — composer focus
- `abortControllerRef` — active stream cancellation
- `researchSourcesRef` — research-source runtime reference (currently only assigned, not consumed)
- `stopRequestedRef` — distinguishes user stop from other aborts
- `selectionAutoScrollRef` — selection auto-scroll interval
- `selectionPointerRef` — pointer Y position for selection auto-scroll
- `isNearBottomRef` — auto-scroll guard

## 5. Logic clusters

### A. Pure / presentation helpers
- `createInitialResearchState`
- `normalizeCitationUrl`
- `getCitationLabel`
- `getCitationDomain`
- `normalizeResearchMarkdown`
- `formatTime`
- `formatWorkedTime`
- `formatConversationDate`
- `cleanDisplayedContent`
- `getMessageSources`

`normalizeResearchMarkdown`, `formatWorkedTime`, and `scrollToLatest` currently appear to be definition-only/dead-code candidates and should be verified before deletion.

### B. Citation / markdown UI
- `CitationLink`
- `toggleCitation`
- ReactMarkdown + remarkGfm + rehypeRaw configuration

### C. Conversation API + lifecycle
- `saveConversationName`
- `deleteConversation`
- `loadConversations`
- `loadHistory`
- `selectConversation`
- `startNewChat`
- `beginRenameConversation`
- `startRenameFromKey`
- `togglePinnedConversation`
- `handleConversationMenuToggle`

### D. Chat viewport / selection
- `handleChatScroll`
- `scrollToLatest`
- `handleSelectionMouseMove`
- `stopSelectionAutoScroll`

### E. Streaming / message assembly
- `appendAssistantText`
- `finishAssistantMessage`
- `handleServerEvent`
- `streamMessage`
- `stopMessage`
- `sendMessage`
- `handleInputChange`
- `handleKeyDown`

### F. Research event handling
- `handleResearchStart`
- `handleResearchQuery`
- `handleResearchAnalyzing`
- `handleResearchSource`
- `handleResearchComplete`
- `handleResearchError`
- `toggleResearchSources`
- `resetResearchState`

### G. Message actions
- `copyMessage`
- `beginEditMessage`
- `cancelEditMessage`
- `retryAssistantMessage`
- `speakMessage`
- `stopReadingMessage`
- `toggleSourcesForMessage`

### H. Memory orchestration
- `handleMemoryCreate`
- `handleMemoryUpdate`
- `handleMemoryDelete`
- `openMemoryView`
- `openChatView`

## 6. API dependency map

All current network calls are directly inside `App.jsx`.

### Conversations
- `GET /api/chat/conversations?user_id=1`
- `POST /api/chat/conversations?user_id=1`
- `PATCH /api/chat/conversations/{conversation_id}`
- `DELETE /api/chat/conversations/{conversation_id}?user_id=1`

### History
- `GET /api/chat/history?user_id=1[&conversation_id=...]`

### Streaming chat
- `POST /api/chat/stream`
- request body includes `user_id`, `user_name`, `message`, `conversation_id`, `new_conversation`
- reads browser `ReadableStream`
- parses SSE-style `event:` + `data:` blocks

## 7. Stream event dependency map

`handleServerEvent` currently routes:

- `metadata` → `conversationId`
- `research_start` → research state
- `research_query` → research state
- `research_sources` → research sources
- `research_analyzing` → research state
- `research_complete` → research state
- `research_error` → research state
- `chunk` → assistant message streaming
- `image` → assistant image attachment
- `done` → finish message + conversation/research metadata
- `error` → thrown error

## 8. UI composition map

### Sidebar
- branding
- New Chat
- search chats
- rename panel
- conversation list
- pinned/chats grouping
- conversation action menu
- Chat / Memory navigation

### Top bar
- mobile sidebar toggle
- current view / conversation title

### Chat page
- welcome state
- message list
- assistant/user message bubbles
- markdown rendering
- citation chips/popovers
- generated image + download
- message actions
- source panel
- research activity
- typing state
- bottom anchor

### Composer
- edit-mode bar
- error banner
- textarea
- send/stop button
- character counter

### Memory page
- header + Add Memory
- page-level error
- create form
- toolbar + refresh
- category filter
- memory list
- edit modal

## 9. Existing child dependencies

`App.jsx` imports these local modules:

- `./components/MemoryCategoryFilter`
- `./components/MemoryCreateForm`
- `./components/MemoryEditModal`
- `./components/MemoryList`
- `./hooks/useMemory`

These were not uploaded in the current turn, so their exact internal dependencies were not treated as verified source-of-truth here.

## 10. CSS ownership map

Current `App.css` contains roughly 169 unique CSS class names / 667 class references, 19 media-query blocks and 16 keyframe blocks.

Major CSS domains:

- App shell
- top bar
- chat container
- welcome state
- message bubbles / markdown
- streaming / typing
- composer
- errors
- memory page
- memory list/items
- memory forms
- memory modal
- responsive rules
- accessibility rules
- research UI
- final response polish / later override blocks
- sidebar responsive behavior

Important: CSS should NOT be globally reorganized before JSX component boundaries are frozen.

## 11. Safe extraction order

### Phase 1 — no UI behavior change
Create API/service boundaries:
- `services/api.js`
- `services/conversationService.js`
- `services/chatService.js`

Move only request/response transport. Keep React state in `App.jsx`.

### Phase 2 — streaming transport
Extract:
- raw `fetch('/api/chat/stream')`
- reader/decoder loop
- SSE event parsing
- URL resolution

Keep state updates in hook/controller until tested.

### Phase 3 — conversation hook
Extract conversation lifecycle into `useConversations`.

Candidate state:
- conversations
- loading
- rename state
- menu state
- pin state
- search/filter

### Phase 4 — chat hook
Extract streaming/message lifecycle into `useChat`.

Candidate state:
- messages
- input
- streaming
- conversationId
- history loading
- abort controller
- stop state
- message actions

### Phase 5 — UI components
Split JSX only after behavior remains identical:
- `Sidebar`
- `TopBar`
- `ChatView`
- `MessageList`
- `MessageBubble`
- `Composer`
- `ResearchStatus`
- `CitationLink`

### Phase 6 — CSS split
Only after components are stable:
- `sidebar.css`
- `chat.css`
- `composer.css`
- `memory.css`
- `research.css`
- `responsive.css`

## 12. Things NOT to change yet

- React → HTML/CSS/JS migration
- WebSocket migration
- design rewrite
- dark-theme rewrite
- global CSS rewrite
- backend API contract changes
- removal of working memory components
- image rendering redesign
- build chunk optimization

## 13. Immediate technical findings

1. `App.jsx` is the real monolith, not the overall project.
2. `main.jsx` and `index.css` are already appropriately small.
3. `App.css` is large but structurally understandable enough to preserve during logic extraction.
4. Conversation, chat streaming, research, memory orchestration and rendering are tightly coupled in `App.jsx`.
5. The safest first architectural boundary is network/service extraction, not JSX surgery.
6. `researchSourcesRef` is currently assigned/reset but not meaningfully read.
7. Several helper functions appear definition-only and should be verified before cleanup.
8. The earlier generated `apply_frontend_step1.ps1` has NOT been applied as part of this map.
