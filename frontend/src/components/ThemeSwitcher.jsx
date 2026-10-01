import { useEffect, useRef, useState } from "react";

const OPTIONS = [
  { value: "dark", label: "Dark", icon: "☾" },
  { value: "light", label: "Light", icon: "☀" },
  { value: "system", label: "System", icon: "◐" },
];

function ThemeSwitcher({ theme, onThemeChange }) {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef(null);

  const activeOption =
    OPTIONS.find((option) => option.value === theme) || OPTIONS[0];

  useEffect(() => {
    const handlePointerDown = (event) => {
      if (!menuRef.current?.contains(event.target)) {
        setIsOpen(false);
      }
    };

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const handleThemeChange = (value) => {
    onThemeChange(value);
    setIsOpen(false);
  };

  return (
    <div className={`theme-menu ${isOpen ? "open" : ""}`} ref={menuRef}>
      <button
        type="button"
        className="theme-menu-trigger"
        onClick={() => setIsOpen((previous) => !previous)}
        aria-label="Open theme menu"
        aria-haspopup="menu"
        aria-expanded={isOpen}
        title="Theme"
      >
        <span aria-hidden="true">•••</span>
      </button>

      {isOpen && (
        <div className="theme-menu-popover" role="menu" aria-label="Theme">
          <div className="theme-menu-title">Theme</div>

          {OPTIONS.map((option) => {
            const isActive = theme === option.value;

            return (
              <button
                key={option.value}
                type="button"
                className={`theme-menu-option ${isActive ? "active" : ""}`}
                onClick={() => handleThemeChange(option.value)}
                role="menuitemradio"
                aria-checked={isActive}
              >
                <span className="theme-menu-option-icon" aria-hidden="true">
                  {option.icon}
                </span>
                <span className="theme-menu-option-label">
                  {option.label}
                </span>
                {isActive && (
                  <span className="theme-menu-option-check" aria-hidden="true">
                    ✓
                  </span>
                )}
              </button>
            );
          })}

          <div className="theme-menu-current">
            Using {activeOption.label}
          </div>
        </div>
      )}
    </div>
  );
}

export default ThemeSwitcher;
