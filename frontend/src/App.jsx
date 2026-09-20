import { useEffect, useRef, useState } from "react";
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
  const textareaRef = useRef(null);

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
    loadHistory();
  }, []);

  useEffect(() => {
    if (!messagesEndRef.current) {
      return;
    }

    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({
        behavior:
          isStreaming
            ? "auto"
            : "smooth",
        block: "end",
      });
    });
  }, [
    messages,
    isStreaming,
    researchState.active,
    researchState.completed,
  ]);

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

  const loadHistory = async () => {
    try {
      const response =
        await fetch(
          `${API_BASE_URL}/api/chat/history?user_id=1`
        );

      if (!response.ok) {
        throw new Error(
          "History load failed."
        );
      }

      const data =
        await response.json();

      if (
        data.conversation_id
      ) {
        setConversationId(
          data.conversation_id
        );
      }

      if (
        data.messages?.length >
        0
      ) {
        setMessages(
          data.messages.map(
            (message) => ({
              role:
                message.role,
              content:
                message.content,
              timestamp:
                message.created_at ||
                new Date().toISOString(),
            })
          )
        );
      }
    } catch (error) {
      console.error(
        "History loading error:",
        error
      );
    } finally {
      setIsLoadingHistory(
        false
      );
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

  const copyMessage =
    async (
      message,
      index
    ) => {
      try {
        await navigator.clipboard.writeText(
          message.content
        );

        setCopiedMessageIndex(
          index
        );

        window.setTimeout(
          () => {
            setCopiedMessageIndex(
              null
            );
          },
          1600
        );
      } catch (error) {
        console.error(
          "Copy failed:",
          error
        );
      }
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

  const sendMessage =
    async () => {
      const message =
        input.trim();

      if (!canSend) {
        return;
      }

      setErrorMessage("");
      setInput("");
      setIsStreaming(true);
      resetResearchState();

      setMessages((previous) => [
        ...previous,
        {
          role: "user",
          content: message,
          timestamp:
            new Date().toISOString(),
        },
      ]);

      try {
        const response =
          await fetch(
            `${API_BASE_URL}/api/chat/stream`,
            {
              method: "POST",
              headers: {
                "Content-Type":
                  "application/json",
                Accept:
                  "text/event-stream",
              },
              body: JSON.stringify({
                user_id: 1,
                user_name: "Ayan",
                message,
                conversation_id:
                  conversationId,
              }),
            }
          );

        if (!response.ok) {
          let errorMessage =
            "Zoya AI service is temporarily unavailable.";

          try {
            const errorData =
              await response.json();

            if (
              errorData?.detail
            ) {
              if (
                Array.isArray(
                  errorData.detail
                )
              ) {
                errorMessage =
                  errorData
                    .detail[0]
                    ?.msg ||
                  errorMessage;
              } else {
                errorMessage =
                  errorData.detail;
              }
            }
          } catch {
            // Keep default.
          }

          throw new Error(
            errorMessage
          );
        }

        if (!response.body) {
          throw new Error(
            "Streaming response is not supported by this browser."
          );
        }

        const reader =
          response.body.getReader();

        const decoder =
          new TextDecoder(
            "utf-8"
          );

        let buffer = "";
        let streamCompleted =
          false;

        while (
          !streamCompleted
        ) {
          const {
            value,
            done,
          } =
            await reader.read();

          if (done) {
            break;
          }

          buffer +=
            decoder.decode(
              value,
              {
                stream: true,
              }
            );

          const events =
            buffer.split(
              "\n\n"
            );

          buffer =
            events.pop() ||
            "";

          for (
            const event of events
          ) {
            const result =
              handleServerEvent(
                event
              );

            if (
              result === "done"
            ) {
              streamCompleted =
                true;
              break;
            }
          }
        }

        buffer +=
          decoder.decode();

        if (
          buffer.trim() &&
          !streamCompleted
        ) {
          handleServerEvent(
            buffer
          );
        }

        finishAssistantMessage();
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "Something went wrong.";

        setErrorMessage(
          message
        );

        setResearchState(
          createInitialResearchState()
        );

        setMessages((previous) => [
          ...previous,
          {
            role: "assistant",
            content: `Sorry Ayan, ${message}`,
            timestamp:
              new Date().toISOString(),
          },
        ]);
      } finally {
        setIsStreaming(
          false
        );
      }
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

  const showResearchSummary =
    researchState.completed &&
    researchState.totalSources >
      0;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-avatar">
            Z
          </div>

          <div>
            <h1>Zoya</h1>

            <div className="status">
              <span className="status-dot"></span>
              Online
            </div>
          </div>
        </div>

        <nav className="topbar-nav">
          <button
            type="button"
            className={`nav-button ${
              activeView ===
              "chat"
                ? "active"
                : ""
            }`}
            onClick={
              openChatView
            }
          >
            Chat
          </button>

          <button
            type="button"
            className={`nav-button ${
              activeView ===
              "memory"
                ? "active"
                : ""
            }`}
            onClick={
              openMemoryView
            }
          >
            Memory
          </button>
        </nav>
      </header>

      {activeView ===
      "chat" ? (
        <>
          <main className="chat-container">
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
                messages.map(
                  (
                    message,
                    index
                  ) => (
                    <div
                      className={`message-row ${message.role}`}
                      key={index}
                    >
                      {message.role ===
                        "assistant" && (
                        <div className="message-avatar">
                          Z
                        </div>
                      )}

                      <div className="message-content">
                        <div className="message-meta">
                          <span className="message-name">
                            {message.role ===
                            "assistant"
                              ? "Zoya"
                              : "Ayan"}
                          </span>

                          {message.timestamp && (
                            <span className="message-time">
                              {formatTime(
                                message.timestamp
                              )}
                            </span>
                          )}
                        </div>

                        <div className="message-bubble">
                          <ReactMarkdown
                            remarkPlugins={[
                              remarkGfm,
                            ]}
                            rehypePlugins={[
                              rehypeRaw,
                            ]}
                            components={{
                              a: ({node,
                                href,
                                children,
                                }) => 
                                  (<CitationLink
                                  href={href}
                                  children={children}
                                  sources={researchState.sources}
                                  isOpen={
                                    openCitationUrl === href
                                  }
                                  onToggle={
                                    toggleCitation
                                  }
                                  />
                                ),
                              }}
                            
                          >
                            {normalizeResearchMarkdown(
                              message.content
                            )}
                          </ReactMarkdown>

                          {message.streaming && (
                            <span className="streaming-cursor">
                              ▋
                            </span>
                          )}
                        </div>

                        {message.role ===
                          "assistant" &&
                          !message.streaming && (
                            <div className="message-actions">
                              <button
                                type="button"
                                className="message-action-button"
                                onClick={() =>
                                  copyMessage(
                                    message,
                                    index
                                  )
                                }
                                aria-label="Copy response"
                              >
                                <span
                                  className="message-action-icon"
                                  aria-hidden="true"
                                >
                                  ⧉
                                </span>

                                {copiedMessageIndex ===
                                index
                                  ? "Copied"
                                  : "Copy"}
                              </button>
                            </div>
                          )}
                      </div>
                    </div>
                  )
                )
              )}

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

              {showResearchSummary && (
                <div className="research-summary-wrapper">
                  <button
                    type="button"
                    className="research-summary-button"
                    onClick={
                      toggleResearchSources
                    }
                    aria-expanded={
                      researchState.sourcesExpanded
                    }
                  >
                    <span className="research-summary-count">
                      {
                        researchState.totalSources
                      }{" "}
                      source
                      {researchState.totalSources ===
                      1
                        ? ""
                        : "s"}
                    </span>

                    {researchState.workedSeconds !==
                      null && (
                      <span className="research-worked-time">
                        · Worked for{" "}
                        {formatWorkedTime(
                          researchState.workedSeconds
                        )}
                      </span>
                    )}

                    <span
                      className={`research-chevron ${
                        researchState.sourcesExpanded
                          ? "open"
                          : ""
                      }`}
                    >
                      ⌄
                    </span>
                  </button>

                  {researchState.sourcesExpanded && (
                    <div className="research-sources-dropdown">
                      {researchState.sources.map(
                        (
                          source
                        ) => (
                          <a
                            key={
                              source.url
                            }
                            href={
                              source.url
                            }
                            target="_blank"
                            rel="noopener noreferrer"
                            className="research-source-link"
                          >
                            <span className="research-source-title">
                              {
                                source.title
                              }
                            </span>

                            {source.domain && (
                              <span className="research-source-domain">
                                {
                                  source.domain
                                }
                              </span>
                            )}
                          </a>
                        )
                      )}
                    </div>
                  )}
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
                  isStreaming
                    ? "Zoya is replying..."
                    : "Message Zoya..."
                }
                rows={1}
                maxLength={
                  MAX_MESSAGE_LENGTH
                }
                disabled={
                  isStreaming ||
                  isLoadingHistory
                }
              />

              <button
                type="button"
                onClick={
                  sendMessage
                }
                disabled={
                  !canSend
                }
                aria-label="Send message"
              >
                {isStreaming
                  ? "..."
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
  );
}

export default App;