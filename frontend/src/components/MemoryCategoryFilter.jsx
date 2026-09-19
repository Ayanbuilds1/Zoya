function MemoryCategoryFilter({
  categories,
  selectedCategory,
  onCategoryChange,
}) {
  return (
    <div className="memory-category-filter">
      <button
        type="button"
        className={`memory-filter-button ${
          selectedCategory === ""
            ? "active"
            : ""
        }`}
        onClick={() => onCategoryChange("")}
      >
        All
      </button>

      {categories.map((item) => (
        <button
          type="button"
          className={`memory-filter-button ${
            selectedCategory === item.category
              ? "active"
              : ""
          }`}
          key={item.category}
          onClick={() =>
            onCategoryChange(item.category)
          }
        >
          {item.category}
          <span>{item.count}</span>
        </button>
      ))}
    </div>
  );
}

export default MemoryCategoryFilter;