import type { ThemeChoice } from "./types";

const KEY = "agentic-rag-theme";

export function loadThemeChoice(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    /* ignore */
  }
  return "system";
}

function resolve(choice: ThemeChoice): "light" | "dark" {
  if (choice === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return choice;
}

export function applyTheme(choice: ThemeChoice): void {
  document.documentElement.dataset.theme = resolve(choice);
  try {
    localStorage.setItem(KEY, choice);
  } catch {
    /* ignore */
  }
}

/** Re-apply when the OS theme changes and the user is on "system". */
export function watchSystemTheme(getChoice: () => ThemeChoice): () => void {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const handler = () => {
    if (getChoice() === "system") applyTheme("system");
  };
  mq.addEventListener("change", handler);
  return () => mq.removeEventListener("change", handler);
}
