export const THEME_STORAGE_KEY = "zoya:theme";

export const THEMES = ["dark", "light", "system"];

const DEFAULT_THEME = "dark";

const isValidTheme = (value) => THEMES.includes(value);

export const getStoredTheme = () => {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isValidTheme(stored) ? stored : DEFAULT_THEME;
  } catch {
    return DEFAULT_THEME;
  }
};

export const getSystemTheme = () => {
  if (typeof window === "undefined" || !window.matchMedia) {
    return DEFAULT_THEME;
  }

  return window.matchMedia("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
};

export const getEffectiveTheme = (theme) =>
  theme === "system" ? getSystemTheme() : theme;

export const applyTheme = (theme) => {
  const root = document.documentElement;
  const safeTheme = isValidTheme(theme) ? theme : DEFAULT_THEME;
  const effectiveTheme = getEffectiveTheme(safeTheme);

  root.dataset.theme = safeTheme;
  root.dataset.themeMode = effectiveTheme;
  root.style.colorScheme = effectiveTheme;

  return effectiveTheme;
};
