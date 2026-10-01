import { useCallback, useEffect, useState } from "react";

import {
  THEMES,
  THEME_STORAGE_KEY,
  applyTheme,
  getStoredTheme,
} from "../theme/theme";

const THEME_SWITCH_TRANSITION_MS = 260;

export const useTheme = () => {
  const [theme, setThemeState] = useState(() => getStoredTheme());

  const setTheme = useCallback((nextTheme) => {
    if (!THEMES.includes(nextTheme)) {
      return;
    }

    const root = document.documentElement;
    root.classList.add("theme-switching");
    applyTheme(nextTheme);
    setThemeState(nextTheme);

    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    } catch {
      // Ignore storage failures. The active theme still applies for this session.
    }

    window.setTimeout(() => {
      root.classList.remove("theme-switching");
    }, THEME_SWITCH_TRANSITION_MS);
  }, []);

  useEffect(() => {
    applyTheme(theme);

    if (theme !== "system" || !window.matchMedia) {
      return undefined;
    }

    const mediaQuery = window.matchMedia("(prefers-color-scheme: light)");
    const handleSystemThemeChange = () => applyTheme("system");

    mediaQuery.addEventListener?.("change", handleSystemThemeChange);

    return () => {
      mediaQuery.removeEventListener?.("change", handleSystemThemeChange);
    };
  }, [theme]);

  return { theme, setTheme };
};
