import { Fragment, useEffect, useMemo, useRef, useState } from "react";

import ReactMarkdown from "react-markdown";

import remarkGfm from "remark-gfm";

import rehypeRaw from "rehype-raw";

import { API_BASE_URL } from "./services/api";
import { streamChat } from "./services/chatService";

import {
  createConversation,
  deleteConversation as deleteConversationRequest,
  getConversationHistory,
  listConversations,
  renameConversation,
} from "./services/conversationService";

import MemoryCategoryFilter from "./components/MemoryCategoryFilter";

import MemoryCreateForm from "./components/MemoryCreateForm";

import MemoryEditModal from "./components/MemoryEditModal";

import MemoryList from "./components/MemoryList";

import { useMemory } from "./hooks/useMemory";
import { useTheme } from "./hooks/useTheme";
import ThemeSwitcher from "./components/ThemeSwitcher";
import AiStatusIndicator from "./components/AiStatusIndicator";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";

import "./App.css";

const MAX_MESSAGE_LENGTH = 12000;

const getCodeBlockText = (children) => {
  const parts = [];

  const collect = (node) => {
    if (node == null) return;
    if (typeof node === "string" || typeof node === "number") {
      parts.push(String(node));
      return;
    }
    if (Array.isArray(node)) {
      node.forEach(collect);
      return;
    }
    if (node?.props?.children !== undefined) {
      collect(node.props.children);
    }
  };

  collect(children);
  return parts.join("").replace(/\n$/, "");
};

const CodeBlock = ({ children }) => {
  const [copied, setCopied] = useState(false);
  const codeText = getCodeBlockText(children);
  const languageClass = children?.props?.className || "";
  const language = languageClass.startsWith("language-")
    ? languageClass.replace("language-", "")
    : "code";

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(codeText);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="message-code-wrap">
      <div className="message-code-toolbar">
        <span className="message-code-language">{language}</span>
        <button
          type="button"
          className="message-code-copy"
          onClick={handleCopy}
          aria-label={copied ? "Code copied" : "Copy code"}
          title={copied ? "Copied" : "Copy code"}
        >
          {copied ? "✓ Copied" : "Copy"}
        </button>
      </div>
      <pre>{children}</pre>
    </div>
  );
};

const shouldShowThinkingForRequest = (message = "") => {
  const normalized = message.trim().toLowerCase();

  if (!normalized) {
    return false;
  }

  const explicitComplexity = [
    "research",
    "research karke",
    "research kar ke",
    "detail me",
    "detail mein",
    "detailed",
    "analyze",
    "analyse",
    "compare",
    "comparison",
    "latest",
    "current information",
    "deep dive",
    "step by step",
    "pros and cons",
    "advantages and disadvantages",
    "summarize",
    "summary",
  ];

  if (explicitComplexity.some((term) => normalized.includes(term))) {
    return true;
  }

  // Ordinary short conversational/factual requests should feel immediate.
  const wordCount = normalized.split(/\s+/).filter(Boolean).length;
  return wordCount >= 9;
};

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

const escapeRegExp = (value) =>
  String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const highlightConversationTitle = (title, query) => {
  const text = String(title || "");
  const needle = String(query || "").trim();

  if (!needle) {
    return <span>{text}</span>;
  }

  const parts = text.split(new RegExp(`(${escapeRegExp(needle)})`, "ig"));

  return parts.map((part, index) =>
    part.toLowerCase() === needle.toLowerCase() ? (
      <mark key={`${part}-${index}`} className="conversation-search-match">
        {part}
      </mark>
    ) : (
      <span key={`${part}-${index}`}>{part}</span>
    )
  );
};

function App() {

  const { theme, setTheme } = useTheme();

  const [messages, setMessages] = useState([]);

  const [input, setInput] = useState("");

  const [isStreaming, setIsStreaming] =

    useState(false);

  const [conversationId, setConversationId] =

    useState(null);

  const [isLoadingHistory, setIsLoadingHistory] =

    useState(true);

  const [switchingConversationId, setSwitchingConversationId] =

    useState(null);

  const [switchingConversationTitle, setSwitchingConversationTitle] =

    useState("");

  const [errorMessage, setErrorMessage] =

    useState("");

  const [activeView, setActiveView] =

    useState("chat");

  const [conversations, setConversations] =
    useState([]);

  const [conversationCount, setConversationCount] =
    useState(0);

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

  const [aiStatusVisible, setAiStatusVisible] =

    useState(false);

  const [copiedMessageIndex, setCopiedMessageIndex] =

    useState(null);

  const [openCitationUrl, setOpenCitationUrl] =

    useState(null);

  const messagesEndRef = useRef(null);

  const chatContainerRef = useRef(null);

  const textareaRef = useRef(null);

  const chatSearchInputRef = useRef(null);
  const conversationMenuFirstActionRef = useRef(null);
  const conversationMenuTriggerRefs = useRef(new Map());
  const lastConversationMenuIdRef = useRef(null);

  const abortControllerRef = useRef(null);

  const researchSourcesRef = useRef([]);

  const stopRequestedRef = useRef(false);

  const selectionAutoScrollRef = useRef(null);

  const selectionPointerRef = useRef({ clientY: 0 });

  const isNearBottomRef = useRef(true);

  const conversationScrollPositionsRef = useRef(new Map());

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

    try {
      const stored = window.sessionStorage.getItem("zoya:conversation-scroll");
      const parsed = stored ? JSON.parse(stored) : {};
      if (parsed && typeof parsed === "object") {
        Object.entries(parsed).forEach(([id, value]) => {
          const numericId = Number(id);
          const numericValue = Number(value);
          if (Number.isFinite(numericId) && Number.isFinite(numericValue)) {
            conversationScrollPositionsRef.current.set(numericId, numericValue);
          }
        });
      }
    } catch {
      // Ignore session storage failures.
    }

    loadConversations();
    loadHistory();

    return () => {
      abortControllerRef.current?.abort();
      stopSelectionAutoScroll();
    };

  }, []);

  useEffect(() => {
    const conversationTitle =
      conversations.find(
        (conversation) => conversation.conversation_id === conversationId
      )?.title;

    if (isStreaming) {
      document.title = researchState.active
        ? "Zoya — Researching…"
        : "Zoya — Responding…";
      return;
    }

    if (activeView === "memory") {
      document.title = "Zoya — Memory";
      return;
    }

    document.title = conversationTitle
      ? `Zoya — ${conversationTitle}`
      : "Zoya";
  }, [
    activeView,
    conversationId,
    conversations,
    isStreaming,
    researchState.active,
  ]);

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
    let timeoutId;

    if (!isStreaming) {
      setAiStatusVisible(false);
      return undefined;
    }

    const latestMessage = messages[messages.length - 1];

    if (latestMessage?.role === "assistant") {
      setAiStatusVisible(false);
      return undefined;
    }

    if (researchState.active) {
      setAiStatusVisible(true);
      return undefined;
    }

    const latestUserMessage = [...messages]
      .reverse()
      .find((message) => message.role === "user")?.content || "";

    const delay = shouldShowThinkingForRequest(latestUserMessage)
      ? 420
      : 220;

    setAiStatusVisible(false);
    timeoutId = window.setTimeout(() => {
      setAiStatusVisible(true);
    }, delay);

    return () => window.clearTimeout(timeoutId);
  }, [isStreaming, messages, researchState.active]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }

    const minHeight = 42;
    const maxHeight = 180;

    textarea.style.height = "auto";
    const nextHeight = Math.min(
      Math.max(textarea.scrollHeight, minHeight),
      maxHeight
    );
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY =
      textarea.scrollHeight > maxHeight ? "auto" : "hidden";
  }, [input]);

  useEffect(() => {
    if (openConversationMenu === null) {
      const lastId = lastConversationMenuIdRef.current;
      if (lastId !== null) {
        requestAnimationFrame(() => {
          conversationMenuTriggerRefs.current.get(lastId)?.focus();
        });
      }
      return;
    }

    lastConversationMenuIdRef.current = openConversationMenu;

    requestAnimationFrame(() => {
      conversationMenuFirstActionRef.current?.focus();
    });
  }, [openConversationMenu]);

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

  const persistConversationScrollPosition = () => {
    const container = chatContainerRef.current;
    if (!container || conversationId === null) {
      return;
    }

    conversationScrollPositionsRef.current.set(
      Number(conversationId),
      Math.max(0, Math.round(container.scrollTop))
    );

    try {
      window.sessionStorage.setItem(
        "zoya:conversation-scroll",
        JSON.stringify(
          Object.fromEntries(conversationScrollPositionsRef.current.entries())
        )
      );
    } catch {
      // Ignore session storage failures.
    }
  };

  const restoreConversationScrollPosition = (targetConversationId) => {
    const saved = conversationScrollPositionsRef.current.get(
      Number(targetConversationId)
    );

    requestAnimationFrame(() => {
      const container = chatContainerRef.current;
      if (!container) {
        return;
      }

      if (Number.isFinite(saved)) {
        container.scrollTop = Math.min(
          saved,
          Math.max(0, container.scrollHeight - container.clientHeight)
        );
        isNearBottomRef.current =
          container.scrollHeight - container.scrollTop - container.clientHeight < 96;
        setIsNearBottom(isNearBottomRef.current);
      } else {
        container.scrollTop = container.scrollHeight;
        isNearBottomRef.current = true;
        setIsNearBottom(true);
      }
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

    if (!isLoadingHistory && switchingConversationId === null) {
      persistConversationScrollPosition();
    }
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

  const hasChatSearch = chatSearch.trim().length > 0;

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
      await renameConversation(editingConversation, title);
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
      await deleteConversationRequest(conversation.conversation_id);

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

  const formatConversationTitle = (value) => {

    let title = String(value || "")
      .replace(/```[\s\S]*?```/g, "")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/[.!?]+$/, "");

    if (!title) {
      return "New conversation";
    }

    const imageRequest = /\b(?:generate|create|make|banao|bana(?:o)?|render)\b/i.test(title);

    if (imageRequest) {
      title = title.split(/,|\n/)[0].trim();
      title = title
        .replace(/^(?:ek|a|an|the)\s+/i, "")
        .replace(/\b(?:generate|create|make|banao|bana|karo|kar do|karna hai)\b/gi, "")
        .replace(/\s+/g, " ")
        .trim();
    } else {
      title = title
        .replace(/^(?:mujhe|mere liye|main|mera|meri|i need|i want|please)\s+/i, "")
        .replace(/^ek\s+/i, "")
        .replace(/\s+/g, " ")
        .trim();
    }

    if (!title) {
      return "New conversation";
    }

    if (title.length <= 48) {
      return title;
    }

    const shortened = title.slice(0, 48).replace(/\s+\S*$/, "").trim();
    return shortened || title.slice(0, 48).trim();
  };

  const loadConversations = async () => {

    setIsLoadingConversations(true);

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/chat/conversations?user_id=1&limit=200`
      );

      if (!response.ok) {
        throw new Error("Conversation list load failed.");
      }

      const data = await response.json();
      const items = Array.isArray(data)
        ? data
        : data.conversations || [];

      const normalizedItems = items.map((item) => {
        const manualTitle = String(item.summary || "").trim();

        return {
          conversation_id: item.conversation_id,
          title: manualTitle
            ? manualTitle
            : formatConversationTitle(item.title),
          started_at: item.started_at || null,
          message_count: Number(item.message_count || 0),
          summary: manualTitle,
        };
      });

      setConversations(normalizedItems);
      setConversationCount(
        Number.isFinite(Number(data.total_count))
          ? Number(data.total_count)
          : normalizedItems.length
      );
    } catch (error) {
      console.warn("Conversation list unavailable:", error);
      setConversations([]);
      setConversationCount(0);
    } finally {
      setIsLoadingConversations(false);
    }

  };

  const loadHistory = async (requestedConversationId = null) => {

    setIsLoadingHistory(true);

    try {
      const data = await getConversationHistory(requestedConversationId);

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

      if (requestedConversationId !== null) {
        restoreConversationScrollPosition(
          data.conversation_id ?? requestedConversationId
        );
      } else {
        isNearBottomRef.current = true;
        setIsNearBottom(true);
      }
    } catch (error) {
      console.error("History loading error:", error);

      if (requestedConversationId !== null) {
        setMessages([]);
      }
    } finally {
      setIsLoadingHistory(false);
      setSwitchingConversationId(null);
      setSwitchingConversationTitle("");
    }

  };

  const selectConversation = async (id) => {

    if (
      isStreaming ||
      id === conversationId ||
      switchingConversationId !== null
    ) {
      return;
    }

    persistConversationScrollPosition();
    setSwitchingConversationId(id);
    setSwitchingConversationTitle(
      conversations.find(
        (conversation) => conversation.conversation_id === id
      )?.title || "Conversation"
    );

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
      const data = await createConversation();
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

          researchSourcesRef.current = nextSources;

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

  const attachResearchSourcesToAssistantMessage = () => {

    const sources = Array.isArray(researchSourcesRef.current)
      ? researchSourcesRef.current
      : [];

    if (!sources.length) {
      return;
    }

    setMessages((previous) => {
      const lastIndex = previous.length - 1;
      const lastMessage = previous[lastIndex];

      if (lastMessage?.role !== "assistant") {
        return previous;
      }

      const existingSources = Array.isArray(lastMessage.sources)
        ? lastMessage.sources
        : [];

      const mergedSources = [...existingSources];

      for (const source of sources) {
        if (!source?.url) continue;
        if (!mergedSources.some((item) => item?.url === source.url)) {
          mergedSources.push(source);
        }
      }

      return [
        ...previous.slice(0, lastIndex),
        {
          ...lastMessage,
          sources: mergedSources,
        },
      ];
    });
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

      "image"

    ) {

      if (!data?.url) {
        return;
      }

      const imageUrl = data.url.startsWith("http")
        ? data.url
        : `${API_BASE_URL}${data.url}`;

      const downloadUrl = data.download_url
        ? (data.download_url.startsWith("http")
          ? data.download_url
          : `${API_BASE_URL}${data.download_url}`)
        : imageUrl;

      setMessages((previous) => {
        const lastMessage = previous[previous.length - 1];

        if (lastMessage?.role === "assistant") {
          return [
            ...previous.slice(0, -1),
            {
              ...lastMessage,
              image: {
                ...data,
                url: imageUrl,
                download_url: downloadUrl,
              },
            },
          ];
        }

        return [
          ...previous,
          {
            role: "assistant",
            content: "",
            timestamp: new Date().toISOString(),
            image: {
              ...data,
              url: imageUrl,
              download_url: downloadUrl,
            },
          },
        ];
      });

      return;

    }

    if (

      eventName ===

      "done"

    ) {

      attachResearchSourcesToAssistantMessage();
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

  const getLastUserMessage = () =>
    [...messages]
      .reverse()
      .find((message) => message?.role === "user" && message.content?.trim());

  const retryLastFailedMessage = async () => {
    if (isStreaming) return;

    const lastUserMessage = getLastUserMessage();
    if (!lastUserMessage) return;

    setErrorMessage("");

    setMessages((previous) => {
      const lastIndex = previous.length - 1;
      const last = previous[lastIndex];

      if (last?.role === "assistant" && last.content?.startsWith("Sorry Ayan,")) {
        return previous.slice(0, lastIndex);
      }

      return previous;
    });

    await streamMessage(lastUserMessage.content, {
      appendUserMessage: false,
      clearError: true,
    });
  };

  const dismissError = () => {
    setErrorMessage("");
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
      await streamChat({
        userId: 1,
        userName: "Ayan",
        message,
        conversationId,
        newConversation: isStartingNewChat,
        signal: controller.signal,
        onEvent: handleServerEvent,
      });

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
        const errorText =
          error instanceof Error
            ? error.message
            : "Something went wrong.";

        setErrorMessage(errorText);
        setResearchState(createInitialResearchState());
        setMessages((previous) => [
          ...previous,
          {
            role: "assistant",
            content: `Sorry Ayan, ${errorText}`,
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


  useKeyboardShortcuts({
    chatSearchInputRef,
    composerRef: textareaRef,
    onEscape: () => {
      if (chatSearch.trim()) {
        setChatSearch("");
        chatSearchInputRef.current?.blur();
        return;
      }

      lastConversationMenuIdRef.current = openConversationMenu;
      setOpenConversationMenu(null);
      setOpenCitationUrl(null);
      setOpenSourcesMessageIndex(null);
      setIsSidebarOpen(false);

      if (editingMessageIndex !== null) {
        setEditingMessageIndex(null);
        setInput("");
      }

      if (editingConversation !== null) {
        setEditingConversation(null);
        setConversationNameDraft("");
      }

      if (showCreateForm) {
        setShowCreateForm(false);
      }

      if (editingMemory !== null) {
        setEditingMemory(null);
      }
    },
  });

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
      setIsSidebarOpen(false);
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
      setIsSidebarOpen(false);
      setOpenConversationMenu(null);

      setMemoryActionError("");

    };

  const showWelcome =

    !isLoadingHistory &&

    messages.length === 0;

  const starterPrompts = [
    "Explain a concept in simple words",
    "Help me write or debug code",
    "Research a topic for me",
    "Help me plan something",
  ];

  const useStarterPrompt = (prompt) => {
    setInput(prompt);
    requestAnimationFrame(() => {
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(prompt.length, prompt.length);
    });
  };

  // Research status always wins. Thinking is deliberately opt-in for
  // complex/explicitly slow requests so short chats do not feel heavy.
  // Once assistant text starts streaming, the answer itself is the feedback.
  const latestUserMessage = [...messages]
    .reverse()
    .find((message) => message.role === "user")?.content || "";

  const shouldShowThinking = shouldShowThinkingForRequest(latestUserMessage);

  const aiPhase =
    !isStreaming
      ? "idle"
      : researchState.active
        ? "researching"
        : messages[messages.length - 1]?.role === "assistant"
          ? "idle"
          : !aiStatusVisible
            ? "idle"
            : shouldShowThinking
              ? "thinking"
              : "typing";

  return (

    <>
      <a className="skip-link" href="#zoya-main-content">
        Skip to main content
      </a>

      <div className={`app ${isSidebarCollapsed ? "sidebar-collapsed" : ""}`}>

      <aside
        className={`sidebar ${isSidebarOpen ? "open" : ""}`}
        aria-label="Conversation sidebar"
      >
        <div className="sidebar-header">
          <button
            type="button"
            className="sidebar-brand"
            onClick={() => {
              setIsSidebarCollapsed(false);
              openChatView();
            }}
            aria-label="Open Zoya chat and expand sidebar"
          >
            <span className="brand-avatar">Z</span>
            <span className="sidebar-brand-copy">
              <strong>Zoya</strong>
              <span>Personal AI</span>
            </span>
          </button>
          <button
            type="button"
            className="sidebar-collapse-button"
            onClick={() => setIsSidebarCollapsed(true)}
            aria-label="Collapse sidebar"
            title="Collapse sidebar"
          >
            ‹
          </button>
          <button
            type="button"
            className="sidebar-close"
            onClick={() => setIsSidebarOpen(false)}
            aria-label="Close sidebar"
          >
            ×
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

        <div className={`sidebar-search-wrap ${hasChatSearch ? "has-query" : ""}`}>
          <span className="sidebar-search-icon">⌕</span>
          <input
            ref={chatSearchInputRef}
            value={chatSearch}
            onChange={(event) => setChatSearch(event.target.value)}
            placeholder="Search chats"
            aria-label="Search chats"
            aria-controls="zoya-conversation-list"
            aria-describedby="zoya-search-status"
          />
          {chatSearch && (
            <button
              type="button"
              className="sidebar-search-clear"
              onClick={() => {
                setChatSearch("");
                chatSearchInputRef.current?.focus();
              }}
              aria-label="Clear chat search"
            >
              ×
            </button>
          )}
        </div>

        <div id="zoya-search-status" className="sidebar-search-status" aria-live="polite">
          {hasChatSearch
            ? `${filteredConversations.length} ${
                filteredConversations.length === 1 ? "chat" : "chats"
              } found`
            : ""}
        </div>

        <div className="sidebar-section-title">
          <span>Chats</span>
          <span className="sidebar-count">{conversationCount}</span>
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

        <div
          className="conversation-switch-live-status"
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          {switchingConversationId !== null
            ? `Loading ${switchingConversationTitle || "conversation"}`
            : ""}
        </div>

        <div className="conversation-list" id="zoya-conversation-list">
          {isLoadingConversations ? (
            <div className="conversation-loading">
              <span className="conversation-skeleton" />
              <span className="conversation-skeleton short" />
              <span className="conversation-skeleton" />
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="conversation-empty search-empty">
              <span className="conversation-empty-icon">⌕</span>
              <strong>{hasChatSearch ? "No matching chats" : "No saved chats yet"}</strong>
              <span>
                {hasChatSearch
                  ? `Nothing matches “${chatSearch.trim()}”.`
                  : "Start a new conversation and it will appear here."}
              </span>
              {!hasChatSearch && (
                <button
                  type="button"
                  className="conversation-empty-action"
                  onClick={startNewChat}
                  disabled={isStartingNewChat || isStreaming}
                >
                  {isStartingNewChat ? "Starting…" : "Start your first chat"}
                </button>
              )}
              {hasChatSearch && (
                <button
                  type="button"
                  className="conversation-empty-clear"
                  onClick={() => {
                    setChatSearch("");
                    chatSearchInputRef.current?.focus();
                  }}
                >
                  Clear search
                </button>
              )}
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
                  disabled={isStreaming || switchingConversationId !== null}
                  aria-current={
                    conversation.conversation_id === conversationId
                      ? "page"
                      : undefined
                  }
                >
                  <span className="conversation-item-icon">{pinnedConversationIds.includes(conversation.conversation_id) ? "★" : "✦"}</span>
                  <span className="conversation-item-copy">
                    <span className="conversation-item-title">
                      {highlightConversationTitle(conversation.title, chatSearch)}
                    </span>
                    <span className="conversation-item-meta">
                      {switchingConversationId === conversation.conversation_id
                        ? "Loading…"
                        : formatConversationDate(conversation.started_at)}
                    </span>
                  </span>

                  {switchingConversationId === conversation.conversation_id && (
                    <span
                      className="conversation-switch-spinner"
                      aria-hidden="true"
                    />
                  )}
                </button>

                <button
                  type="button"
                  className="conversation-item-menu-trigger"
                  ref={(node) => {
                    const id = conversation.conversation_id;
                    if (node) {
                      conversationMenuTriggerRefs.current.set(id, node);
                    } else {
                      conversationMenuTriggerRefs.current.delete(id);
                    }
                  }}
                  onClick={(event) =>
                    handleConversationMenuToggle(
                      event,
                      conversation.conversation_id
                    )
                  }
                  disabled={isStreaming || switchingConversationId !== null}
                  aria-label={`Conversation actions for ${conversation.title}`}
                  aria-haspopup="menu"
                  aria-controls={`conversation-menu-${conversation.conversation_id}`}
                  aria-expanded={
                    openConversationMenu === conversation.conversation_id
                  }
                  title="Conversation actions"
                >
                  ⋯
                </button>

                {openConversationMenu === conversation.conversation_id && (
                  <div
                    id={`conversation-menu-${conversation.conversation_id}`}
                    className="conversation-item-menu"
                    role="menu"
                    aria-label={`Actions for ${conversation.title}`}
                    onClick={(event) => event.stopPropagation()}
                  >
                    <button
                      type="button"
                      role="menuitem"
                      ref={conversationMenuFirstActionRef}
                      onClick={() => beginRenameConversation(conversation)}
                    >
                      Rename
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => togglePinnedConversation(conversation.conversation_id)}
                    >
                      {pinnedConversationIds.includes(conversation.conversation_id) ? "Unpin" : "Pin"}
                    </button>
                    <button
                      type="button"
                      role="menuitem"
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
            aria-current={activeView === "chat" ? "page" : undefined}
          >
            <span>⌂</span> Chat
          </button>
          <button
            type="button"
            className={`sidebar-nav-button ${
              activeView === "memory" ? "active" : ""
            }`}
            onClick={openMemoryView}
            aria-current={activeView === "memory" ? "page" : undefined}
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
            <ThemeSwitcher
              theme={theme}
              onThemeChange={setTheme}
            />
          </div>
        </header>

      {activeView ===

      "chat" ? (

        <>

          <main
            id="zoya-main-content"
            className="chat-container"
            ref={chatContainerRef}
            tabIndex={-1}
            aria-label="Chat with Zoya"
            aria-busy={isLoadingHistory || isStreaming}
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

                  Main Zoya hoon, aapki personal AI assistant.

                </p>

                <span>

                  Start with a prompt below, ya seedha kuch bhi type karo.

                </span>

                <div className="welcome-eyebrow">QUICK START</div>

                <div className="welcome-prompts" aria-label="Starter prompts">
                  {starterPrompts.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      className="welcome-prompt-button"
                      onClick={() => useStarterPrompt(prompt)}
                    >
                      {prompt}
                    </button>
                  ))}
                </div>

              </section>

            )}

            <section className="messages">

              {isLoadingHistory ? (

                <div
                  className="history-loading-skeleton"
                  aria-label="Loading conversation"
                  role="status"
                >
                  <div className="history-skeleton-row assistant">
                    <span className="history-skeleton-avatar" />
                    <span className="history-skeleton-content">
                      <span className="history-skeleton-meta" />
                      <span className="history-skeleton-line wide" />
                      <span className="history-skeleton-line medium" />
                    </span>
                  </div>
                  <div className="history-skeleton-row user">
                    <span className="history-skeleton-content">
                      <span className="history-skeleton-meta short" />
                      <span className="history-skeleton-line medium" />
                    </span>
                  </div>
                  <div className="history-skeleton-row assistant">
                    <span className="history-skeleton-avatar" />
                    <span className="history-skeleton-content">
                      <span className="history-skeleton-meta" />
                      <span className="history-skeleton-line long" />
                      <span className="history-skeleton-line wide" />
                      <span className="history-skeleton-line short" />
                    </span>
                  </div>
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
                              pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
                            }}
                          >
                            {cleanDisplayedContent(message.content)}
                          </ReactMarkdown>

                          {message.image?.url && (
                            <div
                              className="generated-image-container"
                              style={{
                                marginTop: "14px",
                                display: "flex",
                                flexDirection: "column",
                                alignItems: "flex-start",
                                gap: "10px",
                              }}
                            >
                              <img
                                src={message.image.url}
                                alt={message.image.filename || "Generated by Zoya"}
                                className="generated-image"
                                loading="lazy"
                                style={{
                                  display: "block",
                                  width: "min(100%, 720px)",
                                  maxHeight: "720px",
                                  objectFit: "contain",
                                  borderRadius: "14px",
                                }}
                              />

                              <a
                                href={message.image.download_url || message.image.url}
                                className="generated-image-download"
                                download
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  padding: "8px 14px",
                                  borderRadius: "8px",
                                  textDecoration: "none",
                                  fontSize: "14px",
                                  fontWeight: 600,
                                  cursor: "pointer",
                                }}
                              >
                                ↓ Download Image
                              </a>
                            </div>
                          )}
                          {message.streaming && <span className="streaming-cursor">▋</span>}
                          {message.status === "stopped" && !message.streaming && (
                            <div className="message-stopped-label">Generation stopped</div>
                          )}
                        </div>

                        {message.role === "user" && !message.streaming && (
                          <div className="message-actions user-message-actions" aria-label="Message actions">
                            <button
                              type="button"
                              className="message-action-button icon-only"
                              onClick={() => beginEditMessage(index)}
                              aria-label="Edit message"
                              title="Edit"
                              data-tooltip="Edit"
                              disabled={isStreaming}
                            >
                              ✎
                            </button>
                          </div>
                        )}

                        {message.role === "assistant" && !message.streaming && (
                          <div className="message-actions assistant-message-actions" aria-label="Message actions">
                            <button
                              type="button"
                              className="message-action-button icon-only"
                              onClick={() => retryAssistantMessage(index)}
                              aria-label="Retry response"
                              title="Retry"
                              data-tooltip="Retry"
                            >
                              ↻
                            </button>
                            <button
                              type="button"
                              className="message-action-button icon-only"
                              onClick={() => copyMessage(message, index)}
                              aria-label={copiedMessageIndex === index ? "Copied response" : "Copy response"}
                              title={copiedMessageIndex === index ? "Copied" : "Copy"}
                              data-tooltip={copiedMessageIndex === index ? "Copied" : "Copy"}
                            >
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

                        {message.role === "assistant" && copiedMessageIndex === index && (
                          <span className="message-action-live-status" role="status" aria-live="polite">Copied response</span>
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

              <div
                className={`ai-status-shell ${
                  aiPhase !== "idle" ? "visible" : ""
                }`}
                aria-live="polite"
                aria-atomic="true"
              >
                <AiStatusIndicator
                  phase={aiPhase}
                  researchState={researchState}
                />
              </div>

              <div

                ref={

                  messagesEndRef

                }

              />

            </section>

          </main>

          {!isNearBottom && messages.length > 0 && (
            <button
              type="button"
              className="scroll-latest-button"
              onClick={scrollToLatest}
              aria-label="Jump to latest message"
              title="Jump to latest message"
            >
              <span aria-hidden="true">↓</span>
              <span>Latest</span>
            </button>
          )}

          <footer className="composer-wrapper">

            {editingMessageIndex !== null && (
              <div className="composer-editing-bar">
                <span>Editing message</span>
                <button type="button" onClick={cancelEditMessage}>Cancel</button>
              </div>
            )}

            {errorMessage && (

              <div id="zoya-chat-error" className="error-banner" role="alert" aria-live="assertive">

                <span className="error-banner-icon" aria-hidden="true">⚠️</span>

                <div className="error-banner-content">

                  <strong>Something went wrong</strong>

                  <span>{errorMessage}</span>

                </div>

                <div className="error-banner-actions">

                  {getLastUserMessage() && (
                    <button
                      type="button"
                      className="error-banner-retry"
                      onClick={retryLastFailedMessage}
                      disabled={isStreaming}
                    >
                      Retry
                    </button>
                  )}

                  <button
                    type="button"
                    className="error-banner-dismiss"
                    onClick={dismissError}
                    aria-label="Dismiss error"
                    title="Dismiss"
                  >
                    ×
                  </button>

                </div>

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

                aria-describedby={errorMessage ? "zoya-chat-error" : undefined}

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
                title={
                  isStreaming
                    ? "Stop response"
                    : canSend
                      ? "Send message"
                      : "Enter a message"
                }

              >

                {isStreaming
                  ? "■"
                  : "↑"}

              </button>

            </div>

          </footer>

        </>

      ) : (

        <main
          id="zoya-main-content"
          className="memory-container"
          tabIndex={-1}
          aria-label="Zoya memory"
          aria-busy={isLoadingMemories}
        >

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
    </>

  );

}

export default App;
