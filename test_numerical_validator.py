"""Quick test for the programmatic numerical validator."""
from utils.numerical_validator import validate_numbers

# Simulate a fake analysis text with numbers
analysis = """
## COMPANY SPOTLIGHT
- **NVDA**: Currently trading at $135.50 (1W: +3.2%, 1M: +12.5%). MCap: $3.3T. P/E: 55.2
- **TSM**: Trading at $210.00 with RSI of 72.5 (overbought). Margin: 45.3%
- **AMD**: Price $120.00, down -2.1% this week
"""

# Simulate real data
prices = [
    {"ticker": "NVDA", "price": 134.80, "change_1w_pct": 3.1, "change_1m_pct": 12.0,
     "market_cap": 3.28e12, "pe_ratio": 54.0, "profit_margin": 0.56, "revenue_ttm": 1.3e11},
    {"ticker": "TSM", "price": 205.00, "change_1w_pct": 1.5, "change_1m_pct": 8.0,
     "market_cap": 9.5e11, "pe_ratio": 28.0, "profit_margin": 0.45, "revenue_ttm": 8.5e10},
    {"ticker": "AMD", "price": 119.50, "change_1w_pct": -2.3, "change_1m_pct": -5.0,
     "market_cap": 1.9e11, "pe_ratio": 45.0, "profit_margin": 0.08, "revenue_ttm": 2.5e10},
]

technicals = [
    {"ticker": "TSM", "rsi_14": 68.0},
]

result = validate_numbers(analysis, prices, technicals)

print(f"Status: {result.status}")
print(f"Verified: {result.verified_count}")
print(f"Discrepancies: {result.discrepancy_count}")
print(f"Unchecked: {result.unchecked_count}")
print()
for c in result.checks:
    ticker = c.ticker or "?"
    actual = c.actual_value if c.actual_value is not None else "N/A"
    dev = f"{c.deviation_pct:+.1f}%" if c.deviation_pct is not None else "N/A"
    print(f"  {c.status:20s} {ticker:5s} {c.claim_type:18s} claimed={c.claimed_value:<12} actual={actual}  dev={dev}")
print()
print(result.to_markdown())
