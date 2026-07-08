"use client";

import * as React from "react";
import { Suspense } from "react";
import { useMutation } from "@tanstack/react-query";
import { useQuery } from "@tanstack/react-query";

import {
  ApiError,
  fetchAuthConfig,
  googleLoginUrl,
  requestSignup,
  type SignupResult,
} from "@/lib/api";
import { BrandMark } from "@/components/BrandMark";

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.71-1.57 2.68-3.89 2.68-6.62z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18z"
      />
      <path
        fill="#FBBC05"
        d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z"
      />
    </svg>
  );
}

function SignupInner() {
  const [email, setEmail] = React.useState("");
  const [name, setName] = React.useState("");
  const [result, setResult] = React.useState<SignupResult | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const { data: cfg } = useQuery({
    queryKey: ["auth", "config"],
    queryFn: fetchAuthConfig,
    retry: false,
    staleTime: 300_000,
  });
  const configured = cfg?.google_configured ?? true;

  const signup = useMutation({
    mutationFn: () =>
      requestSignup({
        email: email.trim().toLowerCase(),
        name: name.trim() || null,
      }),
    onSuccess: (data) => {
      setResult(data);
      setError(null);
      setEmail("");
      setName("");
    },
    onError: (e: unknown) =>
      setError(
        e instanceof ApiError
          ? e.detail
          : "Something went wrong. Please try again."
      ),
  });

  return (
    <div className="flex min-h-[70vh] items-center justify-center px-4">
      <div className="al-glass w-full max-w-md p-8 text-center space-y-5">
        <div className="flex flex-col items-center gap-3">
          <BrandMark size={40} aria-hidden />
          <div>
            <div className="al-eyebrow">Private beta</div>
            <h1 className="text-2xl font-heading font-extrabold tracking-tight">
              Create your account
            </h1>
          </div>
        </div>

        <p
          className="text-sm"
          style={{ color: "var(--al-on-surface-muted)" }}
        >
          MarketPulse is invite-only. Request access with your email, or sign
          in with Google — an administrator will review your request.
        </p>

        {result && (
          <div
            className="rounded-lg border border-border px-4 py-3 text-sm text-left"
            style={{
              color:
                result.status === "invited"
                  ? "var(--al-on-surface)"
                  : "var(--al-on-surface-muted)",
            }}
          >
            {result.message}
          </div>
        )}

        {error && (
          <div
            className="rounded-lg border border-border px-4 py-3 text-sm text-left"
            style={{ color: "var(--al-danger, #ef4444)" }}
          >
            {error}
          </div>
        )}

        {/* ── Google OAuth signup ─────────────────────────────── */}
        {configured && (
          <>
            <a
              href={googleLoginUrl()}
              className="inline-flex w-full items-center justify-center gap-3 rounded-full border border-border bg-background px-5 py-3 text-sm font-semibold transition-colors hover:bg-muted/40"
            >
              <GoogleIcon />
              Sign up with Google
            </a>

            <div className="flex items-center gap-3">
              <div
                className="h-px flex-1"
                style={{ background: "var(--al-outline)" }}
              />
              <span
                className="text-xs"
                style={{ color: "var(--al-on-surface-muted)" }}
              >
                or
              </span>
              <div
                className="h-px flex-1"
                style={{ background: "var(--al-outline)" }}
              />
            </div>
          </>
        )}

        {/* ── Email-only signup ───────────────────────────────── */}
        <form
          className="space-y-3 text-left"
          onSubmit={(e) => {
            e.preventDefault();
            if (email.trim()) signup.mutate();
          }}
        >
          <div className="space-y-1">
            <label
              htmlFor="signup-name"
              className="text-xs font-medium"
              style={{ color: "var(--al-on-surface-muted)" }}
            >
              Name (optional)
            </label>
            <input
              id="signup-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
              maxLength={120}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </div>
          <div className="space-y-1">
            <label
              htmlFor="signup-email"
              className="text-xs font-medium"
              style={{ color: "var(--al-on-surface-muted)" }}
            >
              Email
            </label>
            <input
              id="signup-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.com"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </div>
          <button
            type="submit"
            className="al-gold-gradient w-full rounded-full px-5 py-3 text-sm font-semibold disabled:opacity-50"
            disabled={signup.isPending}
          >
            {signup.isPending ? "Submitting…" : "Request access"}
          </button>
        </form>

        <p
          className="text-xs"
          style={{ color: "var(--al-on-surface-muted)" }}
        >
          By continuing you agree this is a research tool and not financial
          advice.
        </p>

        <div
          className="text-sm"
          style={{ color: "var(--al-on-surface-muted)" }}
        >
          Already have an account?{" "}
          <a
            href="/login"
            className="font-semibold underline underline-offset-4"
            style={{ color: "var(--al-on-surface)" }}
          >
            Sign in
          </a>
        </div>
      </div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense fallback={<div className="min-h-[70vh]" />}>
      <SignupInner />
    </Suspense>
  );
}