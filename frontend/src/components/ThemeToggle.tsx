"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark";

function readInitialTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  const stored = (localStorage.getItem("marketpulse-theme") ?? localStorage.getItem("alpha-lens-theme")) as Theme | null;
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(readInitialTheme);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
    localStorage.setItem("marketpulse-theme", theme);
  }, [theme]);

  return (
    <button
      aria-label="Toggle theme"
      title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      className="text-sm rounded-md border border-border px-2 py-1 hover:bg-muted/40 transition-colors"
      suppressHydrationWarning
    >
      {theme === "dark" ? "☾" : "☀"}
    </button>
  );
}
