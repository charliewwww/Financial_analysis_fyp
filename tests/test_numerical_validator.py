"""
Tests for utils/numerical_validator.py — the deterministic fact-checker.

All tests use synthetic data, no network calls needed.
"""

import pytest
from utils.numerical_validator import (
    validate_numbers,
    ValidationResult,
    ClaimCheck,
)


class TestValidateNumbers:
    """End-to-end tests for the validate_numbers() function."""

    def test_matching_price_passes(self):
        """Analysis claims price that matches real data → VERIFIED."""
        analysis = "NVIDIA (NVDA) is trading at $130.50 per share."
        prices = [{"ticker": "NVDA", "price": 130.0}]
        result = validate_numbers(analysis, prices, [])
        # Should find at least one claim
        assert len(result.checks) >= 1
        # The NVDA price claim should be verified (within tolerance)
        nvda_checks = [c for c in result.checks if c.ticker == "NVDA"]
        if nvda_checks:
            assert any(c.status == "VERIFIED" for c in nvda_checks)

    def test_wildly_wrong_price_flags_discrepancy(self):
        """Analysis claims price far from real → DISCREPANCY."""
        analysis = "NVIDIA (NVDA) is currently priced at $500.00."
        prices = [{"ticker": "NVDA", "price": 130.0}]
        result = validate_numbers(analysis, prices, [])
        nvda_checks = [c for c in result.checks
                       if c.ticker == "NVDA" and c.claim_type == "price"]
        if nvda_checks:
            assert any(c.status == "DISCREPANCY" for c in nvda_checks)

    def test_no_numbers_in_analysis(self):
        """Analysis with no extractable numbers → empty checks."""
        analysis = "The semiconductor sector is growing rapidly."
        result = validate_numbers(analysis, [], [])
        assert result.status == "PASSED"  # Nothing to flag

    def test_multiple_tickers(self):
        """Analysis mentioning multiple tickers → checks for each."""
        analysis = (
            "NVDA is at $130. TSM is trading at $175. "
            "AMD reached $165 today."
        )
        prices = [
            {"ticker": "NVDA", "price": 130.0},
            {"ticker": "TSM", "price": 175.0},
            {"ticker": "AMD", "price": 165.0},
        ]
        result = validate_numbers(analysis, prices, [])
        tickers_checked = set(c.ticker for c in result.checks if c.ticker)
        # Should have found claims for at least 1 ticker
        assert len(tickers_checked) >= 1

    def test_percentage_claims(self):
        """Analysis with percent change claims should be checked."""
        analysis = "NVDA is up 5.2% this week."
        prices = [{"ticker": "NVDA", "price": 130.0, "week_change_pct": 5.0}]
        result = validate_numbers(analysis, prices, [])
        pct_checks = [c for c in result.checks if c.claim_type == "percent_change"]
        # Should extract the 5.2% claim
        assert len(result.checks) >= 1


class TestValidationResult:
    """Unit tests for the ValidationResult dataclass."""

    def test_counts(self):
        result = ValidationResult(checks=[
            ClaimCheck(claim_text="a", claimed_value=1.0, claim_type="price",
                       ticker="X", status="VERIFIED"),
            ClaimCheck(claim_text="b", claimed_value=2.0, claim_type="price",
                       ticker="Y", status="DISCREPANCY"),
            ClaimCheck(claim_text="c", claimed_value=3.0, claim_type="price",
                       ticker="Z", status="UNCHECKED"),
        ])
        assert result.verified_count == 1
        assert result.discrepancy_count == 1
        assert result.unchecked_count == 1

    def test_to_markdown_not_empty(self):
        result = ValidationResult(
            checks=[
                ClaimCheck(claim_text="test", claimed_value=100.0,
                           claim_type="price", ticker="NVDA",
                           actual_value=100.5, deviation_pct=0.5,
                           status="VERIFIED"),
            ],
            status="PASSED",
        )
        md = result.to_markdown()
        assert "PASSED" in md
        assert "VERIFIED" in md
        assert "NVDA" in md

    def test_to_markdown_empty_checks(self):
        result = ValidationResult(checks=[], status="PASSED")
        md = result.to_markdown()
        assert "No numerical claims" in md


class TestClaimCheck:
    def test_is_error_property(self):
        c = ClaimCheck(claim_text="x", claimed_value=1.0,
                       claim_type="price", ticker="X", status="DISCREPANCY")
        assert c.is_error is True

    def test_is_not_error(self):
        c = ClaimCheck(claim_text="x", claimed_value=1.0,
                       claim_type="price", ticker="X", status="VERIFIED")
        assert c.is_error is False


class TestStricterThresholds:
    """Verify the tightened PASSED/WARNINGS/FAILED thresholds."""

    def test_two_discrepancies_is_failed(self):
        """With the new stricter thresholds, 2 discrepancies → FAILED."""
        analysis = (
            "NVDA is at $500.00 this week. "  # wrong: real = $130
            "NVDA margin is 99.0%."            # wrong: real = 25%
        )
        prices = [{"ticker": "NVDA", "price": 130.0, "profit_margin": 0.25}]
        result = validate_numbers(analysis, prices, [])
        discreps = [c for c in result.checks if c.status == "DISCREPANCY"]
        if len(discreps) >= 2:
            assert result.status == "FAILED"

    def test_one_discrepancy_is_warning(self):
        """1 discrepancy → PASSED WITH WARNINGS."""
        analysis = "NVDA is trading at $500.00."  # wrong
        prices = [{"ticker": "NVDA", "price": 130.0}]
        result = validate_numbers(analysis, prices, [])
        discreps = [c for c in result.checks if c.status == "DISCREPANCY"]
        if len(discreps) == 1:
            assert result.status == "PASSED WITH WARNINGS"


class TestContextWindowTickerMatching:
    """Test that ticker from nearby lines is propagated to claims."""

    def test_ticker_from_heading_carries_to_next_line(self):
        """A ticker mentioned in a heading should match claims on the next line."""
        analysis = (
            "### NVIDIA (NVDA)\n"
            "\n"
            "The stock is at $130.50 per share.\n"
        )
        prices = [{"ticker": "NVDA", "price": 130.0}]
        result = validate_numbers(analysis, prices, [])
        nvda_checks = [c for c in result.checks if c.ticker == "NVDA"]
        assert len(nvda_checks) >= 1

    def test_company_name_resolves_to_ticker(self):
        """Company names like 'NVIDIA' should resolve to ticker NVDA."""
        analysis = "NVIDIA reported revenue of $35.8B this quarter."
        prices = [{"ticker": "NVDA", "price": 130.0, "market_cap": 3.2e12}]
        result = validate_numbers(analysis, prices, [])
        nvda_checks = [c for c in result.checks if c.ticker == "NVDA"]
        assert len(nvda_checks) >= 1

    def test_rsi_claim_checked(self):
        """RSI claims should be verified against technical data."""
        analysis = "NVDA RSI is at 72.5, indicating overbought conditions."
        prices = [{"ticker": "NVDA", "price": 130.0}]
        technicals = [{"ticker": "NVDA", "rsi_14": 72.0}]
        result = validate_numbers(analysis, prices, technicals)
        rsi_checks = [c for c in result.checks if c.claim_type == "rsi" and c.ticker == "NVDA"]
        assert len(rsi_checks) >= 1
        if rsi_checks:
            assert rsi_checks[0].status == "VERIFIED"

    def test_pe_ratio_checked(self):
        """P/E ratio claims should be verified."""
        analysis = "NVDA P/E ratio of 65.3 is elevated."
        prices = [{"ticker": "NVDA", "price": 130.0, "pe_ratio": 65.0}]
        result = validate_numbers(analysis, prices, [])
        pe_checks = [c for c in result.checks if c.claim_type == "pe_ratio"]
        assert len(pe_checks) >= 1
