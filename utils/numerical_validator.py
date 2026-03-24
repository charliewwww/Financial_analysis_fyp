"""
Numerical Validator — programmatic fact-checking of LLM claims.

This is Layer 3 of the anti-hallucination pipeline:
    Layer 1: Source grounding (prompts require citations)
    Layer 2: RAG validation (vector DB cross-reference — coming soon)
  → Layer 3: Numerical cross-check (THIS FILE)
    Layer 4: Self-correction loop (orchestrator retries)
    Layer 5: Confidence scoring (score_node)

HOW IT WORKS:
1. Extract every number from the analysis text (prices, percentages, market caps)
2. Match each number to a ticker using context clues
3. Compare against real Yahoo Finance / technical analysis data
4. Flag any deviation > NUMERICAL_TOLERANCE_PCT as an error

This is DETERMINISTIC — no LLM involved. Numbers either match or they don't.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from config.settings import NUMERICAL_TOLERANCE_PCT


# ── Data structures ───────────────────────────────────────────────

@dataclass
class ClaimCheck:
    """Result of checking a single numerical claim."""
    claim_text: str          # The raw text snippet containing the number
    claimed_value: float     # The number we extracted
    claim_type: str          # "price" | "percent_change" | "market_cap" | "pe_ratio" | "margin" | "revenue"
    ticker: str | None       # Which ticker we think this refers to
    actual_value: float | None = None  # Real value from data (None = can't check)
    deviation_pct: float | None = None  # How far off (None = can't compute)
    status: str = "UNCHECKED"  # VERIFIED | DISCREPANCY | UNCHECKED
    note: str = ""

    @property
    def is_error(self) -> bool:
        return self.status == "DISCREPANCY"


@dataclass
class ValidationResult:
    """Complete result of numerical validation."""
    checks: list[ClaimCheck] = field(default_factory=list)
    status: str = ""  # PASSED | PASSED WITH WARNINGS | FAILED
    summary: str = ""

    @property
    def verified_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "VERIFIED")

    @property
    def discrepancy_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "DISCREPANCY")

    @property
    def unchecked_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "UNCHECKED")

    def to_markdown(self) -> str:
        """Format as Markdown for display in the UI."""
        lines = ["## PROGRAMMATIC VALIDATION RESULTS\n"]

        if not self.checks:
            lines.append("No numerical claims found to validate.\n")
            return "\n".join(lines)

        for check in self.checks:
            if check.status == "VERIFIED":
                icon = "✅"
            elif check.status == "DISCREPANCY":
                icon = "⚠️"
            else:
                icon = "❓"

            line = f"- {icon} **{check.status}**: "
            if check.ticker:
                line += f"`{check.ticker}` "
            line += f"{check.claim_type} = {_format_num(check.claimed_value, check.claim_type)}"

            if check.actual_value is not None:
                line += (f" → actual: {_format_num(check.actual_value, check.claim_type)}"
                         f" (off by {check.deviation_pct:+.1f}%)")
            if check.note:
                line += f"  *{check.note}*"
            lines.append(line)

        lines.append(f"\n**Overall: {self.status}**")
        lines.append(f"- Verified: {self.verified_count}")
        lines.append(f"- Discrepancies: {self.discrepancy_count}")
        lines.append(f"- Unchecked: {self.unchecked_count}")
        if self.summary:
            lines.append(f"\n{self.summary}")

        return "\n".join(lines)


# ── Main entry point ──────────────────────────────────────────────

def validate_numbers(
    analysis_text: str,
    prices: list[dict],
    technicals: list[dict] | None = None,
    tolerance_pct: float = NUMERICAL_TOLERANCE_PCT,
) -> ValidationResult:
    """
    Extract numerical claims from analysis and verify against real data.

    Args:
        analysis_text: The LLM-generated analysis report (Markdown)
        prices: Real stock data from Yahoo Finance
        technicals: Real technical analysis data
        tolerance_pct: Max allowed % deviation (default 5%)

    Returns:
        ValidationResult with per-claim verdicts and overall status
    """
    # Build lookup tables from real data
    price_lookup = _build_price_lookup(prices)
    ta_lookup = _build_ta_lookup(technicals) if technicals else {}
    all_tickers = set(price_lookup.keys()) | set(ta_lookup.keys())

    # Extract claims from text
    claims = _extract_numerical_claims(analysis_text, all_tickers)

    # Check each claim against real data
    for claim in claims:
        if not claim.ticker or claim.ticker not in price_lookup:
            claim.status = "UNCHECKED"
            claim.note = "No matching ticker data"
            continue

        real_data = price_lookup[claim.ticker]
        ta_data = ta_lookup.get(claim.ticker, {})

        _check_claim(claim, real_data, ta_data, tolerance_pct)

    # Determine overall status
    result = ValidationResult(checks=claims)
    total_checkable = result.verified_count + result.discrepancy_count
    if result.discrepancy_count == 0 and result.verified_count > 0:
        result.status = "PASSED"
        result.summary = f"All {result.verified_count} checkable claims verified within {tolerance_pct}% tolerance."
    elif result.discrepancy_count == 1:
        result.status = "PASSED WITH WARNINGS"
        result.summary = (f"1 claim deviates more than {tolerance_pct}% "
                          f"from real data. Review flagged items.")
    elif result.discrepancy_count >= 2:
        result.status = "FAILED"
        result.summary = (f"{result.discrepancy_count} numerical discrepancies found. "
                          f"Analysis may contain hallucinated numbers.")
    elif result.unchecked_count > 0 and total_checkable == 0:
        # All claims are unchecked — can't verify anything
        result.status = "PASSED WITH WARNINGS"
        result.summary = (f"{result.unchecked_count} claims could not be verified "
                          f"(no matching ticker data). Manual review recommended.")
    else:
        result.status = "PASSED"
        result.summary = "No checkable numerical claims found."

    return result


# ── Number extraction engine ──────────────────────────────────────

# Patterns for extracting numbers with context
_PATTERNS = [
    # $1.5T or $1T (market cap / revenue) — check BEFORE bare prices
    (r'\$(\d{1,4}(?:\.\d{1,2})?)\s*[Tt](?:rillion)?', "market_cap_trillion"),
    # $1.5B or $150B (market cap / revenue) — check BEFORE bare prices
    (r'\$(\d{1,4}(?:\.\d{1,2})?)\s*[Bb](?:illion)?', "market_cap_or_revenue"),
    # $150M (revenue / smaller caps) — check BEFORE bare prices
    (r'\$(\d{1,6}(?:\.\d{1,2})?)\s*[Mm](?:illion)?', "revenue_million"),
    # $123.45 or $123 (stock prices) — must NOT be followed by B/T/M and must
    # not be a fragment of a larger number like "$3.3T" → avoid matching "$3"
    (r'\$(\d{1,5}\.\d{1,2})(?!\s*[BTMbtm])', "price"),
    # 1W: +5.2% or weekly change patterns (multiple formats the LLM may use)
    (r'(?:1W|1w|week(?:ly)?|past\s+week)\s*[:=]?\s*([+-]?\d{1,3}\.\d{1,2})%', "change_1w_pct"),
    (r'(?:weekly|1-week|one.week)\s+(?:change|return|move|gain|loss)\s*(?:of|:)?\s*([+-]?\d{1,3}\.\d{1,2})%', "change_1w_pct"),
    # 1M: +5.2% or monthly change patterns
    (r'(?:1M|1m|month(?:ly)?|past\s+month)\s*[:=]?\s*([+-]?\d{1,3}\.\d{1,2})%', "change_1m_pct"),
    (r'(?:monthly|1-month|one.month)\s+(?:change|return|move|gain|loss)\s*(?:of|:)?\s*([+-]?\d{1,3}\.\d{1,2})%', "change_1m_pct"),
    # P/E: 25.3 or P/E of 25.3 or P/E ratio of 25
    (r'P/?E(?:\s+(?:ratio|of))?\s*(?::|of|=)?\s*(\d{1,4}(?:\.\d{1,2})?)', "pe_ratio"),
    # RSI: 65.2 or RSI(14): 65 or RSI of 65 or RSI is at 65
    (r'RSI(?:\s*\(?\d{1,2}\)?)?\s*(?::|of|=|is\s+at|is|at)?\s*(\d{1,3}(?:\.\d{1,2})?)', "rsi"),
    # MACD patterns
    (r'MACD\s*(?:signal|line)?\s*(?::|of|=|is|at)?\s*([+-]?\d{1,3}(?:\.\d{1,2})?)', "macd"),
    # margin: 25.3% or margin of 25%
    (r'[Mm]argin\s*(?::|of|=|is)?\s*(\d{1,3}(?:\.\d{1,2})?)%', "margin"),
    # EPS patterns: EPS $5.23 or EPS of 5.23
    (r'EPS\s*(?:of|:|\$)?\s*\$?(\d{1,4}(?:\.\d{1,2})?)', "eps"),
    # Revenue with plain numbers: revenue of 35.8 billion
    (r'[Rr]evenue\s+(?:of|:)?\s*\$?(\d{1,4}(?:\.\d{1,2})?)\s*[Bb]', "market_cap_or_revenue"),
    # Generic percentage (catch-all, lower priority) — LAST so specific patterns match first
    (r'([+-]?\d{1,3}\.\d{1,2})%', "percent"),
]


def _extract_numerical_claims(text: str, known_tickers: set[str]) -> list[ClaimCheck]:
    """
    Pull every numerical claim from the analysis text and try to
    associate it with a ticker symbol.

    Uses a sliding context window of ±3 lines so that a ticker mentioned
    in a heading or previous sentence can still be associated with
    numbers on the next few lines.
    """
    claims = []
    lines = text.split("\n")

    # Pre-compute a "last mentioned ticker" that carries across lines
    last_ticker_seen: str | None = None

    for line_idx, line in enumerate(lines):
        # Build a context window of ±3 lines for ticker matching
        context_start = max(0, line_idx - 3)
        context_end = min(len(lines), line_idx + 4)
        context_window = " ".join(lines[context_start:context_end])

        # Find the nearest ticker mention in this line or context window
        line_ticker = _find_ticker_in_context(line, known_tickers)
        if line_ticker is None:
            # Try the context window (nearby lines)
            line_ticker = _find_ticker_in_context(context_window, known_tickers)
        if line_ticker is None:
            # Fall back to the last ticker mentioned in the document
            line_ticker = last_ticker_seen
        else:
            # Update the last-seen ticker
            last_ticker_seen = line_ticker

        for pattern, claim_type in _PATTERNS:
            for match in re.finditer(pattern, line, re.IGNORECASE):
                raw_value = match.group(1)
                try:
                    value = float(raw_value)
                except ValueError:
                    continue

                # Adjust for B/T/M suffixes
                if claim_type == "market_cap_or_revenue":
                    claim_type = "market_cap"
                    value *= 1e9
                elif claim_type == "market_cap_trillion":
                    claim_type = "market_cap"
                    value *= 1e12
                elif claim_type == "revenue_million":
                    claim_type = "revenue"
                    value *= 1e6

                # For bare prices, check context to classify
                if claim_type == "price":
                    # If the price is between 1 and 5000, it's likely a stock price
                    if not (0.5 < value < 5000):
                        continue  # Skip implausible stock prices

                # For percentages, classify based on context
                if claim_type == "percent":
                    # Skip if this exact value was already captured by a more
                    # specific pattern (1W, 1M, margin) on this same line
                    # Those patterns run first and are already in `claims`
                    already_captured = any(
                        c.claimed_value == value and c.ticker == line_ticker
                        and c.claim_type in ("change_1w_pct", "change_1m_pct", "margin")
                        for c in claims
                    )
                    if already_captured:
                        continue
                    lower_line = line.lower()
                    if "margin" in lower_line:
                        claim_type = "margin"
                    else:
                        claim_type = "percent_generic"

                # Get surrounding context for the claim text
                start = max(0, match.start() - 30)
                end = min(len(line), match.end() + 30)
                context = line[start:end].strip()

                claims.append(ClaimCheck(
                    claim_text=context,
                    claimed_value=value,
                    claim_type=claim_type,
                    ticker=line_ticker,
                ))

    # Deduplicate: same value + same ticker + same type = one claim
    seen = set()
    unique = []
    for c in claims:
        key = (c.ticker, c.claim_type, round(c.claimed_value, 2))
        if key not in seen:
            seen.add(key)
            unique.append(c)

    return unique


def _find_ticker_in_context(line: str, known_tickers: set[str]) -> str | None:
    """
    Find the most likely ticker symbol mentioned in a line of text.

    Checks both explicit ticker mentions (NVDA, $NVDA) and common
    company name → ticker mappings so that "NVIDIA" resolves to NVDA.
    """
    # Look for explicit ticker mentions: NVDA, $NVDA, (NVDA)
    for ticker in known_tickers:
        patterns = [
            rf'\b{ticker}\b',        # Word boundary: "NVDA reported..."
            rf'\${ticker}\b',         # Dollar prefix: "$NVDA"
            rf'\({ticker}\)',         # Parenthesized: "(NVDA)"
        ]
        for pat in patterns:
            if re.search(pat, line, re.IGNORECASE):
                return ticker

    # Look for company names → resolve to ticker
    line_upper = line.upper()
    for ticker in known_tickers:
        names = _TICKER_COMPANY_NAMES.get(ticker, [])
        for name in names:
            if name.upper() in line_upper:
                return ticker

    return None


# Common company name → ticker mappings for better claim association
_TICKER_COMPANY_NAMES: dict[str, list[str]] = {
    "NVDA": ["NVIDIA", "Nvidia"],
    "TSM": ["TSMC", "Taiwan Semiconductor"],
    "AMD": ["Advanced Micro"],
    "INTC": ["Intel"],
    "AVGO": ["Broadcom"],
    "QCOM": ["Qualcomm"],
    "ASML": ["ASML"],
    "MU": ["Micron"],
    "MRVL": ["Marvell"],
    "ARM": ["Arm Holdings"],
    "SMCI": ["Super Micro", "Supermicro"],
    "CEG": ["Constellation Energy"],
    "MSFT": ["Microsoft"],
    "GOOGL": ["Google", "Alphabet"],
    "META": ["Meta Platforms", "Facebook"],
    "AMZN": ["Amazon"],
    "RKLB": ["Rocket Lab"],
    "BA": ["Boeing"],
    "LMT": ["Lockheed Martin", "Lockheed"],
    "RTX": ["Raytheon", "RTX Corp"],
    "NOC": ["Northrop Grumman", "Northrop"],
    "SPCE": ["Virgin Galactic"],
    "RDW": ["Redwire"],
    "ASTS": ["AST SpaceMobile"],
    "GSAT": ["Globalstar"],
    "LITE": ["Lumentum"],
    "COHR": ["Coherent"],
    "CIENA": ["Ciena"],
    "CIEN": ["Ciena"],
    "ANET": ["Arista Networks", "Arista"],
    "KEYS": ["Keysight"],
    "VIAV": ["VIAV Solutions", "VIAV"],
    "INFN": ["Infinera"],
    "IIVI": ["II-VI"],
    "FNSR": ["Finisar"],
}


# ── Claim verification ────────────────────────────────────────────

def _check_claim(
    claim: ClaimCheck,
    real_data: dict,
    ta_data: dict,
    tolerance_pct: float,
):
    """Compare a single claim against real data."""
    actual = None

    if claim.claim_type == "price":
        actual = real_data.get("price")
    elif claim.claim_type == "change_1w_pct":
        actual = real_data.get("change_1w_pct")
    elif claim.claim_type == "change_1m_pct":
        actual = real_data.get("change_1m_pct")
    elif claim.claim_type == "market_cap":
        actual = real_data.get("market_cap")
    elif claim.claim_type == "pe_ratio":
        actual = real_data.get("pe_ratio")
    elif claim.claim_type == "margin":
        actual = real_data.get("profit_margin")
        if actual is not None:
            actual = actual * 100  # Convert from 0.25 to 25.0 for comparison
    elif claim.claim_type == "revenue":
        actual = real_data.get("revenue_ttm")
    elif claim.claim_type == "rsi":
        actual = ta_data.get("rsi_14")
    elif claim.claim_type == "macd":
        actual = ta_data.get("macd_line")
    elif claim.claim_type == "eps":
        actual = real_data.get("eps_ttm")

    if actual is None:
        claim.status = "UNCHECKED"
        claim.note = f"No {claim.claim_type} data available for {claim.ticker}"
        return

    claim.actual_value = actual

    # Calculate deviation
    if actual == 0:
        # Can't compute % deviation from zero
        claim.deviation_pct = 0.0 if claim.claimed_value == 0 else 100.0
    else:
        claim.deviation_pct = ((claim.claimed_value - actual) / abs(actual)) * 100

    # Verdict
    if abs(claim.deviation_pct) <= tolerance_pct:
        claim.status = "VERIFIED"
        claim.note = "Within tolerance"
    else:
        claim.status = "DISCREPANCY"
        claim.note = f"Exceeds {tolerance_pct}% tolerance"


# ── Lookup builders ───────────────────────────────────────────────

def _build_price_lookup(prices: list[dict]) -> dict[str, dict]:
    """Build a ticker → price data lookup from Yahoo Finance snapshots."""
    lookup = {}
    for p in prices:
        if p.get("error"):
            continue
        ticker = p.get("ticker", "").upper()
        if ticker:
            lookup[ticker] = p
    return lookup


def _build_ta_lookup(technicals: list[dict]) -> dict[str, dict]:
    """Build a ticker → technical data lookup."""
    lookup = {}
    for t in technicals:
        if t.get("error"):
            continue
        ticker = t.get("ticker", "").upper()
        if ticker:
            lookup[ticker] = t
    return lookup


# ── Display helpers ───────────────────────────────────────────────

def _format_num(value: float, claim_type: str) -> str:
    """Format a number for display based on its type."""
    if claim_type in ("market_cap", "revenue"):
        if value >= 1e12:
            return f"${value/1e12:.2f}T"
        elif value >= 1e9:
            return f"${value/1e9:.1f}B"
        elif value >= 1e6:
            return f"${value/1e6:.0f}M"
        else:
            return f"${value:,.0f}"
    elif claim_type == "price":
        return f"${value:.2f}"
    elif "pct" in claim_type or claim_type in ("margin", "percent_generic"):
        return f"{value:+.1f}%"
    elif claim_type == "pe_ratio":
        return f"{value:.1f}x"
    elif claim_type in ("rsi", "macd"):
        return f"{value:.1f}"
    elif claim_type == "eps":
        return f"${value:.2f}"
    else:
        return f"{value:.2f}"
