/**
 * Browser-only LLM credentials.
 *
 * Users may bring their own OpenAI-compatible API key, base URL, and model.
 * These live ONLY in the browser (localStorage) and are attached to each
 * pipeline trigger request body. They are never persisted server-side and
 * never written to backend logs — the backend uses them for a single run and
 * then discards them, falling back to the server's own key when absent.
 */

export interface LlmCreds {
  apiKey: string;
  baseUrl: string;
  model: string;
}

export const LLM_CREDS_STORAGE_KEY = "marketpulse-llm-creds";

export const EMPTY_LLM_CREDS: LlmCreds = {
  apiKey: "",
  baseUrl: "",
  model: "",
};

/** Read the saved credentials from localStorage. Safe on the server (SSR). */
export function readLlmCreds(): LlmCreds {
  if (typeof window === "undefined") return { ...EMPTY_LLM_CREDS };
  try {
    const raw = window.localStorage.getItem(LLM_CREDS_STORAGE_KEY);
    if (!raw) return { ...EMPTY_LLM_CREDS };
    const parsed = JSON.parse(raw) as Partial<LlmCreds>;
    return {
      apiKey: typeof parsed.apiKey === "string" ? parsed.apiKey : "",
      baseUrl: typeof parsed.baseUrl === "string" ? parsed.baseUrl : "",
      model: typeof parsed.model === "string" ? parsed.model : "",
    };
  } catch {
    return { ...EMPTY_LLM_CREDS };
  }
}

/** Persist credentials to localStorage (browser only). */
export function writeLlmCreds(creds: LlmCreds): void {
  if (typeof window === "undefined") return;
  const trimmed: LlmCreds = {
    apiKey: creds.apiKey.trim(),
    baseUrl: creds.baseUrl.trim(),
    model: creds.model.trim(),
  };
  if (!trimmed.apiKey && !trimmed.baseUrl && !trimmed.model) {
    window.localStorage.removeItem(LLM_CREDS_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(LLM_CREDS_STORAGE_KEY, JSON.stringify(trimmed));
}

/** Clear any saved credentials. */
export function clearLlmCreds(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(LLM_CREDS_STORAGE_KEY);
}

/**
 * Merge the current browser credentials into a pipeline trigger body. Only
 * non-empty fields are attached so default runs keep using the server key.
 */
export function withLlmCreds<T extends object>(body: T): T {
  const creds = readLlmCreds();
  const extra: Record<string, string> = {};
  if (creds.apiKey) extra.api_key = creds.apiKey;
  if (creds.baseUrl) extra.base_url = creds.baseUrl;
  if (creds.model) extra.model = creds.model;
  if (Object.keys(extra).length === 0) return body;
  return { ...body, ...extra };
}
