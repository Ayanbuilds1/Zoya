import { Fragment, useEffect, useMemo, useRef, useState } from "react";

import ReactMarkdown from "react-markdown";

import remarkGfm from "remark-gfm";

import rehypeRaw from "rehype-raw";

import MemoryCategoryFilter from "./components/MemoryCategoryFilter";

import MemoryCreateForm from "./components/MemoryCreateForm";

import MemoryEditModal from "./components/MemoryEditModal";

import MemoryList from "./components/MemoryList";

import { useMemory } from "./hooks/useMemory";

import "./App.css";

const API_BASE_URL = "http://127.0.0.1:8000";

const MAX_MESSAGE_LENGTH = 12000;

const createInitialResearchState = () => ({

  visible: false,

  active: false,

  completed: false,

  status: "",

  detail: "",

  currentQuery: "",

  sources: [],

  totalSources: 0,

  searchCount: 0,

  workedSeconds: null,

  sourcesExpanded: false,

});

const normalizeCitationUrl = (url) => {

  try {

      return new URL(url).toString().replace(/\/$/, "");

  } catch {

    return String(url || "").replace(/\/$/, "");

  }

};

const getCitationLabel = (source, href) => {

  if (source?.title) {

    const title = source.title

      .replace(/\s+\|\s+.*$/, "")

      .replace(/\s+-\s+.*$/, "")

      .trim();

    if (title.length <= 28) {

      return title;

    }

  }

  try {

    return new URL(href).hostname.replace(

      /^www\./,

      ""

    );

  } catch {

    return "Source";

  }

};

const getCitationDomain = (source, href) => {

  if (source?.domain) {

    return source.domain.replace(

      /^www\./,

      ""

    );

  }

  try {

    return new URL(href).hostname.replace(

      /^www\./,

      ""

    );

  } catch {

    return "";

  }

};

function CitationLink({

  href,

  children,

  sources,

  isOpen,

  onToggle,

}) {

  const matchedSource = sources.find(

    (source) =>

      normalizeCitationUrl(source.url) ===

      normalizeCitationUrl(href)

  );

  const label = getCitationLabel(

    matchedSource,

    href

  );

  const domain = getCitationDomain(

    matchedSource,

    href

  );

  return (

    <span className="citation-wrap">

      <button

        type="button"

        className={`citation-chip ${

          isOpen ? "open" : ""

        }`}

        onClick={(event) => {

          event.preventDefault();

          onToggle(href);

        }}

        aria-expanded={isOpen}

      >

        <span className="citation-chip-dot">

          {label.charAt(0).toUpperCase()}

        </span>

        <span className="citation-chip-label">

          {children || label}

        </span>

        <span className="citation-chip-chevron">

          {isOpen ? "⌃" : "⌄"}

        </span>

      </button>

      {isOpen && (

        <span className="citation-popover">

          <span className="citation-popover-title">

            {matchedSource?.title ||

              label}

          </span>

          {domain && (

            <span className="citation-popover-domain">

              {domain}

            </span>

          )}

          <a

            href={href}

            target="_blank"

            rel="noopener noreferrer"

            className="citation-popover-open"

          >

            Open source

            <span>↗</span>

          </a>

        </span>

      )}

    </span>

  );

}

/*

 * Converts malformed/raw research URLs into clean Markdown links.

 *

 * Example:

 * [https://news.microsoft.com/example]

 *

 * becomes:

 * [news.microsoft.com](https://news.microsoft.com/example)

 *

 * It also converts standalone raw URLs into clean clickable

 * domain links.

 */

const normalizeResearchMarkdown = (content) => {

  if (!content) {

    return "";

  }

  let normalized = content;

  normalized = normalized.replace(

    /\[(https?:\/\/[^\]\s]+)\]/g,

    (_, rawUrl) => {

      try {

        const url = rawUrl.replace(

          /[.,;:)]+$/,

          ""

        );

        const domain =

          new URL(url).hostname

            .replace(/^www\./, "");

        return `[${domain}](${url})`;

      } catch {

        return rawUrl;

      }

    }

  );

  normalized = normalized.replace(

    /(?<!\()https?:\/\/[^\s<>)\]]+/g,

    (rawUrl) => {

      try {

        const url = rawUrl.replace(

          /[.,;:)]+$/,

          ""

        );

        const domain =

          new URL(url).hostname

            .replace(/^www\./, "");

        return `[${domain}](${url})`;

      } catch {

        return rawUrl;

      }

    }

  );

  return normalized;

};

function App() {

  const [messages, setMessages] = useState([]);

  const [input, setInput] = useState("");

  const [isStreaming, setIsStreaming] =

    useState(false);

  const [conversationId, setConversationId] =

    useState(null);

  const [isLoadingHistory, setIsLoadingHistory] =

    useState(true);

  const [errorMessage, setErrorMessage] =

    useState("");

  const [activeView, setActiveView] =

    useState("chat");

  const [conversations, setConversations] =
    useState([]);

  const [isLoadingConversations, setIsLoadingConversations] =
    useState(true);

  const [isSidebarOpen, setIsSidebarOpen] =
    useState(false);

  const [isSidebarCollapsed, setIsSidebarCollapsed] =
    useState(false);

  const [chatSearch, setChatSearch] =
    useState("");

  const [pinnedConversationIds, setPinnedConversationIds] =
    useState(() => {
      try {
        const stored = window.localStorage.getItem("zoya:pinned-conversations");
        const parsed = stored ? JSON.parse(stored) : [];
        return Array.isArray(parsed) ? parsed.map(Number) : [];
      } catch {
        return [];
      }
    });

  const [openSourcesMessageIndex, setOpenSourcesMessageIndex] =
    useState(null);

  const [readingMessageIndex, setReadingMessageIndex] =
    useState(null);

  const [editingMessageIndex, setEditingMessageIndex] =
    useState(null);

  const [isNearBottom, setIsNearBottom] =
    useState(true);

  const [openConversationMenu, setOpenConversationMenu] =
    useState(null);

  const [editingConversation, setEditingConversation] =
    useState(null);

  const [conversationNameDraft, setConversationNameDraft] =
    useState("");

  const [isSavingConversationName, setIsSavingConversationName] =
    useState(false);

  const [conversationActionError, setConversationActionError] =
    useState("");

  const [isStartingNewChat, setIsStartingNewChat] =
    useState(false);

  const [selectedCategory, setSelectedCategory] =

    useState("");

  const [editingMemory, setEditingMemory] =

    useState(null);

  const [showCreateForm, setShowCreateForm] =

    useState(false);

  const [memoryActionError, setMemoryActionError] =

    useState("");

  const [researchState, setResearchState] =

    useState(

      createInitialResearchState()

    );

  const [copiedMessageIndex, setCopiedMessageIndex] =

    useState(null);

  const [openCitationUrl, setOpenCitationUrl] =

    useState(null);

  const messagesEndRef = useRef(null);

  const chatContainerRef = useRef(null);

  const textareaRef = useRef(null);

  const abortControllerRef = useRef(null);

  const researchSourcesRef = useRef([]);

  const stopRequestedRef = useRef(false);

  const selectionAutoScrollRef = useRef(null);

  const selectionPointerRef = useRef({ clientY: 0 });

  const isNearBottomRef = useRef(true);

  const {

    memories,

    categories,

    isLoading: isLoadingMemories,

    error: memoryError,

    createMemory,

    updateMemory,

    deleteMemory,

    refreshMemories,

  } = useMemory(selectedCategory);

  const remainingCharacters =

    MAX_MESSAGE_LENGTH - input.length;

  const isMessageTooLong =

    input.length > MAX_MESSAGE_LENGTH;

  const canSend =

    input.trim().length > 0 &&

    !isMessageTooLong &&

    !isStreaming &&

    !isLoadingHistory;

  useEffect(() => {

    loadConversations();
    loadHistory();

    return () => {
      abortControllerRef.current?.abort();
      stopSelectionAutoScroll();
    };

  }, []);

  useEffect(() => {

    if (!messagesEndRef.current || !isNearBottomRef.current) {
      return;
    }

    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({
        behavior: isStreaming ? "auto" : "smooth",
        block: "end",
      });
    });

  }, [messages, isStreaming, researchState.active, researchState.completed]);

  useEffect(() => {

    const closeMenu = () => {
      setOpenConversationMenu(null);
    };

    document.addEventListener("click", closeMenu);
    return () => document.removeEventListener("click", closeMenu);

  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        "zoya:pinned-conversations",
        JSON.stringify(pinnedConversationIds)
      );
    } catch {
      // Ignore storage failures.
    }
  }, [pinnedConversationIds]);

  useEffect(() => {

    if (

      activeView === "chat" &&

      !isStreaming &&

      !isLoadingHistory

    ) {

      textareaRef.current?.focus();

    }

  }, [

    activeView,

    isStreaming,

    isLoadingHistory,

  ]);

  const formatTime = (timestamp) => {

    if (!timestamp) {

      return "";

    }

    const date =

      new Date(timestamp);

    if (

      Number.isNaN(

        date.getTime()

      )

    ) {

      return "";

    }

    return date.toLocaleTimeString(

      [],

      {

        hour: "2-digit",

        minute: "2-digit",

      }

    );

  };

  const formatWorkedTime = (

    seconds

  ) => {

    if (

      seconds === null ||

      seconds === undefined

    ) {

      return "";

    }

    const rounded = Math.max(

      0,

      Math.round(

        Number(seconds)

      )

    );

    if (rounded < 60) {

      return `${rounded}s`;

    }

    const minutes =

      Math.floor(

        rounded / 60

      );

    const remainingSeconds =

      rounded % 60;

    return `${minutes}m ${remainingSeconds}s`;

  };

  const formatConversationDate = (timestamp) => {

    if (!timestamp) {
      return "";
    }

    const date = new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
      return "";
    }

    const now = new Date();

    if (date.toDateString() === now.toDateString()) {
      return date.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
    }

    return date.toLocaleDateString([], {
      day: "numeric",
      month: "short",
    });

  };

  const handleChatScroll = () => {
    const container = chatContainerRef.current;
    if (!container) {
      return;
    }
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    const nearBottom = distanceFromBottom < 96;
    isNearBottomRef.current = nearBottom;
    setIsNearBottom(nearBottom);
  };

  const scrollToLatest = () => {
    isNearBottomRef.current = true;
    setIsNearBottom(true);
    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    });
  };

  const togglePinnedConversation = (conversationIdToToggle) => {
    setPinnedConversationIds((previous) =>
      previous.includes(conversationIdToToggle)
        ? previous.filter((id) => id !== conversationIdToToggle)
        : [...previous, conversationIdToToggle]
    );
    setOpenConversationMenu(null);
  };

  const filteredConversations = useMemo(() => {
    const query = chatSearch.trim().toLowerCase();
    const visible = query
      ? conversations.filter((conversation) =>
          String(conversation.title || "").toLowerCase().includes(query)
        )
      : conversations;
    return [...visible].sort((a, b) => {
      const aPinned = pinnedConversationIds.includes(a.conversation_id);
      const bPinned = pinnedConversationIds.includes(b.conversation_id);
      if (aPinned !== bPinned) return Number(bPinned) - Number(aPinned);
      return 0;
    });
  }, [conversations, chatSearch, pinnedConversationIds]);

  const cleanDisplayedContent = (content) => {
    if (!content) return "";
    return content
      .replace(/\n+\*\*Sources?:\*\*\s*\n(?:\s*[-*]\s+.*\n?)+/gi, "\n")
      .trim();
  };

  const getMessageSources = (message) =>
    Array.isArray(message?.sources) ? message.sources : [];

  const speakMessage = (message, index) => {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(
      cleanDisplayedContent(message.content)
        .replace(/```[\s\S]*?```/g, "")
        .replace(/[#*_`>]/g, " ")
        .replace(/\s+/g, " ")
        .trim()
    );
    utterance.onstart = () => setReadingMessageIndex(index);
    utterance.onend = () => setReadingMessageIndex(null);
    utterance.onerror = () => setReadingMessageIndex(null);
    window.speechSynthesis.speak(utterance);
  };

  const stopReadingMessage = () => {
    window.speechSynthesis?.cancel();
    setReadingMessageIndex(null);
  };

  const handleConversationMenuToggle = (event, conversationIdToToggle) => {

    event.stopPropagation();

    setConversationActionError("");

    setOpenConversationMenu((previous) =>
      previous === conversationIdToToggle
        ? null
        : conversationIdToToggle
    );

  };

  const beginRenameConversation = (conversation) => {

    setOpenConversationMenu(null);
    setConversationActionError("");
    setEditingConversation(conversation.conversation_id);
    setConversationNameDraft(conversation.title || "");

  };

  const saveConversationName = async () => {

    const title = conversationNameDraft.trim();

    if (!editingConversation || !title || isSavingConversationName) {
      return;
    }

    setIsSavingConversationName(true);
    setConversationActionError("");

    try {

      const response = await fetch(
        `${API_BASE_URL}/api/chat/conversations/${editingConversation}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            user_id: 1,
            title,
          }),
        }
      );

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(
          data?.detail || "Unable to rename conversation."
        );
      }

      await loadConversations();
      setEditingConversation(null);
      setConversationNameDraft("");

    } catch (error) {

      setConversationActionError(
        error instanceof Error
          ? error.message
          : "Unable to rename conversation."
      );

    } finally {

      setIsSavingConversationName(false);

    }

  };

  const deleteConversation = async (conversation) => {

    setOpenConversationMenu(null);
    setConversationActionError("");

    const confirmed = window.confirm(
      `Delete \"${conversation.title}\"? This conversation will be permanently removed.`
    );

    if (!confirmed) {
      return;
    }

    try {

      const response = await fetch(
        `${API_BASE_URL}/api/chat/conversations/${conversation.conversation_id}?user_id=1`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(
          data?.detail || "Unable to delete conversation."
        );
      }

      if (conversation.conversation_id === conversationId) {
        setConversationId(null);
        setMessages([]);
        setInput("");
        resetResearchState();
        setOpenCitationUrl(null);
        setOpenSourcesMessageIndex(null);
        setCopiedMessageIndex(null);
      }
      setPinnedConversationIds((previous) =>
        previous.filter((id) => id !== conversation.conversation_id)
      );

      await loadConversations();

    } catch (error) {

      setConversationActionError(
        error instanceof Error
          ? error.message
          : "Unable to delete conversation."
      );

    }

  };

  const startRenameFromKey = (event, conversation) => {

    if (event.key === "Enter" || event.key === "F2") {
      event.preventDefault();
      event.stopPropagation();
      beginRenameConversation(conversation);
    }

  };

  const handleSelectionMouseMove = (event) => {

    const selection = window.getSelection();

    if (!selection || selection.isCollapsed) {
      return;
    }

    selectionPointerRef.current.clientY = event.clientY;

    if (selectionAutoScrollRef.current) {
      return;
    }

    selectionAutoScrollRef.current = window.setInterval(() => {
      const container = chatContainerRef.current;

      if (!container) {
        return;
      }

      const y = selectionPointerRef.current.clientY;
      const rect = container.getBoundingClientRect();
      const edge = 72;

      if (y < rect.top + edge) {
        const distance = rect.top + edge - y;
        container.scrollTop -= Math.min(28, 7 + distance * 0.18);
      } else if (y > rect.bottom - edge) {
        const distance = y - (rect.bottom - edge);
        container.scrollTop += Math.min(28, 7 + distance * 0.18);
      }
    }, 16);

  };

  const stopSelectionAutoScroll = () => {

    if (selectionAutoScrollRef.current) {
      window.clearInterval(selectionAutoScrollRef.current);
      selectionAutoScrollRef.current = null;
    }

  };

  const loadConversations = async () => {

    setIsLoadingConversations(true);

    try {

      const response = await fetch(
        `${API_BASE_URL}/api/chat/conversations?user_id=1`
      );

      if (!response.ok) {
        throw new Error("Conversation list load failed.");
      }

      const data = await response.json();
      const items = Array.isArray(data)
        ? data
        : data.conversations || [];

      setConversations(
        items.map((item) => ({
          conversation_id: item.conversation_id,
          title: item.title || "New conversation",
          started_at: item.started_at || null,
          message_count: item.message_count || 0,
          summary: item.summary || "",
        }))
      );

    } catch (error) {

      console.warn("Conversation list unavailable:", error);
      setConversations([]);

    } finally {

      setIsLoadingConversations(false);

    }

  };

  const loadHistory = async (requestedConversationId = null) => {

    setIsLoadingHistory(true);

    try {

      const query = new URLSearchParams({ user_id: "1" });

      if (
        requestedConversationId !== null &&
        requestedConversationId !== undefined
      ) {
        query.set(
          "conversation_id",
          String(requestedConversationId)
        );
      }

      const response = await fetch(
        `${API_BASE_URL}/api/chat/history?${query.toString()}`
      );

      if (!response.ok) {
        throw new Error("History load failed.");
      }

      const data = await response.json();

      setConversationId(
        data.conversation_id ?? requestedConversationId ?? null
      );

      setMessages(
        (data.messages || []).map((message) => ({
          role: message.role,
          content: message.content,
          timestamp:
            message.timestamp ||
            message.created_at ||
            new Date().toISOString(),
          sources: Array.isArray(message.sources) ? message.sources : [],
          status: message.status || undefined,
        }))
      );
      isNearBottomRef.current = true;
      setIsNearBottom(true);

    } catch (error) {

      console.error("History loading error:", error);

      if (requestedConversationId !== null) {
        setMessages([]);
      }

    } finally {

      setIsLoadingHistory(false);

    }

  };

  const selectConversation = async (id) => {

    if (isStreaming || id === conversationId) {
      return;
    }

    setActiveView("chat");
    setIsSidebarOpen(false);
    setIsStartingNewChat(false);
    setErrorMessage("");
    resetResearchState();
    setOpenCitationUrl(null);
    setOpenSourcesMessageIndex(null);
    setCopiedMessageIndex(null);
    setEditingMessageIndex(null);
    isNearBottomRef.current = true;
    setIsNearBottom(true);

    await loadHistory(id);

  };

  const startNewChat = async () => {

    if (isStreaming || isStartingNewChat) {
      return;
    }

    setIsStartingNewChat(true);
    setErrorMessage("");
    setActiveView("chat");
    setIsSidebarOpen(false);
    resetResearchState();
    setOpenCitationUrl(null);
    setOpenSourcesMessageIndex(null);
    setCopiedMessageIndex(null);
    setEditingMessageIndex(null);
    isNearBottomRef.current = true;
    setIsNearBottom(true);

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/chat/conversations?user_id=1`,
        { method: "POST" }
      );

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(
          data?.detail || "Unable to create a new chat."
        );
      }

      const data = await response.json();
      const newConversationId = data?.conversation_id ?? null;

      setConversationId(newConversationId);
      setMessages([]);
      setInput("");
      await loadConversations();

      requestAnimationFrame(() => {
        textareaRef.current?.focus();
      });
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Unable to create a new chat."
      );
    } finally {
      setIsStartingNewChat(false);
    }

  };

  const resetResearchState =

    () => {

      setResearchState(

        createInitialResearchState()

      );

    };

  const appendAssistantText = (

    text

  ) => {

    setMessages((previous) => {

      const lastMessage =

        previous[

          previous.length - 1

        ];

      if (

        lastMessage?.role ===

          "assistant" &&

        lastMessage.streaming

      ) {

        return [

          ...previous.slice(

            0,

            -1

          ),

          {

            ...lastMessage,

            content:

              lastMessage.content +

              text,

          },

        ];

      }

      return [

        ...previous,

        {

          role: "assistant",

          content: text,

          timestamp:

            new Date().toISOString(),

          streaming: true,

        },

      ];

    });

  };

  const finishAssistantMessage =

    () => {

      setMessages((previous) => {

        const lastMessage =

          previous[

            previous.length - 1

          ];

        if (

          lastMessage?.role !==

          "assistant"

        ) {

          return previous;

        }

        const {

          streaming,

          ...cleanMessage

        } = lastMessage;

        return [

          ...previous.slice(

            0,

            -1

          ),

          cleanMessage,

        ];

      });

    };

  const handleResearchStart =

    () => {

      setResearchState({

        visible: true,

        active: true,

        completed: false,

        status:

          "Searching the web...",

        detail:

          "Finding current information",

        currentQuery: "",

        sources: [],

        totalSources: 0,

        searchCount: 0,

        workedSeconds: null,

        sourcesExpanded: false,

      });

    };

  const handleResearchQuery = (

    data

  ) => {

    setResearchState(

      (previous) => ({

        ...previous,

        visible: true,

        active: true,

        completed: false,

        status:

          "Searching the web...",

        detail:

          "Finding current information",

        currentQuery:

          data.query || "",

        searchCount:

          previous.searchCount +

          1,

      })

    );

  };

  const handleResearchAnalyzing =

    (data) => {

      const stateMap = {

        evaluating: {

          status:

            "Refining research...",

          detail:

            "Reviewing relevant sources",

        },

        continuing: {

          status:

            "Searching for more evidence...",

          detail:

            "Looking for additional relevant information",

        },

        stopping: {

          status:

            "Research complete",

          detail:

            "Preparing the answer",

        },

        provider_error: {

          status:

            "Continuing research...",

          detail:

            "One search route was unavailable",

        },

      };

      const nextState =

        stateMap[

          data.status

        ] ||

        stateMap.evaluating;

      setResearchState(

        (previous) => ({

          ...previous,

          visible: true,

          active: true,

          ...nextState,

        })

      );

    };

  const handleResearchSource =

    (data) => {

      if (!data.url) {

        return;

      }

      setResearchState(

        (previous) => {

          const exists =

            previous.sources.some(

              (source) =>

                source.url ===

                data.url

            );

          if (exists) {

            return previous;

          }

          const nextSources = [

            ...previous.sources,

            {

              title:

                data.title ||

                "Untitled source",

              url: data.url,

              domain:

                data.domain ||

                "",

              snippet:

                data.snippet ||

                "",

            },

          ];

          return {

            ...previous,

            visible: true,

            sources:

              nextSources,

            totalSources:

              nextSources.length,

          };

        }

      );

    };

  const handleResearchComplete =

    (data) => {

      setResearchState(

        (previous) => ({

          ...previous,

          visible: true,

          active: false,

          completed: true,

          totalSources:

            data.total_sources ??

            previous.sources.length,

          status: "",

          detail: "",

        })

      );

    };

  const handleResearchError =

    (data) => {

      setResearchState(

        (previous) => ({

          ...previous,

          visible: true,

          active: false,

          completed: false,

          status:

            "Web research was unavailable",

          detail:

            data.message ||

            "Continuing without web research.",

        })

      );

    };

  const handleServerEvent = (

    event

  ) => {

    const lines =

      event.split(/\r?\n/);

    let eventName = "";

    let dataText = "";

    for (const line of lines) {

      if (

        line.startsWith(

          "event:"

        )

      ) {

        eventName =

          line

            .slice(6)

            .trim();

      }

      if (

        line.startsWith(

          "data:"

        )

      ) {

        dataText += line

          .slice(5)

          .trim();

      }

    }

    if (!dataText) {

      return;

    }

    let data;

    try {

      data =

        JSON.parse(

          dataText

        );

    } catch {

      return;

    }

    if (

      eventName ===

      "metadata"

    ) {

      if (

        data.conversation_id !==

          null &&

        data.conversation_id !==

          undefined

      ) {

        setConversationId(

          data.conversation_id

        );

      }

      return;

    }

    if (

      eventName ===

      "research_start"

    ) {

      handleResearchStart();

      return;

    }

    if (

      eventName ===

      "research_query"

    ) {

      handleResearchQuery(

        data

      );

      return;

    }

    if (

      eventName ===

      "research_sources"

    ) {

      handleResearchSource(

        data

      );

      return;

    }

    if (

      eventName ===

      "research_analyzing"

    ) {

      handleResearchAnalyzing(

        data

      );

      return;

    }

    if (

      eventName ===

      "research_complete"

    ) {

      handleResearchComplete(

        data

      );

      return;

    }

    if (

      eventName ===

      "research_error"

    ) {

      handleResearchError(

        data

      );

      return;

    }

    if (

      eventName ===

      "chunk"

    ) {

      const content =

        data.content ||

        "";

      if (content) {

        /*

         * Research progress disappears immediately

         * when Zoya's actual answer starts streaming.

         */

        setResearchState(

          (previous) => ({

            ...previous,

            active: false,

          })

        );

        appendAssistantText(

          content

        );

      }

      return;

    }

    if (

      eventName ===

      "done"

    ) {

      finishAssistantMessage();

      if (

        data.conversation_id !== undefined &&

        data.conversation_id !== null

      ) {

        setConversationId(data.conversation_id);

      }

      if (

        data.research

      ) {

        setResearchState(

          (previous) => ({

            ...previous,

            visible: true,

            active: false,

            completed: true,

            totalSources:

              data.research

                .total_sources ??

              previous.totalSources,

            searchCount:

              data.research

                .search_count ??

              previous.searchCount,

            workedSeconds:

              data.research

                .research_duration ??

              previous.workedSeconds,

          })

        );

      }

      return "done";

    }

    if (

      eventName ===

      "error"

    ) {

      throw new Error(

        data.message ||

          "Zoya AI service is temporarily unavailable."

      );

    }

  };

  const copyMessage = async (message, index) => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopiedMessageIndex(index);
      window.setTimeout(() => setCopiedMessageIndex(null), 1600);
    } catch (error) {
      console.error("Copy failed:", error);
    }
  };

  const beginEditMessage = (index) => {
    const message = messages[index];
    if (!message || message.role !== "user" || isStreaming) return;
    setEditingMessageIndex(index);
    setInput(message.content || "");
    setOpenSourcesMessageIndex(null);
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const cancelEditMessage = () => {
    setEditingMessageIndex(null);
    setInput("");
  };

  const toggleSourcesForMessage = (index) => {
    setOpenSourcesMessageIndex((previous) => previous === index ? null : index);
  };

  const retryAssistantMessage = async (index) => {
    if (isStreaming) return;
    const previousUser = messages
      .slice(0, index)
      .reverse()
      .find((message) => message.role === "user");
    if (!previousUser) return;

    setMessages((previous) => previous.filter((_, messageIndex) => messageIndex !== index));
    setOpenSourcesMessageIndex(null);
    await streamMessage(previousUser.content, { appendUserMessage: false, clearError: true });
  };

    const toggleCitation = (url) => {

  setOpenCitationUrl((previous) =>

    previous === url ? null : url

  );

};

  const toggleResearchSources =

    () => {

      setResearchState(

        (previous) => ({

          ...previous,

          sourcesExpanded:

            !previous.sourcesExpanded,

        })

      );

    };

  const stopMessage = () => {
    if (!isStreaming) return;
    stopRequestedRef.current = true;
    abortControllerRef.current?.abort();
    setMessages((previous) => {
      const last = previous[previous.length - 1];
      if (last?.role !== "assistant") return previous;
      return [
        ...previous.slice(0, -1),
        { ...last, streaming: false, status: "stopped" },
      ];
    });
    setIsStreaming(false);
    setResearchState((previous) => ({
      ...previous,
      active: false,
      status: "Generation stopped",
      detail: "You stopped the response.",
    }));
  };

  const streamMessage = async (message, options = {}) => {
    const { appendUserMessage = true, clearError = true } = options;
    if (!message?.trim() || isStreaming) return;

    if (clearError) setErrorMessage("");
    setInput("");
    setIsStreaming(true);
    resetResearchState();
    researchSourcesRef.current = [];
    stopRequestedRef.current = false;
    isNearBottomRef.current = true;
    setIsNearBottom(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    if (appendUserMessage) {
      setMessages((previous) => [
        ...previous,
        { role: "user", content: message, timestamp: new Date().toISOString() },
      ]);
    }

      try {

        const response = await fetch(
          `${API_BASE_URL}/api/chat/stream`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Accept: "text/event-stream",
            },
            signal: controller.signal,
            body: JSON.stringify({
              user_id: 1,
              user_name: "Ayan",
              message,
              conversation_id: conversationId,
              new_conversation: isStartingNewChat,
            }),
          }
        );

        if (!response.ok) {
          let errorMessage =
            "Zoya AI service is temporarily unavailable.";

          try {
            const errorData = await response.json();
            if (errorData?.detail) {
              if (Array.isArray(errorData.detail)) {
                errorMessage =
                  errorData.detail[0]?.msg || errorMessage;
              } else {
                errorMessage = errorData.detail;
              }
            }
          } catch {
            // Keep default.
          }

          throw new Error(errorMessage);
        }

        if (!response.body) {
          throw new Error(
            "Streaming response is not supported by this browser."
          );
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        let streamCompleted = false;

        while (!streamCompleted) {
          const { value, done } = await reader.read();

          if (done) {
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const events = buffer.split("\n\n");
          buffer = events.pop() || "";

          for (const event of events) {
            const result = handleServerEvent(event);
            if (result === "done") {
              streamCompleted = true;
              break;
            }
          }
        }

        buffer += decoder.decode();
        if (
          buffer.trim() &&
          !streamCompleted &&
          !stopRequestedRef.current
        ) {
          handleServerEvent(buffer);
        }

        finishAssistantMessage();

        try {
          await refreshMemories();
        } catch (error) {
          console.error(
            "Memory refresh after chat failed:",
            error
          );
        }

        await loadConversations();

      } catch (error) {

        const wasStopped =
          stopRequestedRef.current ||
          error?.name === "AbortError";

        if (wasStopped) {
          finishAssistantMessage();
        } else {
          const message =
            error instanceof Error
              ? error.message
              : "Something went wrong.";

          setErrorMessage(message);
          setResearchState(createInitialResearchState());
          setMessages((previous) => [
            ...previous,
            {
              role: "assistant",
              content: `Sorry Ayan, ${message}`,
              timestamp: new Date().toISOString(),
            },
          ]);
        }

      } finally {

        abortControllerRef.current = null;
        stopRequestedRef.current = false;
        setIsStartingNewChat(false);
        setIsStreaming(false);

      }

    };

  const sendMessage = async () => {
    const message = input.trim();
    if (!message) return;

    if (editingMessageIndex !== null) {
      const editIndex = editingMessageIndex;
      setEditingMessageIndex(null);
      setMessages((previous) => previous.slice(0, editIndex));
      await streamMessage(message, { appendUserMessage: true, clearError: true });
      return;
    }

    if (!canSend) return;
    await streamMessage(message, { appendUserMessage: true, clearError: true });
  };

  const handleInputChange =

    (event) => {

      setInput(

        event.target.value

      );

    };

  const handleKeyDown =

    (event) => {

      if (

        event.key ===

          "Enter" &&

        !event.shiftKey

      ) {

        event.preventDefault();

        sendMessage();

      }

    };

  const handleMemoryCreate =

    async (

      memoryData

    ) => {

      try {

        setMemoryActionError("");

        await createMemory(

          memoryData

        );

        setShowCreateForm(

          false

        );

      } catch (error) {

        const message =

          error instanceof Error

            ? error.message

            : "Unable to create memory.";

        setMemoryActionError(

          message

        );

        throw error;

      }

    };

  const handleMemoryUpdate =

    async (

      memoryId,

      memoryData

    ) => {

      try {

        setMemoryActionError("");

        await updateMemory(

          memoryId,

          memoryData

        );

        setEditingMemory(

          null

        );

      } catch (error) {

        const message =

          error instanceof Error

            ? error.message

            : "Unable to update memory.";

        setMemoryActionError(

          message

        );

        throw error;

      }

    };

  const handleMemoryDelete =

    async (

      memoryId

    ) => {

      try {

        setMemoryActionError("");

        await deleteMemory(

          memoryId

        );

      } catch (error) {

        const message =

          error instanceof Error

            ? error.message

            : "Unable to delete memory.";

        setMemoryActionError(

          message

        );

        throw error;

      }

    };

  const openMemoryView =

    () => {

      setActiveView(

        "memory"

      );
      setOpenConversationMenu(null);

      setErrorMessage("");

      setMemoryActionError("");

      setShowCreateForm(

        false

      );

      setEditingMemory(

        null

      );

    };

  const openChatView =

    () => {

      setActiveView(

        "chat"

      );
      setOpenConversationMenu(null);

      setMemoryActionError("");

    };

  const showWelcome =

    !isLoadingHistory &&

    messages.length === 0;

  const showResearchActivity =

    researchState.visible &&

    !researchState.completed &&

    Boolean(

      researchState.status

    ) &&

    researchState.active;

  return (

    <div className={`app ${isSidebarCollapsed ? "sidebar-collapsed" : ""}`}>

      <aside
        className={`sidebar ${isSidebarOpen ? "open" : ""}`}
        aria-label="Conversation sidebar"
      >
        <div className="sidebar-header">
          <button
            type="button"
            className="sidebar-brand"
            onClick={openChatView}
            aria-label="Open Zoya chat"
          >
            <span className="brand-avatar">Z</span>
            <span className="sidebar-brand-copy">
              <strong>Zoya</strong>
              <span>Personal AI</span>
            </span>
          </button>
          <button
            type="button"
            className="sidebar-close"
            onClick={() => setIsSidebarOpen(false)}
            aria-label="Close sidebar"
          >
            ×
          </button>
          <button
            type="button"
            className="sidebar-collapse-button"
            onClick={() => setIsSidebarCollapsed((previous) => !previous)}
            aria-label="Collapse sidebar"
          >
            ‹
          </button>
        </div>

        <button
          type="button"
          className="new-chat-button"
          onClick={startNewChat}
          disabled={isStreaming}
        >
          <span className="new-chat-icon">+</span>
          <span>New chat</span>
        </button>

        <div className="sidebar-search-wrap">
          <span className="sidebar-search-icon">⌕</span>
          <input
            value={chatSearch}
            onChange={(event) => setChatSearch(event.target.value)}
            placeholder="Search chats"
            aria-label="Search chats"
          />
          {chatSearch && (
            <button
              type="button"
              className="sidebar-search-clear"
              onClick={() => setChatSearch("")}
              aria-label="Clear chat search"
            >
              ×
            </button>
          )}
        </div>

        <div className="sidebar-section-title">
          <span>Chats</span>
          <span className="sidebar-count">{conversations.length}</span>
        </div>

        {conversationActionError && (
          <div className="conversation-action-error">
            {conversationActionError}
          </div>
        )}

        {editingConversation && (
          <div className="conversation-rename-panel">
            <div className="conversation-rename-label">Rename conversation</div>
            <input
              value={conversationNameDraft}
              onChange={(event) =>
                setConversationNameDraft(event.target.value)
              }
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  saveConversationName();
                }
                if (event.key === "Escape") {
                  setEditingConversation(null);
                  setConversationNameDraft("");
                }
              }}
              maxLength={80}
              autoFocus
              disabled={isSavingConversationName}
            />
            <div className="conversation-rename-actions">
              <button
                type="button"
                onClick={() => {
                  setEditingConversation(null);
                  setConversationNameDraft("");
                }}
                disabled={isSavingConversationName}
              >
                Cancel
              </button>
              <button
                type="button"
                className="primary"
                onClick={saveConversationName}
                disabled={
                  isSavingConversationName ||
                  !conversationNameDraft.trim()
                }
              >
                {isSavingConversationName ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        )}

        <div className="conversation-list">
          {isLoadingConversations ? (
            <div className="conversation-loading">
              <span className="conversation-skeleton" />
              <span className="conversation-skeleton short" />
              <span className="conversation-skeleton" />
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="conversation-empty">
              <span className="conversation-empty-icon">✦</span>
              <strong>No saved chats yet</strong>
              <span>Start a new conversation and it will appear here.</span>
            </div>
          ) : (
            filteredConversations.map((conversation, index) => {
              const isPinnedConversation = pinnedConversationIds.includes(
                conversation.conversation_id
              );
              const previousConversation = filteredConversations[index - 1];
              const previousWasPinned = previousConversation
                ? pinnedConversationIds.includes(
                    previousConversation.conversation_id
                  )
                : false;
              const showPinnedHeading =
                !chatSearch &&
                isPinnedConversation &&
                index === 0;
              const showChatsHeading =
                !chatSearch &&
                !isPinnedConversation &&
                (index === 0 || previousWasPinned);

              return (
                <Fragment key={conversation.conversation_id}>
                  {showPinnedHeading && (
                    <div className="conversation-section-heading">Pinned</div>
                  )}
                  {showChatsHeading && (
                    <div className="conversation-section-heading">Chats</div>
                  )}
                  <div
                    className={`conversation-item ${
                      conversation.conversation_id === conversationId
                        ? "active"
                        : ""
                    }`}
                    title={conversation.title}
              >
                <button
                  type="button"
                  className="conversation-item-main"
                  onClick={() =>
                    selectConversation(conversation.conversation_id)
                  }
                  onKeyDown={(event) =>
                    startRenameFromKey(event, conversation)
                  }
                  disabled={isStreaming}
                >
                  <span className="conversation-item-icon">{pinnedConversationIds.includes(conversation.conversation_id) ? "★" : "✦"}</span>
                  <span className="conversation-item-copy">
                    <span className="conversation-item-title">
                      {conversation.title}
                    </span>
                    <span className="conversation-item-meta">
                      {formatConversationDate(conversation.started_at)}
                    </span>
                  </span>
                </button>

                <button
                  type="button"
                  className="conversation-item-menu-trigger"
                  onClick={(event) =>
                    handleConversationMenuToggle(
                      event,
                      conversation.conversation_id
                    )
                  }
                  disabled={isStreaming}
                  aria-label={`Conversation actions for ${conversation.title}`}
                  aria-expanded={
                    openConversationMenu === conversation.conversation_id
                  }
                >
                  ⋯
                </button>

                {openConversationMenu === conversation.conversation_id && (
                  <div
                    className="conversation-item-menu"
                    onClick={(event) => event.stopPropagation()}
                  >
                    <button
                      type="button"
                      onClick={() => beginRenameConversation(conversation)}
                    >
                      Rename
                    </button>
                    <button
                      type="button"
                      onClick={() => togglePinnedConversation(conversation.conversation_id)}
                    >
                      {pinnedConversationIds.includes(conversation.conversation_id) ? "Unpin" : "Pin"}
                    </button>
                    <button
                      type="button"
                      className="danger"
                      onClick={() => deleteConversation(conversation)}
                    >
                      Delete
                    </button>
                  </div>
                )}
                  </div>
                </Fragment>
              );
            })
          )}
        </div>

        <div className="sidebar-footer">
          <button
            type="button"
            className={`sidebar-nav-button ${
              activeView === "chat" ? "active" : ""
            }`}
            onClick={openChatView}
          >
            <span>⌂</span> Chat
          </button>
          <button
            type="button"
            className={`sidebar-nav-button ${
              activeView === "memory" ? "active" : ""
            }`}
            onClick={openMemoryView}
          >
            <span>◈</span> Memory
          </button>
        </div>
      </aside>

      {isSidebarOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          onClick={() => setIsSidebarOpen(false)}
          aria-label="Close sidebar overlay"
        />
      )}

      <div className="app-main">
        <header className="topbar">
          <div className="topbar-left">
            <button
              type="button"
              className="sidebar-toggle"
              onClick={() => setIsSidebarOpen(true)}
              aria-label="Open sidebar"
            >
              ☰
            </button>
            <div className="topbar-title">
              <span>
                {activeView === "memory"
                  ? "Memory"
                  : conversations.find(
                      (conversation) =>
                        conversation.conversation_id === conversationId
                    )?.title || "New chat"}
              </span>
            </div>
          </div>
          <div className="topbar-right">
            <button
              type="button"
              className="topbar-sidebar-button"
              onClick={() => setIsSidebarCollapsed((previous) => !previous)}
              aria-label="Toggle sidebar"
            >
              {isSidebarCollapsed ? "›" : "‹"}
            </button>
          </div>
        </header>

      {activeView ===

      "chat" ? (

        <>

          <main
            className="chat-container"
            ref={chatContainerRef}
            onScroll={handleChatScroll}
            onMouseMove={handleSelectionMouseMove}
            onMouseUp={stopSelectionAutoScroll}
            onMouseLeave={stopSelectionAutoScroll}
          >

            {showWelcome && (

              <section className="welcome">

                <div className="welcome-avatar">

                  Z

                </div>

                <h2>

                  Hi Ayan 🖤

                </h2>

                <p>

                  Main Zoya hoon,

                  aapki personal AI

                  assistant.

                </p>

                <span>

                  Aap mujhse kuch bhi

                  pooch sakte hain.

                </span>

              </section>

            )}

            <section className="messages">

              {isLoadingHistory ? (

                <div className="history-loading">

                  <div className="loading-spinner"></div>

                  <span>

                    Loading conversation...

                  </span>

                </div>

              ) : (

                messages.map((message, index) => {
                  const sources = getMessageSources(message);
                  return (
                    <div
                      className={`message-row ${message.role}`}
                      key={`${message.role}-${index}`}
                    >
                      {message.role === "assistant" && (
                        <div className="message-avatar">Z</div>
                      )}
                      <div className="message-content">
                        <div className="message-meta">
                          <span className="message-name">
                            {message.role === "assistant" ? "Zoya" : "Ayan"}
                          </span>
                          {message.timestamp && (
                            <span className="message-time">{formatTime(message.timestamp)}</span>
                          )}
                        </div>
                        <div className={`message-bubble ${message.role === "assistant" ? "assistant-answer" : "user-answer"} ${message.status === "stopped" ? "message-stopped" : ""}`}>
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            rehypePlugins={[rehypeRaw]}
                            components={{
                              a: ({ href, children }) => (
                                <CitationLink
                                  href={href}
                                  children={children}
                                  sources={sources}
                                  isOpen={openCitationUrl === href}
                                  onToggle={toggleCitation}
                                />
                              ),
                            }}
                          >
                            {cleanDisplayedContent(message.content)}
                          </ReactMarkdown>
                          {message.streaming && <span className="streaming-cursor">▋</span>}
                          {message.status === "stopped" && !message.streaming && (
                            <div className="message-stopped-label">Generation stopped</div>
                          )}
                        </div>

                        {message.role === "user" && !message.streaming && (
                          <div className="message-actions user-message-actions">
                            <button
                              type="button"
                              className="message-action-button icon-only"
                              onClick={() => beginEditMessage(index)}
                              aria-label="Edit message"
                              title="Edit"
                              disabled={isStreaming}
                            >
                              ✎
                            </button>
                          </div>
                        )}

                        {message.role === "assistant" && !message.streaming && (
                          <div className="message-actions assistant-message-actions">
                            <button type="button" className="message-action-button icon-only" onClick={() => retryAssistantMessage(index)} aria-label="Retry response" title="Retry">↻</button>
                            <button type="button" className="message-action-button icon-only" onClick={() => copyMessage(message, index)} aria-label="Copy response" title={copiedMessageIndex === index ? "Copied" : "Copy"}>
                              {copiedMessageIndex === index ? "✓" : "⧉"}
                            </button>
                            <button
                              type="button"
                              className={`message-action-button icon-only ${readingMessageIndex === index ? "active" : ""}`}
                              onClick={() => readingMessageIndex === index ? stopReadingMessage() : speakMessage(message, index)}
                              aria-label={readingMessageIndex === index ? "Stop read aloud" : "Read aloud"}
                              title={readingMessageIndex === index ? "Stop" : "Read aloud"}
                            >
                              {readingMessageIndex === index ? "■" : "◖"}
                            </button>
                            {sources.length > 0 && (
                              <button
                                type="button"
                                className={`message-action-button icon-only ${openSourcesMessageIndex === index ? "active" : ""}`}
                                onClick={() => toggleSourcesForMessage(index)}
                                aria-label="View sources"
                                title="View sources"
                              >◉</button>
                            )}
                          </div>
                        )}

                        {message.role === "assistant" && openSourcesMessageIndex === index && sources.length > 0 && (
                          <div className="message-sources-panel">
                            <div className="message-sources-title">Sources</div>
                            {sources.map((source) => (
                              <a key={source.url} href={source.url} target="_blank" rel="noopener noreferrer" className="message-source-item">
                                <span className="message-source-main">
                                  <span className="message-source-dot">{(source.domain || source.title || "S").charAt(0).toUpperCase()}</span>
                                  <span><strong>{source.title || source.domain || "Source"}</strong>{source.domain && <small>{source.domain}</small>}</span>
                                </span>
                                <span className="message-source-arrow">↗</span>
                              </a>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                }))}

              {showResearchActivity && (

                <div className="research-activity">

                  <div className="research-activity-main">

                    <span className="research-spinner"></span>

                    <div>

                      <div className="research-activity-title">

                        {

                          researchState.status

                        }

                      </div>

                      <div className="research-activity-detail">

                        {

                          researchState.detail

                        }

                      </div>

                    </div>

                  </div>

                </div>

              )}

              {isStreaming &&

                messages[

                  messages.length -

                    1

                ]?.role ===

                  "user" &&

                !researchState.active && (

                  <div className="message-row assistant">

                    <div className="message-avatar">

                      Z

                    </div>

                    <div className="message-content">

                      <div className="message-meta">

                        <span className="message-name">

                          Zoya

                        </span>

                      </div>

                      <div className="message-bubble typing">

                        <span></span>

                        <span></span>

                        <span></span>

                      </div>

                    </div>

                  </div>

                )}

              <div

                ref={

                  messagesEndRef

                }

              />

            </section>

          </main>

          <footer className="composer-wrapper">

            {editingMessageIndex !== null && (
              <div className="composer-editing-bar">
                <span>Editing message</span>
                <button type="button" onClick={cancelEditMessage}>Cancel</button>
              </div>
            )}

            {errorMessage && (

              <div className="error-banner">

                <span>

                  ⚠️

                </span>

                <span>

                  {

                    errorMessage

                  }

                </span>

              </div>

            )}

            <div

              className={`composer ${

                isMessageTooLong

                  ? "composer-error"

                  : ""

              }`}

            >

              <textarea

                ref={

                  textareaRef

                }

                value={input}

                onChange={

                  handleInputChange

                }

                onKeyDown={

                  handleKeyDown

                }

                placeholder={
                  editingMessageIndex !== null
                    ? "Edit your message..."
                    : isStreaming
                      ? "Type your next message..."
                      : "Message Zoya..."
                }

                rows={1}

                maxLength={

                  MAX_MESSAGE_LENGTH

                }

                disabled={

                  isLoadingHistory

                }

              />

              <button

                type="button"

                className={
                  isStreaming
                    ? "composer-stop-button"
                    : ""
                }

                onClick={
                  isStreaming
                    ? stopMessage
                    : sendMessage
                }

                disabled={
                  isStreaming
                    ? false
                    : !canSend
                }

                aria-label={
                  isStreaming
                    ? "Stop response"
                    : "Send message"
                }

              >

                {isStreaming
                  ? "■"
                  : "↑"}

              </button>

            </div>

            <div

              className={`composer-hint ${

                isMessageTooLong

                  ? "limit-warning"

                  : ""

              }`}

            >

              {isMessageTooLong

                ? `Message is too long by ${Math.abs(

                    remainingCharacters

                  )} characters`

                : `${input.length.toLocaleString()} / ${MAX_MESSAGE_LENGTH.toLocaleString()} characters · Enter to send · Shift + Enter for new line`}

            </div>

          </footer>

        </>

      ) : (

        <main className="memory-container">

          <div className="memory-header">

            <div>

              <span className="memory-eyebrow">

                ZOYA MEMORY

              </span>

              <h2>

                What Zoya remembers

              </h2>

              <p>

                View, edit, add, or remove

                memories stored about you.

              </p>

            </div>

            <button

              type="button"

              className="memory-primary-button"

              onClick={() => {

                setMemoryActionError(

                  ""

                );

                setShowCreateForm(

                  (previous) =>

                    !previous

                );

                setEditingMemory(

                  null

                );

              }}

            >

              {showCreateForm

                ? "Close"

                : "+ Add Memory"}

            </button>

          </div>

          {(memoryError ||

            memoryActionError) && (

            <div className="memory-page-error">

              ⚠️{" "}

              {memoryActionError ||

                memoryError}

            </div>

          )}

          {showCreateForm && (

            <MemoryCreateForm

              onCreate={

                handleMemoryCreate

              }

              onCancel={() =>

                setShowCreateForm(

                  false

                )

              }

            />

          )}

          <section className="memory-toolbar">

            <div>

              <strong>

                {

                  memories.length

                }

              </strong>{" "}

              {memories.length ===

              1

                ? "memory"

                : "memories"}

            </div>

            <button

              type="button"

              className="memory-refresh-button"

              onClick={

                refreshMemories

              }

              disabled={

                isLoadingMemories

              }

            >

              {isLoadingMemories

                ? "Refreshing..."

                : "Refresh"}

            </button>

          </section>

          <MemoryCategoryFilter

            categories={

              categories

            }

            selectedCategory={

              selectedCategory

            }

            onCategoryChange={

              setSelectedCategory

            }

          />

          <MemoryList

            memories={

              memories

            }

            isLoading={

              isLoadingMemories

            }

            onEdit={

              setEditingMemory

            }

            onDelete={

              handleMemoryDelete

            }

          />

          <MemoryEditModal

            memory={

              editingMemory

            }

            onClose={() =>

              setEditingMemory(

                null

              )

            }

            onSave={

              handleMemoryUpdate

            }

          />

        </main>

      )}

        </div>
    </div>

  );

}

export default App;
