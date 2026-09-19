import { useEffect, useState } from "react";

function MemoryEditModal({
  memory,
  onClose,
  onSave,
}) {
  const [value, setValue] = useState("");
  const [importance, setImportance] =
    useState(5);
  const [isSaving, setIsSaving] =
    useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!memory) {
      return;
    }

    setValue(memory.value);
    setImportance(memory.importance);
    setError("");
  }, [memory]);

  useEffect(() => {
    if (!memory) {
      return;
    }

    const handleEscape = (event) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener(
      "keydown",
      handleEscape
    );

    return () => {
      document.removeEventListener(
        "keydown",
        handleEscape
      );
    };
  }, [memory, onClose]);

  if (!memory) {
    return null;
  }

  const handleSubmit = async (event) => {
    event.preventDefault();

    const trimmedValue = value.trim();

    if (!trimmedValue) {
      setError(
        "Memory value cannot be empty."
      );
      return;
    }

    try {
      setIsSaving(true);
      setError("");

      await onSave(memory.memory_id, {
        value: trimmedValue,
        importance: Number(importance),
      });

      onClose();
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to update memory."
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleBackdropClick = (event) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className="memory-modal-backdrop"
      onMouseDown={handleBackdropClick}
    >
      <div
        className="memory-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="memory-edit-title"
      >
        <div className="memory-modal-header">
          <div>
            <span className="memory-modal-label">
              Edit Memory
            </span>

            <h2 id="memory-edit-title">
              {memory.key}
            </h2>
          </div>

          <button
            type="button"
            className="memory-modal-close"
            onClick={onClose}
            disabled={isSaving}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <form
          className="memory-edit-form"
          onSubmit={handleSubmit}
        >
          <label>
            <span>Memory value</span>

            <textarea
              value={value}
              onChange={(event) =>
                setValue(event.target.value)
              }
              rows={4}
              maxLength={1000}
              disabled={isSaving}
              autoFocus
            />
          </label>

          <label>
            <div className="memory-range-label">
              <span>Importance</span>

              <strong>
                {importance}/10
              </strong>
            </div>

            <input
              type="range"
              min="1"
              max="10"
              step="1"
              value={importance}
              onChange={(event) =>
                setImportance(
                  Number(event.target.value)
                )
              }
              disabled={isSaving}
            />
          </label>

          {error && (
            <div className="memory-form-error">
              ⚠️ {error}
            </div>
          )}

          <div className="memory-modal-actions">
            <button
              type="button"
              className="memory-secondary-button"
              onClick={onClose}
              disabled={isSaving}
            >
              Cancel
            </button>

            <button
              type="submit"
              className="memory-primary-button"
              disabled={
                isSaving ||
                !value.trim()
              }
            >
              {isSaving
                ? "Saving..."
                : "Save Changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default MemoryEditModal;