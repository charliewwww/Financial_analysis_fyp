"""Tests for utils.http_retry.resilient_get."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests
from requests.exceptions import ConnectionError, Timeout

from utils.http_retry import resilient_get


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok_response(status: int = 200, text: str = "ok") -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.text = text
    resp.headers = {}
    resp.raise_for_status = MagicMock()
    return resp


def _error_response(status: int) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.headers = {}
    resp.raise_for_status = MagicMock(
        side_effect=requests.HTTPError(f"{status} Error", response=resp)
    )
    return resp


# ---------------------------------------------------------------------------
# Success on first attempt
# ---------------------------------------------------------------------------

@patch("utils.http_retry.requests.get")
def test_success_first_try(mock_get):
    mock_get.return_value = _ok_response()
    resp = resilient_get("https://example.com", label="test")
    assert resp.status_code == 200
    assert mock_get.call_count == 1


# ---------------------------------------------------------------------------
# Retry on timeout then succeed
# ---------------------------------------------------------------------------

@patch("utils.http_retry.time.sleep")  # skip real delays
@patch("utils.http_retry.requests.get")
def test_retry_on_timeout(mock_get, mock_sleep):
    mock_get.side_effect = [Timeout("timed out"), _ok_response()]
    resp = resilient_get("https://example.com", max_retries=2, backoff_base=0.01)
    assert resp.status_code == 200
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()  # one retry sleep


# ---------------------------------------------------------------------------
# Retry on ConnectionError then succeed
# ---------------------------------------------------------------------------

@patch("utils.http_retry.time.sleep")
@patch("utils.http_retry.requests.get")
def test_retry_on_connection_error(mock_get, mock_sleep):
    mock_get.side_effect = [ConnectionError("reset"), _ok_response()]
    resp = resilient_get("https://example.com", max_retries=1, backoff_base=0.01)
    assert resp.status_code == 200
    assert mock_get.call_count == 2


# ---------------------------------------------------------------------------
# Retry on 502 then succeed
# ---------------------------------------------------------------------------

@patch("utils.http_retry.time.sleep")
@patch("utils.http_retry.requests.get")
def test_retry_on_502(mock_get, mock_sleep):
    bad = MagicMock(spec=requests.Response)
    bad.status_code = 502
    bad.headers = {}
    mock_get.side_effect = [bad, _ok_response()]
    resp = resilient_get("https://example.com", max_retries=1, backoff_base=0.01)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Exhaust all retries → raise
# ---------------------------------------------------------------------------

@patch("utils.http_retry.time.sleep")
@patch("utils.http_retry.requests.get")
def test_raises_after_exhausting_retries(mock_get, mock_sleep):
    mock_get.side_effect = Timeout("always timeout")
    with pytest.raises(Timeout):
        resilient_get("https://example.com", max_retries=2, backoff_base=0.01)
    assert mock_get.call_count == 3  # 1 initial + 2 retries


# ---------------------------------------------------------------------------
# 404 passes through immediately (no retry)
# ---------------------------------------------------------------------------

@patch("utils.http_retry.requests.get")
def test_404_no_retry(mock_get):
    mock_get.return_value = _error_response(404)
    with pytest.raises(requests.HTTPError):
        resilient_get("https://example.com", max_retries=2)
    assert mock_get.call_count == 1


# ---------------------------------------------------------------------------
# Extra kwargs (e.g. params) forwarded to requests.get
# ---------------------------------------------------------------------------

@patch("utils.http_retry.requests.get")
def test_kwargs_forwarded(mock_get):
    mock_get.return_value = _ok_response()
    resilient_get("https://example.com", params={"q": "test"}, label="kw-test")
    _, kwargs = mock_get.call_args
    assert kwargs["params"] == {"q": "test"}


# ---------------------------------------------------------------------------
# Backoff delay increases exponentially
# ---------------------------------------------------------------------------

@patch("utils.http_retry.time.sleep")
@patch("utils.http_retry.requests.get")
def test_exponential_backoff(mock_get, mock_sleep):
    mock_get.side_effect = Timeout("fail")
    with pytest.raises(Timeout):
        resilient_get("https://example.com", max_retries=2, backoff_base=1.0)
    # delays: 1*2^0=1, 1*2^1=2
    delays = [call.args[0] for call in mock_sleep.call_args_list]
    assert delays == [1.0, 2.0]
