import MemoryItem from "./MemoryItem";

function MemoryList({
  memories,
  isLoading,
  onEdit,
  onDelete,
}) {
  if (isLoading) {
    return (
      <div className="memory-loading">
        <div className="memory-loading-spinner"></div>
        <span>Loading memories...</span>
      </div>
    );
  }

  if (memories.length === 0) {
    return (
      <div className="memory-empty">
        <div className="memory-empty-icon">
          🧠
        </div>

        <h3>No memories found</h3>

        <p>
          Zoya doesn't have any memories in this
          category yet.
        </p>
      </div>
    );
  }

  return (
    <div className="memory-list">
      {memories.map((memory) => (
        <MemoryItem
          key={memory.memory_id}
          memory={memory}
          onEdit={onEdit}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}

export default MemoryList;