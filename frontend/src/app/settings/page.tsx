"use client";

import { useEffect, useState } from "react";
import { KeyRound, Save, Trash2, Eye, EyeOff } from "lucide-react";

import {
  EMPTY_LLM_CREDS,
  readLlmCreds,
  writeLlmCreds,
  clearLlmCreds,
  type LlmCreds,
} from "@/lib/llm-creds";

export default function SettingsPage() {
  const [creds, setCreds] = useState<LlmCreds>(EMPTY_LLM_CREDS);
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setCreds(readLlmCreds());
  }, []);

  function update<K extends keyof LlmCreds>(key: K, value: string) {
    setCreds((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  }

  function handleSave() {
    writeLlmCreds(creds);
    setCreds(readLlmCreds());
    setSaved(true);
  }

  function handleClear() {
    clearLlmCreds();
    setCreds({ ...EMPTY_LLM_CREDS });
    setSaved(false);
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <header className="mb-6 flex items-center gap-3">
        <KeyRound className="h-6 w-6" style={{ color: "var(--al-gold)" }} />
        <div>
          <h1 className="text-xl font-semibold">Your API Keys &amp; Model</h1>
          <p className="text-sm" style={{ color: "var(--al-on-surface-muted)" }}>
            Bring your own LLM provider for analysis runs.
          </p>
        </div>
      </header>

      <section
        className="rounded-2xl border p-5"
        style={{ borderColor: "var(--al-outline)" }}
      >
        <div
          className="mb-5 rounded-xl border px-4 py-3 text-xs leading-relaxed"
          style={{
            borderColor: "var(--al-outline)",
            color: "var(--al-on-surface-muted)",
          }}
        >
          These credentials are stored <strong>only in this browser</strong> and
          attached to each run you start. They are never saved on the server and
          never written to logs. Leave them blank to use the platform&apos;s
          default provider. The tokens you spend are billed to your own account.
        </div>

        <label className="mb-4 block">
          <span className="mb-1 block text-sm font-medium">API key</span>
          <div className="flex items-center gap-2">
            <input
              type={showKey ? "text" : "password"}
              value={creds.apiKey}
              onChange={(e) => update("apiKey", e.target.value)}
              placeholder="sk-..."
              autoComplete="off"
              spellCheck={false}
              className="w-full rounded-lg border px-3 py-2 text-sm"
              style={{ borderColor: "var(--al-outline)", background: "transparent" }}
            />
            <button
              type="button"
              onClick={() => setShowKey((s) => !s)}
              className="rounded-lg border p-2"
              style={{ borderColor: "var(--al-outline)" }}
              aria-label={showKey ? "Hide API key" : "Show API key"}
            >
              {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </label>

        <label className="mb-4 block">
          <span className="mb-1 block text-sm font-medium">
            Base URL <span style={{ color: "var(--al-on-surface-muted)" }}>(optional)</span>
          </span>
          <input
            type="text"
            value={creds.baseUrl}
            onChange={(e) => update("baseUrl", e.target.value)}
            placeholder="https://openrouter.ai/api/v1"
            autoComplete="off"
            spellCheck={false}
            className="w-full rounded-lg border px-3 py-2 text-sm"
            style={{ borderColor: "var(--al-outline)", background: "transparent" }}
          />
          <span className="mt-1 block text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
            Any OpenAI-compatible endpoint. Defaults to the platform provider.
          </span>
        </label>

        <label className="mb-5 block">
          <span className="mb-1 block text-sm font-medium">
            Model <span style={{ color: "var(--al-on-surface-muted)" }}>(optional)</span>
          </span>
          <input
            type="text"
            value={creds.model}
            onChange={(e) => update("model", e.target.value)}
            placeholder="e.g. openai/gpt-4o-mini"
            autoComplete="off"
            spellCheck={false}
            className="w-full rounded-lg border px-3 py-2 text-sm"
            style={{ borderColor: "var(--al-outline)", background: "transparent" }}
          />
          <span className="mt-1 block text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
            When you supply your own key, you can name any model your provider
            offers — the curated allow-list no longer applies.
          </span>
        </label>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleSave}
            className="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold"
            style={{ background: "var(--al-gold)", color: "var(--al-gold-on)" }}
          >
            <Save className="h-4 w-4" />
            Save
          </button>
          <button
            type="button"
            onClick={handleClear}
            className="inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium"
            style={{ borderColor: "var(--al-outline)" }}
          >
            <Trash2 className="h-4 w-4" />
            Clear
          </button>
          {saved && (
            <span className="text-sm" style={{ color: "var(--al-positive, #16a34a)" }}>
              Saved to this browser.
            </span>
          )}
        </div>
      </section>
    </main>
  );
}
