import { useState } from "react";

function MemoryCreateForm({
  onCreate,
  onCancel,
}) {
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [category, setCategory] =
    useState("");
  const [importance, setImportance] =
    useState(5);
  const [isSaving, setIsSaving] =
    useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();

    const trimmedKey = key.trim();
    const trimmedValue = value.trim();
    const trimmedCategory = category.trim();

    if (!trimmedKey) {
      setError("Memory key cannot be empty.");
      return;
    }

    if (!trimmedValue) {
      setError("Memory value cannot be empty.");
      return;
    }

    if (!trimmedCategory) {
      setError("Category cannot be empty.");
      return;
    }

    try {
      setIsSaving(true);
      setError("");

      await onCreate({
        key: trimmedKey,
        value: trimmedValue,
        category: trimmedCategory,
        importance: Number(importance),
      });

      setKey("");
      setValue("");
      setCategory("");
      setImportance(5);
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Unable to create memory."
      );
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <form
      className="memory-create-form"
      onSubmit={handleSubmit}
    >
      <div className="memory-create-header">
        <div>
          <span className="memory-modal-label">
            New Memory
          </span>

          <h2>Add something Zoya should remember</h2>
        </div>

        {onCancel && (
          <button
            type="button"
            className="memory-modal-close"
            onClick={onCancel}
            disabled={isSaving}
            aria-label="Close"
          >
            ×
          </button>
        )}
      </div>

      <div className="memory-form-grid">
        <label>
          <span>Key</span>

          <input
            type="text"
            value={key}
            onChange={(event) =>
              setKey(event.target.value)
            }
            placeholder="e.g. favorite_color"
            maxLength={100}
            disabled={isSaving}
          />
        </label>

        <label>
          <span>Category</span>

          <input
            type="text"
            value={category}
            onChange={(event) =>
              setCategory(event.target.value)
            }
            placeholder="e.g. preference"
            maxLength={100}
            disabled={isSaving}
          />
        </label>
      </div>

      <label>
        <span>Value</span>

        <textarea
          value={value}
          onChange={(event) =>
            setValue(event.target.value)
          }
          placeholder="What should Zoya remember?"
          rows={4}
          maxLength={1000}
          disabled={isSaving}
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

      <div className="memory-create-actions">
        {onCancel && (
          <button
            type="button"
            className="memory-secondary-button"
            onClick={onCancel}
            disabled={isSaving}
          >
            Cancel
          </button>
        )}

        <button
          type="submit"
          className="memory-primary-button"
          disabled={
            isSaving ||
            !key.trim() ||
            !value.trim() ||
            !category.trim()
          }
        >
          {isSaving
            ? "Saving..."
            : "Add Memory"}
        </button>
      </div>
    </form>
  );
}

export default MemoryCreateForm;