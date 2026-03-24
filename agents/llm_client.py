"""
LLM Client — talks to GLM-4.7-Flash via OpenRouter (dev) or Ollama (local).

Dual-mode architecture:
    LLM_PROVIDER=openrouter  → OpenRouter API (fast dev iteration, free tier)
    LLM_PROVIDER=ollama      → Local Ollama server (production, $0/month, full privacy)

Both use the OpenAI-compatible API format — zero code changes needed to switch.
Toggle via LLM_PROVIDER in your .env file.

Observability:
    If LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set in .env, all LLM
    calls are automatically traced via Langfuse's OpenAI wrapper (drop-in).
    See https://langfuse.com/docs/integrations/openai for details.
"""

from __future__ import annotations

import logging
import threading
import time as _time
import random as _random
from dataclasses import dataclass
from config.settings import (
    LLM_API_KEY, LLM_BASE_URL, REASONING_MODEL, FAST_MODEL, LLM_PROVIDER,
    LANGFUSE_ENABLED, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST,
    LLM_MAX_RETRIES, LLM_RETRY_BASE_DELAY,
)

# ── OpenAI client: auto-instrumented when Langfuse is configured ──
# Langfuse provides a drop-in OpenAI replacement that wraps every
# chat.completions.create() call with automatic tracing (prompt,
# response, tokens, latency, cost).  If Langfuse keys are not set,
# we fall back to the plain OpenAI SDK — zero overhead.
if LANGFUSE_ENABLED:
    from langfuse.openai import OpenAI  # auto-traced client
else:
    from openai import OpenAI  # standard client

logger = logging.getLogger(__name__)

# Timeout for LLM calls (seconds). Free-tier reasoning models can be slow.
LLM_TIMEOUT = 180  # 3 minutes max per call


# ── Graceful cancellation ──────────────────────────────────────────
# Any thread can call request_cancellation() to stop all in-flight and
# future LLM calls.  The event is checked before every API request and
# during retry sleeps, raising PipelineCancelled immediately.

_cancel_event = threading.Event()


class PipelineCancelled(Exception):
    """Raised when cancellation is requested (Ctrl+C or UI cancel button)."""
    pass


def request_cancellation():
    """Signal all LLM calls to abort as soon as possible."""
    _cancel_event.set()
    logger.warning("Cancellation requested — aborting LLM calls")


def reset_cancellation():
    """Clear the cancellation flag (call before starting a new run)."""
    _cancel_event.clear()


def is_cancelled() -> bool:
    """Check whether cancellation has been requested."""
    return _cancel_event.is_set()


def _check_cancelled():
    """Raise PipelineCancelled if stop was requested."""
    if _cancel_event.is_set():
        raise PipelineCancelled("Pipeline cancelled by user")

# ── Langfuse setup ────────────────────────────────────────────────
# When LANGFUSE_ENABLED=True the Langfuse OpenAI wrapper automatically
# reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST from
# env vars (already loaded by config.settings → python-dotenv).
# We also export a helper so nodes can attach session/trace metadata.
if LANGFUSE_ENABLED:
    import os
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", LANGFUSE_PUBLIC_KEY)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", LANGFUSE_SECRET_KEY)
    os.environ.setdefault("LANGFUSE_HOST", LANGFUSE_HOST)
    logger.info("Langfuse tracing ENABLED → %s", LANGFUSE_HOST)
else:
    logger.info("Langfuse tracing disabled (no keys configured)")


# ── Structured LLM response ───────────────────────────────────────
# Every LLM call now returns a rich object, not just a string.
# Old callers still work — str(result) or using it in f-strings
# returns the content. But nodes can now inspect .error, .tokens, etc.

@dataclass
class LLMResponse:
    """Structured response from an LLM call."""
    content: str = ""
    error: str | None = None
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def ok(self) -> bool:
        return self.error is None

    def __str__(self) -> str:
        """Backward-compatible: using as string returns the content."""
        return self.content

    def __bool__(self) -> bool:
        return bool(self.content)


# ── Singleton client (connection pooling) ─────────────────────────
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Return a cached OpenAI client — reuses HTTP connections across calls."""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            timeout=LLM_TIMEOUT,
        )
    return _client


# ── Retryable exceptions ──────────────────────────────────────────
_RETRYABLE_ERRORS = (
    "rate_limit",
    "timeout",
    "502",
    "503",
    "504",
    "overloaded",
    "connection",
)


def _is_retryable(exc: Exception) -> bool:
    """Check if an exception is transient and worth retrying."""
    msg = str(exc).lower()
    return any(kw in msg for kw in _RETRYABLE_ERRORS)


def _retry_delay(attempt: int) -> float:
    """Exponential backoff with jitter: base * 2^attempt ± 25%."""
    delay = LLM_RETRY_BASE_DELAY * (2 ** attempt)
    jitter = delay * 0.25 * (2 * _random.random() - 1)  # ±25%
    return delay + jitter


# ── Health check ──────────────────────────────────────────────────

class LLMHealthCheckError(Exception):
    """Raised when the LLM is unreachable — fails fast before data fetch."""
    pass


def check_llm_health(timeout: int = 15) -> bool:
    """
    Quick pre-flight check: can we reach the LLM?

    Sends a trivial prompt with a short timeout. If it fails, the
    pipeline should abort immediately instead of spending 3+ minutes
    fetching data that can never be analyzed.

    Returns True if healthy. Raises LLMHealthCheckError if not.
    """
    if LLM_PROVIDER == "openrouter" and not LLM_API_KEY:
        raise LLMHealthCheckError(
            "OPENROUTER_API_KEY is not set. Add it to your .env file.\n"
            "  Get a free key at: https://openrouter.ai/keys\n"
            "  Or switch to local Ollama: set LLM_PROVIDER=ollama in .env"
        )

    try:
        client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            timeout=timeout,
        )
        # GLM-4.7-Flash (and similar reasoning models) consume "reasoning
        # tokens" from the max_tokens budget before producing visible output.
        # A trivial prompt may use ~70-100 reasoning tokens, so we need
        # max_tokens >> expected content length.
        response = client.chat.completions.create(
            model=FAST_MODEL,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=300,
            temperature=0,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            # One retry — sometimes the model needs a nudge
            response = client.chat.completions.create(
                model=FAST_MODEL,
                messages=[{"role": "user", "content": "Say hello"}],
                max_tokens=500,
                temperature=0.5,
            )
            content = (response.choices[0].message.content or "").strip()
        if not content:
            raise LLMHealthCheckError(
                f"LLM returned empty response during health check.\n"
                f"  Provider: {LLM_PROVIDER} | Model: {FAST_MODEL}\n"
                f"  The model may be overloaded or quota exceeded.\n"
                f"  Try again in a moment."
            )
        logger.info("LLM health check passed (%s via %s)", FAST_MODEL, LLM_PROVIDER)
        return True
    except LLMHealthCheckError:
        raise
    except Exception as e:
        raise LLMHealthCheckError(
            f"Cannot reach LLM at {LLM_BASE_URL}.\n"
            f"  Provider: {LLM_PROVIDER} | Model: {FAST_MODEL}\n"
            f"  Error: {e}\n"
            f"  {'Check your API key and internet connection.' if LLM_PROVIDER == 'openrouter' else 'Is Ollama running? Start with: ollama serve'}"
        ) from e


# ── Main LLM call ─────────────────────────────────────────────────

def call_llm(
    prompt: str,
    system_prompt: str = "",
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    *,
    langfuse_name: str | None = None,
    langfuse_metadata: dict | None = None,
    langfuse_trace_id: str | None = None,
) -> str:
    """
    Send a prompt to the LLM and return the response text.

    Args:
        prompt: The user message / main prompt
        system_prompt: System-level instructions (role, constraints)
        model: Which model to use (defaults to REASONING_MODEL)
        temperature: Creativity (0 = deterministic, 1 = creative)
        max_tokens: Max response length
        langfuse_name: Generation name in Langfuse (e.g. "summarize — AI & Semiconductors")
        langfuse_metadata: Extra key/value pairs attached to the generation
        langfuse_trace_id: Parent trace ID — groups this call under a sector-level trace

    Returns:
        The LLM's response as a string.
        On error, raises an exception instead of silently returning
        an error string (which would get saved as the "analysis").
    """
    client = _get_client()
    model = model or REASONING_MODEL

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # Langfuse kwargs — the OpenAiArgsExtractor in langfuse.openai extracts
    # these before passing remaining kwargs to the real OpenAI SDK.
    lf_kwargs: dict = {}
    if LANGFUSE_ENABLED:
        if langfuse_name:
            lf_kwargs["name"] = langfuse_name
        if langfuse_metadata:
            lf_kwargs["metadata"] = langfuse_metadata
        if langfuse_trace_id:
            lf_kwargs["trace_id"] = langfuse_trace_id

    last_exc: Exception | None = None
    for attempt in range(LLM_MAX_RETRIES + 1):
        _check_cancelled()  # bail out before making the API call
        try:
            logger.info("Calling %s...%s", model, f" (retry {attempt})" if attempt else "")
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **lf_kwargs,
            )
            _check_cancelled()  # bail out if cancelled while waiting
            content = response.choices[0].message.content or ""
            # Log token usage if available
            if response.usage:
                reasoning = ""
                if hasattr(response.usage, 'completion_tokens_details') and response.usage.completion_tokens_details:
                    rt = getattr(response.usage.completion_tokens_details, 'reasoning_tokens', 0)
                    if rt:
                        reasoning = f" (reasoning: {rt})"
                logger.info("Tokens: %d in → %d out%s", response.usage.prompt_tokens,
                            response.usage.completion_tokens, reasoning)
            return content
        except PipelineCancelled:
            raise
        except Exception as e:
            last_exc = e
            if attempt < LLM_MAX_RETRIES and _is_retryable(e):
                delay = _retry_delay(attempt)
                logger.warning("LLM call failed (attempt %d/%d): %s — retrying in %.1fs",
                               attempt + 1, LLM_MAX_RETRIES + 1, e, delay)
                # Interruptible sleep — wakes up if cancellation is requested
                if _cancel_event.wait(timeout=delay):
                    raise PipelineCancelled("Pipeline cancelled during retry wait") from e
            else:
                break
    raise RuntimeError(f"LLM call failed ({model} via {LLM_PROVIDER}): {last_exc}") from last_exc


def call_llm_with_metadata(
    prompt: str,
    system_prompt: str = "",
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    *,
    langfuse_name: str | None = None,
    langfuse_metadata: dict | None = None,
    langfuse_trace_id: str | None = None,
) -> LLMResponse:
    """
    Same as call_llm but returns a structured LLMResponse with metadata.
    Use this when you need token counts, error info, or model name.

    Langfuse kwargs (optional):
        langfuse_name, langfuse_metadata, langfuse_trace_id
    """
    client = _get_client()
    model = model or REASONING_MODEL

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    lf_kwargs: dict = {}
    if LANGFUSE_ENABLED:
        if langfuse_name:
            lf_kwargs["name"] = langfuse_name
        if langfuse_metadata:
            lf_kwargs["metadata"] = langfuse_metadata
        if langfuse_trace_id:
            lf_kwargs["trace_id"] = langfuse_trace_id

    last_exc: Exception | None = None
    for attempt in range(LLM_MAX_RETRIES + 1):
        _check_cancelled()
        try:
            logger.info("Calling %s (%s) [with metadata]...%s", model, LLM_PROVIDER,
                        f" (retry {attempt})" if attempt else "")
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **lf_kwargs,
            )
            _check_cancelled()
            content = response.choices[0].message.content or ""
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            if response.usage:
                reasoning = ""
                if hasattr(response.usage, 'completion_tokens_details') and response.usage.completion_tokens_details:
                    rt = getattr(response.usage.completion_tokens_details, 'reasoning_tokens', 0)
                    if rt:
                        reasoning = f" (reasoning: {rt})"
                logger.info("Tokens: %d in → %d out%s", prompt_tokens, completion_tokens, reasoning)
            return LLMResponse(
                content=content,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        except PipelineCancelled:
            raise
        except Exception as e:
            last_exc = e
            if attempt < LLM_MAX_RETRIES and _is_retryable(e):
                delay = _retry_delay(attempt)
                logger.warning("LLM call [metadata] failed (attempt %d/%d): %s — retrying in %.1fs",
                               attempt + 1, LLM_MAX_RETRIES + 1, e, delay)
                if _cancel_event.wait(timeout=delay):
                    raise PipelineCancelled("Pipeline cancelled during retry wait") from e
            else:
                break
    return LLMResponse(
        content="",
        error=str(last_exc),
        model=model,
    )


def call_llm_fast(
    prompt: str,
    system_prompt: str = "",
    *,
    langfuse_name: str | None = None,
    langfuse_metadata: dict | None = None,
    langfuse_trace_id: str | None = None,
) -> str:
    """
    Use the faster/lighter model for simple tasks like summarization
    or data extraction. Cheaper and faster than the reasoning model.
    """
    return call_llm(
        prompt=prompt,
        system_prompt=system_prompt,
        model=FAST_MODEL,
        temperature=0.1,
        max_tokens=2048,
        langfuse_name=langfuse_name,
        langfuse_metadata=langfuse_metadata,
        langfuse_trace_id=langfuse_trace_id,
    )
