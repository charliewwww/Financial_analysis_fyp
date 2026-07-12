"use client";

import { Suspense } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchAuthConfig, googleLoginUrl } from "@/lib/api";
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
  const { data: cfg } = useQuery({
    queryKey: ["auth", "config"],
    queryFn: fetchAuthConfig,
    retry: false,
    staleTime: 300_000,
  });
  const configured = cfg?.google_configured ?? true;

  return (
    <div className="flex min-h-[70vh] items-center justify-center px-4">
      <div className="al-glass w-full max-w-md p-8 text-center space-y-5">
        <div className="flex flex-col items-center gap-3">
          <BrandMark size={40} aria-hidden />
          <div>
            <div className="al-eyebrow">Get started</div>
            <h1 className="text-2xl font-heading font-extrabold tracking-tight">
              Create your account
            </h1>
          </div>
        </div>

        <p
          className="text-sm"
          style={{ color: "var(--al-on-surface-muted)" }}
        >
          Sign in with your Google account to get your own private workspace —
          no invitation or approval needed.
        </p>


        {configured ? (
          <a
            href={googleLoginUrl()}
            className="inline-flex w-full items-center justify-center gap-3 rounded-full border border-border bg-background px-5 py-3 text-sm font-semibold transition-colors hover:bg-muted/40"
          >
            <GoogleIcon />
            Sign up with Google
          </a>
        ) : (
          <div
            className="text-sm"
            style={{ color: "var(--al-on-surface-muted)" }}
          >
            Google sign-in isn't configured yet. Please contact the
            administrator.
          </div>
        )}


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