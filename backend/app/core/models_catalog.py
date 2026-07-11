"""Curated catalog of selectable LLM models.

The Stocks control panel lets a user pick which model the NEXT pipeline run
should use. To keep that safe we only allow models from a curated allow-list
rather than accepting an arbitrary model string from the browser.

The catalog always includes the currently-configured default models so the
panel never offers fewer options than the server is already running with.
"""

from __future__ import annotations

from app.core.config import settings


class ModelOption(dict):
    """Lightweight serialisable model option ({id, label, provider})."""


# Curated extras per provider. Keep this conservative — only well-known,
# generally-available model ids belong here.
_OPENROUTER_CURATED: list[tuple[str, str]] = [
    ("deepseek/deepseek-chat", "DeepSeek Chat"),
    ("google/gemini-2.0-flash-001", "Gemini 2.0 Flash"),
    ("anthropic/claude-3.5-haiku", "Claude 3.5 Haiku"),
    ("meta-llama/llama-3.3-70b-instruct", "Llama 3.3 70B"),
    ("qwen/qwen-2.5-72b-instruct", "Qwen 2.5 72B"),
]

_OLLAMA_CURATED: list[tuple[str, str]] = [
    ("llama3.1", "Llama 3.1 (local)"),
    ("qwen2.5", "Qwen 2.5 (local)"),
]

# DeepSeek's official API exposes only deepseek-v4-pro / deepseek-v4-flash,
# which are already included via the configured reasoning/fast models. An
# empty list avoids offering ids the official endpoint would reject.
_DEEPSEEK_CURATED: list[tuple[str, str]] = []


def _curated_for_provider(provider: str) -> list[tuple[str, str]]:
    if provider == "ollama":
        return _OLLAMA_CURATED
    if provider == "deepseek":
        return _DEEPSEEK_CURATED
    return _OPENROUTER_CURATED


def list_model_options() -> list[dict]:
    """Return the curated model allow-list for the active provider.

    The configured reasoning/fast models are always included first so the
    default is always selectable.
    """
    provider = settings.llm_provider
    seen: set[str] = set()
    options: list[dict] = []

    def _add(model_id: str, label: str) -> None:
        model_id = (model_id or "").strip()
        if not model_id or model_id in seen:
            return
        seen.add(model_id)
        options.append({"id": model_id, "label": label, "provider": provider})

    _add(settings.reasoning_model, f"{settings.reasoning_model} (default)")
    _add(settings.fast_model, settings.fast_model)
    for model_id, label in _curated_for_provider(provider):
        _add(model_id, label)
    return options


def allowed_model_ids() -> set[str]:
    return {opt["id"] for opt in list_model_options()}


def is_allowed_model(model_id: str) -> bool:
    return bool(model_id) and model_id.strip() in allowed_model_ids()
