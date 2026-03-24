"""
Markdown Report Exporter — converts a DB report + optional state into a
clean, self-contained Markdown document suitable for sharing or archiving.

Usage:
    from utils.markdown_export import export_report_markdown
    md = export_report_markdown(report_dict, state_dict)
"""

from __future__ import annotations

import json
from datetime import datetime


def export_report_markdown(report: dict, state: dict | None = None) -> str:
    """
    Build a full Markdown report from DB report dict + optional pipeline state.

    Args:
        report: Row from the reports table (dict with keys like sector_name,
                analysis, validation, confidence_score, etc.)
        state: Optional deserialized pipeline_state JSON.

    Returns:
        Complete Markdown string ready for download or file write.
    """
    lines: list[str] = []
    _a = lines.append  # shorthand

    sector = report.get("sector_name", "Unknown Sector")
    date_raw = report.get("created_at", "")
    date_str = date_raw[:16].replace("T", " ") if date_raw else "N/A"
    conf = report.get("confidence_score", 0) or 0

    # ── Title & metadata ──────────────────────────────────────────
    _a(f"# {sector} — Weekly Analysis Report")
    _a("")
    _a(f"**Generated:** {date_str}  ")
    _a(f"**Report ID:** {report.get('id', 'N/A')}  ")
    _a(f"**Sector ID:** {report.get('sector_id', 'N/A')}  ")
    _a(f"**Confidence Score:** {conf:.1f} / 10  ")
    _a(f"**Validation Status:** {report.get('validation_status', 'N/A')}  ")
    _a(f"**Data Sufficiency:** {report.get('data_sufficiency', 'N/A')}  ")
    _a("")

    # ── Executive summary ─────────────────────────────────────────
    ns = report.get("news_summary", "")
    if ns:
        _a("## Executive Summary")
        _a("")
        _a(f"> {ns}")
        _a("")

    # ── Analysis ──────────────────────────────────────────────────
    _a("## Analysis")
    _a("")
    _a(report.get("analysis", "*No analysis available.*"))
    _a("")

    # ── Validation ────────────────────────────────────────────────
    validation = report.get("validation", "")
    if validation:
        _a("## Validation Report")
        _a("")
        vs = report.get("validation_status", "")
        if vs:
            _a(f"**Status:** {vs}")
            _a("")
        _a(validation)
        _a("")

    if state:
        issues = state.get("validation_issues", [])
        if issues:
            _a("### Validation Issues")
            _a("")
            for iss in issues:
                _a(f"- ⚠️ {iss}")
            _a("")

    # ── Technical indicators ──────────────────────────────────────
    technicals = _parse_json(report.get("technicals_snapshot"))
    if technicals:
        _a("## Technical Indicators")
        _a("")
        _a("| Ticker | Price | RSI(14) | Volume Z | BB Pos | 5d Chg % |")
        _a("|--------|------:|--------:|---------:|-------:|---------:|")
        for t in technicals:
            if t.get("error"):
                _a(f"| {t.get('ticker', '?')} | — | — | — | — | error |")
                continue
            _a(
                f"| {t.get('ticker', '?')} "
                f"| {_fmt(t.get('current_price'))} "
                f"| {_fmt(t.get('rsi_14'))} "
                f"| {_fmt(t.get('volume_zscore'))} "
                f"| {_fmt(t.get('bb_position'))} "
                f"| {_fmt(t.get('change_5d_pct'))} |"
            )
        _a("")

    # ── Price snapshot ────────────────────────────────────────────
    prices = _parse_json(report.get("prices_snapshot"))
    if prices:
        _a("## Price Snapshot")
        _a("")
        _a("| Ticker | Price | 1W Chg % | 1M Chg % | Mkt Cap |")
        _a("|--------|------:|---------:|---------:|--------:|")
        for p in prices:
            if p.get("error"):
                _a(f"| {p.get('ticker', '?')} | — | — | — | error |")
                continue
            # yahoo_finance stores as 'price', technicals as 'current_price'
            price_val = p.get('price') or p.get('current_price')
            _a(
                f"| {p.get('ticker', '?')} "
                f"| {_fmt(price_val)} "
                f"| {_fmt(p.get('change_1w_pct'))} "
                f"| {_fmt(p.get('change_1m_pct'))} "
                f"| {_fmt_large(p.get('market_cap'))} |"
            )
        _a("")

    # ── Anomaly alerts (from state) ───────────────────────────────
    if state:
        anomalies = state.get("anomaly_alerts", [])
        if anomalies:
            _a("## Anomaly Alerts")
            _a("")
            for a in anomalies:
                sev = a.get("severity", "?")
                icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
                _a(f"- {icon} **{a.get('ticker', '?')}** [{a.get('signal_type', '?')}]: "
                   f"{a.get('description', 'N/A')}")
            _a("")

    # ── Macro environment (from state) ────────────────────────────
    if state:
        macro = state.get("macro_data", {})
        indicators = {k: v for k, v in macro.items() if k != "_meta"}
        if indicators:
            _a("## Macro Environment")
            _a("")
            _a("| Indicator | Value |")
            _a("|-----------|------:|")
            for k, v in indicators.items():
                val = v.get("value", "N/A") if isinstance(v, dict) else v
                _a(f"| {k} | {val} |")
            _a("")

    # ── News sources ──────────────────────────────────────────────
    news = _parse_json(report.get("news_snapshot"))
    if news:
        _a("## News Sources")
        _a("")
        _a(f"*{len(news)} articles used in this analysis.*")
        _a("")
        for i, art in enumerate(news[:30], 1):
            title = art.get("title", "Untitled")
            source = art.get("source", "")
            link = art.get("link", "")
            published = art.get("published", "")
            if link:
                _a(f"{i}. [{title}]({link}) — *{source}* ({published})")
            else:
                _a(f"{i}. {title} — *{source}* ({published})")
        if len(news) > 30:
            _a(f"\n*... and {len(news) - 30} more articles*")
        _a("")

    # ── SEC filings ───────────────────────────────────────────────
    filings = _parse_json(report.get("filings_snapshot"))
    if filings:
        _a("## SEC Filings")
        _a("")
        for f in filings:
            if f.get("error"):
                continue
            _a(f"- **{f.get('ticker', '?')}** {f.get('type', f.get('form_type', '?'))} "
               f"({f.get('date', f.get('filing_date', 'N/A'))})")
        _a("")

    # ── Pipeline timing ───────────────────────────────────────────
    timing = _parse_json(report.get("timing_snapshot"))
    if timing:
        _a("## Pipeline Timing")
        _a("")
        total = timing.get("total_seconds", 0)
        _a(f"**Total runtime:** {total:.1f}s")
        _a("")
        steps = timing.get("steps", [])
        if steps:
            _a("| Node | Duration |")
            _a("|------|----------|")
            for step in steps:
                _a(f"| {step.get('name', '?')} | {step.get('seconds', 0):.1f}s |")
            _a("")

    # ── Footer ────────────────────────────────────────────────────
    _a("---")
    _a("")
    _a(f"*Report generated by Multi-Agentic Financial Analysis Pipeline · "
       f"{datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    return "\n".join(lines)


# ── Helpers ───────────────────────────────────────────────────────

def _parse_json(val) -> list | dict | None:
    """Safely parse a JSON string or return the value if already parsed."""
    if val is None:
        return None
    if isinstance(val, (list, dict)):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return None


def _fmt(val, decimals: int = 2) -> str:
    """Format a numeric value or return '—' for None."""
    if val is None:
        return "—"
    try:
        return f"{float(val):.{decimals}f}"
    except (ValueError, TypeError):
        return str(val)


def _fmt_large(val) -> str:
    """Format large numbers (market cap) in B/M/K."""
    if val is None:
        return "—"
    try:
        v = float(val)
    except (ValueError, TypeError):
        return str(val)
    if v >= 1e12:
        return f"{v / 1e12:.1f}T"
    if v >= 1e9:
        return f"{v / 1e9:.1f}B"
    if v >= 1e6:
        return f"{v / 1e6:.1f}M"
    if v >= 1e3:
        return f"{v / 1e3:.0f}K"
    return f"{v:.0f}"
