"""
Tests for data_sources/rss_fetcher.py — with mocked HTTP requests.

No real network calls — all feeds are mocked.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


class TestFetchNewsForSector:
    @patch("data_sources.rss_fetcher._fetch_google_news_for_ticker")
    @patch("data_sources.rss_fetcher._fetch_feed_with_timeout")
    def test_filters_by_keywords(self, mock_fetch_feed, mock_google):
        """Should only return articles that match sector keywords."""
        from data_sources.rss_fetcher import fetch_news_for_sector

        # Mock RSS feed with one relevant and one irrelevant article
        mock_entry_relevant = MagicMock()
        mock_entry_relevant.title = "NVIDIA launches new AI chip for data centers"
        mock_entry_relevant.summary = "Semiconductor giant NVIDIA unveils next-gen GPU"
        mock_entry_relevant.published_parsed = (2026, 2, 19, 12, 0, 0, 0, 0, 0)
        mock_entry_relevant.link = "https://example.com/nvidia"

        mock_entry_irrelevant = MagicMock()
        mock_entry_irrelevant.title = "Weather forecast for Florida"
        mock_entry_irrelevant.summary = "Sunny skies expected all week"
        mock_entry_irrelevant.published_parsed = (2026, 2, 19, 12, 0, 0, 0, 0, 0)
        mock_entry_irrelevant.link = "https://example.com/weather"

        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry_relevant, mock_entry_irrelevant]
        mock_fetch_feed.return_value = mock_feed
        mock_google.return_value = []

        sector = {
            "name": "AI & Semiconductors",
            "tickers": ["NVDA"],
            "keywords": ["nvidia", "semiconductor", "ai chip"],
        }
        result = fetch_news_for_sector(sector)

        # The NVIDIA article should match (ticker mention), weather should not
        titles = [a["title"] for a in result]
        assert any("NVIDIA" in t for t in titles)
        assert not any("Weather" in t for t in titles)

    @patch("data_sources.rss_fetcher._fetch_google_news_for_ticker")
    @patch("data_sources.rss_fetcher._fetch_feed_with_timeout")
    def test_handles_feed_failure_gracefully(self, mock_fetch_feed, mock_google):
        """Should not crash when a feed is unreachable."""
        from data_sources.rss_fetcher import fetch_news_for_sector

        mock_fetch_feed.return_value = None  # Feed failed
        mock_google.return_value = []

        sector = {
            "name": "Test",
            "tickers": ["NVDA"],
            "keywords": ["nvidia"],
        }
        result = fetch_news_for_sector(sector)
        assert isinstance(result, list)  # Should not raise

    @patch("data_sources.rss_fetcher._fetch_google_news_for_ticker")
    @patch("data_sources.rss_fetcher._fetch_feed_with_timeout")
    def test_deduplicates_articles(self, mock_fetch_feed, mock_google):
        """Should remove duplicate articles by title."""
        from data_sources.rss_fetcher import fetch_news_for_sector

        mock_entry = MagicMock()
        mock_entry.title = "NVDA stock surges on AI demand"
        mock_entry.summary = "NVIDIA shares jump 5%"
        mock_entry.published_parsed = (2026, 2, 19, 12, 0, 0, 0, 0, 0)
        mock_entry.link = "https://example.com/nvda"

        mock_feed = MagicMock()
        # Same entry appears twice
        mock_feed.entries = [mock_entry, mock_entry]
        mock_fetch_feed.return_value = mock_feed
        mock_google.return_value = []

        sector = {"name": "Test", "tickers": ["NVDA"], "keywords": []}
        result = fetch_news_for_sector(sector)
        # Should be deduplicated
        assert len([a for a in result if a["title"] == "NVDA stock surges on AI demand"]) <= 1


class TestIsRelevant:
    def test_ticker_match(self):
        """Should match on direct ticker mention."""
        from data_sources.rss_fetcher import _is_relevant

        article = {"title": "NVDA beats earnings", "summary": ""}
        assert _is_relevant(article, [], ["NVDA"])

    def test_keyword_threshold(self):
        """Should require 2+ keyword matches to avoid false positives."""
        from data_sources.rss_fetcher import _is_relevant

        article = {"title": "rocket launch delayed by weather", "summary": "Space mission postponed"}
        # Only 1 keyword match — should not be enough
        assert not _is_relevant(article, ["rocket", "semiconductor"], [])

        # 2 keyword matches — should pass
        article2 = {"title": "SpaceX rocket launch success", "summary": "Space mission completed"}
        assert _is_relevant(article2, ["rocket", "space"], [])

    def test_no_match(self):
        """Should return False when nothing matches."""
        from data_sources.rss_fetcher import _is_relevant

        article = {"title": "Cooking recipe", "summary": "Pasta with tomato sauce"}
        assert not _is_relevant(article, ["nvidia", "semiconductor"], ["NVDA"])


class TestDeduplicate:
    def test_removes_duplicates(self):
        """Should keep only first occurrence of duplicate titles."""
        from data_sources.rss_fetcher import _deduplicate

        articles = [
            {"title": "Article A", "source": "Feed1"},
            {"title": "Article B", "source": "Feed1"},
            {"title": "Article A", "source": "Feed2"},  # duplicate
        ]
        result = _deduplicate(articles)
        assert len(result) == 2

    def test_preserves_order(self):
        """Should maintain the original order."""
        from data_sources.rss_fetcher import _deduplicate

        articles = [
            {"title": "First", "source": "A"},
            {"title": "Second", "source": "B"},
        ]
        result = _deduplicate(articles)
        assert result[0]["title"] == "First"


class TestParseEntry:
    def test_valid_entry(self):
        """Should parse a valid RSS entry into article dict."""
        from data_sources.rss_fetcher import _parse_entry

        entry = MagicMock()
        entry.title = "Test Article"
        entry.summary = "<p>Some <b>HTML</b> content</p>"
        entry.published_parsed = (2026, 2, 19, 10, 0, 0, 0, 0, 0)
        entry.link = "https://example.com"

        result = _parse_entry(entry, "TestFeed")
        assert result["title"] == "Test Article"
        assert "<" not in result["summary"]  # HTML should be stripped
        assert result["source"] == "TestFeed"
        assert result["link"] == "https://example.com"

    def test_empty_title_returns_none(self):
        """Should return None for entries with no title."""
        from data_sources.rss_fetcher import _parse_entry

        entry = MagicMock()
        entry.title = ""

        result = _parse_entry(entry, "TestFeed")
        assert result is None
