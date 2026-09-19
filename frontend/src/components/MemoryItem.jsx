import { useState } from "react";

function MemoryItem({
  memory,
  onEdit,
  onDelete,
}) {
  const [isDeleting, setIsDeleting] =
    useState(false);

  const handleDelete = async () => {
    const confirmed = window.confirm(
      `Delete memory "${memory.key}"?`
    );

    if (!confirmed) {
      return;
    }

    try {
      setIsDeleting(true);
      await onDelete(memory.memory_id);
    } catch (error) {
      console.error(
        "Memory deletion error:",
        error
      );
    } finally {
      setIsDeleting(false);
    }
  };

  const formatDate = (timestamp) => {
    if (!timestamp) {
      return "";
    }

    const date = new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
      return "";
    }

    return date.toLocaleDateString([], {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  };

  return (
    <article className="memory-item">
      <div className="memory-item-header">
        <div className="memory-item-title">
          <span className="memory-key">
            {memory.key}
          </span>

          <span className="memory-category">
            {memory.category}
          </span>
        </div>

        <div className="memory-importance">
          <span>Importance</span>

          <strong>
            {memory.importance}/10
          </strong>
        </div>
      </div>

      <div className="memory-value">
        {memory.value}
      </div>

      <div className="memory-item-meta">
        <span>
          Source: {memory.source}
        </span>

        <span>
          Confidence:{" "}
          {Math.round(memory.confidence * 100)}%
        </span>

        {memory.updated_at && (
          <span>
            Updated:{" "}
            {formatDate(memory.updated_at)}
          </span>
        )}
      </div>

      <div className="memory-item-actions">
        <button
          type="button"
          className="memory-action-button edit"
          onClick={() => onEdit(memory)}
        >
          Edit
        </button>

        <button
          type="button"
          className="memory-action-button delete"
          onClick={handleDelete}
          disabled={isDeleting}
        >
          {isDeleting
            ? "Deleting..."
            : "Delete"}
        </button>
      </div>
    </article>
  );
}

export default MemoryItem;