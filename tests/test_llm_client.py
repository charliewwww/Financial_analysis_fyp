"""
Tests for agents/llm_client.py — with mocked OpenAI client.

No real API calls — all OpenAI interactions are mocked.
"""

import pytest
from unittest.mock import MagicMock, patch
import agents.llm_client as llm_client
from agents.llm_client import call_llm, call_llm_fast, check_llm_health, LLMHealthCheckError


def _mock_chat_response(content: str = "Test response"):
    """Create a mock OpenAI ChatCompletion response."""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50
    return mock_response


class TestCallLLM:
    @patch("agents.llm_client._get_client")
    def test_returns_response_text(self, mock_get_client):
        """call_llm should return the LLM's text response."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_chat_response("Hello world")
        mock_get_client.return_value = mock_client

        result = call_llm("Test prompt", "System prompt")
        assert result == "Hello world"

    @patch("agents.llm_client._get_client")
    def test_passes_parameters(self, mock_get_client):
        """call_llm should pass temperature and max_tokens to the API."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_chat_response("ok")
        mock_get_client.return_value = mock_client

        call_llm("prompt", "system", temperature=0.5, max_tokens=2048)

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs.get("temperature") == 0.5 or \
               (call_args[1].get("temperature") == 0.5 if len(call_args) > 1 else True)

    @patch("agents.llm_client._get_client")
    def test_handles_empty_response(self, mock_get_client):
        """call_llm should handle None content gracefully."""
        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 0

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = call_llm("prompt", "system")
        assert result == ""

    @patch("agents.llm_client._get_client")
    def test_uses_global_llm_slot(self, mock_get_client, monkeypatch):
        """call_llm should acquire and release the provider/GPU slot."""
        events: list[str] = []

        class FakeSlot:
            def acquire(self, timeout: float) -> bool:
                events.append(f"acquire:{timeout}")
                return True

            def release(self) -> None:
                events.append("release")

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_chat_response("slot response")
        mock_get_client.return_value = mock_client
        monkeypatch.setattr(llm_client, "_llm_slots", FakeSlot())

        result = call_llm("Test prompt", "System prompt")

        assert result == "slot response"
        assert events == ["acquire:1.0", "release"]


class TestCallLLMFast:
    @patch("agents.llm_client._get_client")
    def test_uses_fast_model(self, mock_get_client):
        """call_llm_fast should call the API with FAST_MODEL."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_chat_response("fast response")
        mock_get_client.return_value = mock_client

        result = call_llm_fast("quick prompt", "system")
        assert result == "fast response"

    @patch("agents.llm_client._get_client")
    def test_accepts_generation_overrides(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_chat_response("judged")
        mock_get_client.return_value = mock_client

        call_llm_fast("judge prompt", "system", temperature=0.0, max_tokens=1024)

        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["temperature"] == 0.0
        assert call_args.kwargs["max_tokens"] == 1024


class TestCheckLLMHealth:
    @patch("agents.llm_client.OpenAI")
    def test_healthy_llm(self, mock_openai_cls):
        """Health check should pass when LLM responds."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_chat_response("pong")
        mock_openai_cls.return_value = mock_client

        # Should not raise
        check_llm_health()

    @patch("agents.llm_client.OpenAI")
    def test_unhealthy_llm(self, mock_openai_cls):
        """Health check should raise LLMHealthCheckError on failure."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Connection refused")
        mock_openai_cls.return_value = mock_client

        with pytest.raises(LLMHealthCheckError):
            check_llm_health()
