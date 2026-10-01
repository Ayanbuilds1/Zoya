const STATUS_COPY = {
  thinking: {
    label: "Thinking...",
    detail: "Working on your request",
  },
};

export default function AiStatusIndicator({ phase, researchState }) {
  if (phase === "researching") {
    return (
      <div className="research-activity" role="status" aria-live="polite">
        <div className="research-activity-main">
          <span className="research-spinner" aria-hidden="true"></span>
          <div>
            <div className="research-activity-title">
              {researchState?.status || "Searching the web..."}
            </div>
            <div className="research-activity-detail">
              {researchState?.detail || "Finding current information"}
            </div>
            {researchState?.currentQuery && (
              <div className="research-current-query">
                {researchState.currentQuery}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (phase === "typing") {
    return (
      <div className="message-row assistant ai-typing-row" role="status" aria-live="polite">
        <div className="message-avatar">Z</div>
        <div className="message-content">
          <div className="message-meta">
            <span className="message-name">Zoya</span>
          </div>
          <div className="message-bubble typing ai-typing-bubble">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>
    );
  }

  const copy = STATUS_COPY[phase];
  if (!copy) return null;

  return (
    <div className="ai-status-compact" role="status" aria-live="polite">
      <span className="ai-status-orb" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <span className="ai-status-copy">
        <strong>{copy.label}</strong>
        <span>{copy.detail}</span>
      </span>
    </div>
  );
}
