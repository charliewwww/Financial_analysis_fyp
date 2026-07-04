"use client";

import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AlertCircle, LinkIcon, Loader2, MessageSquareText, Send, ShieldCheck } from "lucide-react";

import { askSignalEvidence } from "@/lib/api";
import type { SignalChatCitation, SignalChatTurn } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Pill } from "@/components/primitives";
import { cn } from "@/lib/utils";

const DEFAULT_SUGGESTIONS = [
  "What changed?",
  "What would invalidate this?",
  "Which supplier or customer is affected?",
  "Which claims are verified?",
];

interface LocalMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: SignalChatCitation[];
  limitations?: string[];
  grounded?: boolean;
}

interface SignalEvidenceChatProps {
  cardId?: number | null;
  ticker?: string;
  title?: string;
  decisionContext?: string | null;
  suggestedQuestions?: string[];
  className?: string;
  compact?: boolean;
  showHeader?: boolean;
}

function nextId(role: LocalMessage["role"]): string {
  return `${role}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function toHistory(messages: LocalMessage[]): SignalChatTurn[] {
  return messages.slice(-6).map((message) => ({
    role: message.role,
    content: message.content,
  }));
}

function CitationList({ citations }: { citations: SignalChatCitation[] | undefined }) {
  if (!citations?.length) return null;

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {citations.map((citation) => {
        const content = (
          <>
            {citation.url ? <LinkIcon className="size-3" aria-hidden /> : null}
            <span>{citation.label}</span>
          </>
        );
        return citation.url ? (
          <a
            key={`${citation.label}-${citation.url}`}
            href={citation.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold hover:bg-muted/50"
            style={{ borderColor: "var(--al-outline)", color: "var(--al-gold)" }}
          >
            {content}
          </a>
        ) : (
          <span
            key={citation.label}
            className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold"
            style={{ borderColor: "var(--al-outline)", color: "var(--al-on-surface-muted)" }}
          >
            {content}
          </span>
        );
      })}
    </div>
  );
}

function Limitations({ limitations }: { limitations: string[] | undefined }) {
  if (!limitations?.length) return null;

  return (
    <div className="mt-3 space-y-1.5">
      {limitations.slice(0, 3).map((limitation) => (
        <div key={limitation} className="flex gap-2 text-xs leading-5 text-amber-700 dark:text-amber-300">
          <AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>{limitation}</span>
        </div>
      ))}
    </div>
  );
}

export function SignalEvidenceChat({
  cardId,
  ticker,
  title = "Ask this evidence",
  decisionContext,
  suggestedQuestions = DEFAULT_SUGGESTIONS,
  className,
  compact = false,
  showHeader = true,
}: SignalEvidenceChatProps) {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [suggestions, setSuggestions] = useState(suggestedQuestions);
  const disabled = cardId == null;

  useEffect(() => {
    setMessages([]);
    setDraft("");
  }, [cardId]);

  useEffect(() => {
    setSuggestions(suggestedQuestions);
  }, [suggestedQuestions]);

  const mutation = useMutation({
    mutationFn: async ({ question, history }: { question: string; history: SignalChatTurn[] }) => {
      if (cardId == null) throw new Error("No signal card selected.");
      return askSignalEvidence(cardId, {
        question,
        history,
        context: decisionContext ?? null,
      });
    },
    onSuccess: (response) => {
      setMessages((current) => [
        ...current,
        {
          id: nextId("assistant"),
          role: "assistant",
          content: response.answer,
          citations: response.citations,
          limitations: response.limitations,
          grounded: response.grounded,
        },
      ]);
      if (response.suggested_questions.length) setSuggestions(response.suggested_questions);
    },
  });

  const visibleSuggestions = useMemo(
    () => suggestions.filter((item) => item.trim()).slice(0, compact ? 3 : 4),
    [compact, suggestions]
  );

  function ask(question: string) {
    const trimmed = question.trim();
    if (!trimmed || disabled || mutation.isPending) return;
    const history = toHistory(messages);
    setMessages((current) => [
      ...current,
      { id: nextId("user"), role: "user", content: trimmed },
    ]);
    setDraft("");
    mutation.mutate({ question: trimmed, history });
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    ask(draft);
  }

  return (
    <section className={cn("al-glass p-5", className)}>
      {showHeader ? (
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="al-eyebrow">Evidence chat</div>
            <h2 className="mt-1 text-lg">{title}</h2>
            {ticker ? (
              <p className="mt-1 font-mono text-xs" style={{ color: "var(--al-on-surface-muted)" }}>
                {ticker}
              </p>
            ) : null}
          </div>
          <Pill variant={disabled ? "gray" : "gold"}>
            <ShieldCheck className="size-3" aria-hidden />
            evidence scoped
          </Pill>
        </div>
      ) : null}

      <div
        className={cn(
          "space-y-3 overflow-y-auto rounded-xl border",
          showHeader && "mt-4",
          compact ? "max-h-[240px] min-h-[120px] p-2" : "max-h-[480px] min-h-[220px] p-3"
        )}
        style={{ borderColor: "var(--al-outline)" }}
        role="log"
        aria-live="polite"
        aria-label="Evidence chat messages"
      >
        {messages.length ? (
          messages.map((message) => (
            <div
              key={message.id}
              className={cn(
                "max-w-[92%] rounded-xl border px-3 py-2 text-sm leading-6",
                message.role === "user" ? "ml-auto bg-muted/45" : "mr-auto bg-background/45"
              )}
              style={{ borderColor: "var(--al-outline)" }}
            >
              <div className="whitespace-pre-wrap">{message.content}</div>
              {message.role === "assistant" ? <CitationList citations={message.citations} /> : null}
              {message.role === "assistant" ? <Limitations limitations={message.limitations} /> : null}
            </div>
          ))
        ) : (
          <div className={cn("flex h-full flex-col items-center justify-center gap-3 text-center", compact ? "min-h-[104px]" : "min-h-[160px]")}> 
            <MessageSquareText className="size-8" aria-hidden style={{ color: "var(--al-gold)" }} />
            <p className="max-w-sm text-sm leading-6" style={{ color: "var(--al-on-surface-muted)" }}>
              {disabled
                ? "A current signal card is needed before chat can answer from evidence."
                : "Ask about the catalyst, risk, sources, claims, or supply-chain ripple attached to this card."}
            </p>
          </div>
        )}
        {mutation.isPending ? (
          <div className="mr-auto inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm" style={{ borderColor: "var(--al-outline)", color: "var(--al-on-surface-muted)" }}>
            <Loader2 className="size-4 animate-spin" aria-hidden />
            Checking evidence
          </div>
        ) : null}
      </div>

      {mutation.isError ? (
        <div role="alert" className="mt-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm leading-6 text-red-800 dark:border-red-500/25 dark:bg-red-500/10 dark:text-red-100">
          {mutation.error instanceof Error ? mutation.error.message : "Evidence chat failed."}
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        {visibleSuggestions.map((question) => (
          <button
            key={question}
            type="button"
            onClick={() => ask(question)}
            disabled={disabled || mutation.isPending}
            className="rounded-full border px-3 py-1.5 text-xs font-semibold transition hover:bg-muted/50 disabled:pointer-events-none disabled:opacity-50"
            style={{ borderColor: "var(--al-outline)" }}
          >
            {question}
          </button>
        ))}
      </div>

      <form onSubmit={submit} className="mt-3 flex flex-col gap-2 sm:flex-row">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          disabled={disabled || mutation.isPending}
          className="h-10 min-w-0 flex-1 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring disabled:opacity-60"
          placeholder={disabled ? "No signal card selected" : "Ask a question about this evidence"}
          aria-label="Evidence question"
        />
        <Button type="submit" className="al-gold-gradient self-start rounded-full px-4 sm:self-auto" disabled={disabled || mutation.isPending || !draft.trim()}>
          <Send data-icon="inline-start" className="size-4" aria-hidden />
          Ask
        </Button>
      </form>
    </section>
  );
}