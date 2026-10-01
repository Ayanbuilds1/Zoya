import { useEffect } from "react";

const isEditableTarget = (target) => {
  if (!(target instanceof HTMLElement)) {
    return false;
  }

  return (
    target.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)
  );
};

export function useKeyboardShortcuts({
  chatSearchInputRef,
  composerRef,
  onEscape,
}) {
  useEffect(() => {
    const handleGlobalKeyDown = (event) => {
      const key = event.key.toLowerCase();
      const modifier = event.ctrlKey || event.metaKey;

      if (modifier && key === "k") {
        event.preventDefault();
        chatSearchInputRef.current?.focus();
        chatSearchInputRef.current?.select?.();
        return;
      }

      if (modifier && event.key === "/") {
        event.preventDefault();
        composerRef.current?.focus();
        return;
      }

      if (event.key === "Escape") {
        if (typeof onEscape === "function") {
          onEscape();
        }

        if (isEditableTarget(event.target)) {
          return;
        }

        event.preventDefault();
      }
    };

    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => {
      window.removeEventListener("keydown", handleGlobalKeyDown);
    };
  }, [chatSearchInputRef, composerRef, onEscape]);
}
