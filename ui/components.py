"""
Shared UI components — used across multiple pages.

Small, reusable rendering functions that don't belong to any one page.
"""

import json
import re
import streamlit as st
from utils.time_utils import to_hkt, to_hkt_short


# ── Sector colour map ─────────────────────────────────────────────

SECTOR_COLORS = {
    "ai_semiconductors": "#5C9CE6",
    "space_rockets": "#9575CD",
    "optical_communications": "#b8860b",
}

# Map sector_id → CSS class suffix for dot boxes
SECTOR_DOT_CLASS = {
    "ai_semiconductors": "ai",
    "space_rockets": "space",
    "optical_communications": "optical",
}


# ── SVG / Visual helpers ─────────────────────────────────────────

def ring_svg(score: float, max_score: float = 10, size: int = 144) -> str:
    """SVG donut ring — gold primary for high, grey track underneath."""
    pct = min(score / max_score, 1.0) if max_score else 0
    pct_display = round(pct * 100)
    r = 64
    circ = 2 * 3.14159 * r
    offset = circ * (1 - pct)
    # Gold gradient for ≥4, red for <4
    color = "#b8860b" if score >= 4 else "#ef4444"
    track_color = "#f1f5f9"
    return (
        f'<div style="text-align:center">'
        f'<svg width="{size}" height="{size}" viewBox="0 0 144 144">'
        f'<circle cx="72" cy="72" r="{r}" stroke="{track_color}" stroke-width="8" fill="none"/>'
        f'<circle cx="72" cy="72" r="{r}" stroke="{color}" stroke-width="12" fill="none"'
        f' stroke-dasharray="{circ:.1f}" stroke-dashoffset="{offset:.1f}"'
        f' transform="rotate(-90 72 72)" stroke-linecap="round"/>'
        f'<text x="72" y="66" text-anchor="middle" dominant-baseline="central"'
        f' font-size="32" font-weight="800" fill="#0f172a"'
        f' font-family="Manrope, sans-serif">{pct_display}'
        f'<tspan font-size="14" dy="-4">%</tspan></text>'
        f'<text x="72" y="92" text-anchor="middle" font-size="10" fill="#64748b"'
        f' font-family="Inter, sans-serif">{score}/{max_score:.0f}</text>'
        f'</svg></div>')


def pill_cls(status: str) -> str:
    """Map validation status to pill CSS class."""
    s = (status or "").upper()
    if "FAILED" in s:
        return "pill-red"
    if "WARNING" in s:
        return "pill-amber"
    if "PASSED" in s:
        return "pill-green"
    return "pill-gray"


def load_state(report: dict) -> dict | None:
    """Deserialize the pipeline_state JSON from a report row."""
    raw = report.get("pipeline_state")
    if not raw:
        return None
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return None


def linkify_sources(analysis_text: str, articles: list[dict]) -> str:
    """Replace [SOURCE: ...] citations in analysis text with clickable links."""
    if not articles:
        return analysis_text

    # Build source name → best URL mapping
    source_urls: dict[str, str] = {}
    for a in articles:
        src = a.get("source", "")
        url = a.get("link", "")
        if src and url and src not in source_urls:
            source_urls[src] = url

    if not source_urls:
        return analysis_text

    def _replace_citation(match):
        cited = match.group(1).strip()
        # Exact match
        url = source_urls.get(cited)
        if not url:
            # Case-insensitive partial match
            for src_name, src_url in source_urls.items():
                if cited.lower() in src_name.lower() or src_name.lower() in cited.lower():
                    url = src_url
                    break
        if not url:
            # Match first word (e.g., "Yahoo Finance" → "Yahoo Finance Top News")
            cited_words = cited.lower().split()
            if cited_words:
                for src_name, src_url in source_urls.items():
                    if cited_words[0] in src_name.lower():
                        url = src_url
                        break
        if url:
            # Sanitize URL — only allow http/https to prevent XSS
            if not url.startswith(("http://", "https://")):
                return match.group(0)
            # Escape the cited name to prevent HTML injection
            import html as _html
            safe_cited = _html.escape(cited)
            safe_url = _html.escape(url)
            return (f'[SOURCE: <a href="{safe_url}" target="_blank" '
                    f'class="source-link">'
                    f'{safe_cited} &#x2197;</a>]')
        return match.group(0)

    return re.sub(r'\[SOURCE:\s*([^\]]+)\]', _replace_citation, analysis_text)


def report_row(report: dict, btn_key: str, open_callback):
    """Intelligence-feed style row with glowing sector dot box."""
    from ui.components import SECTOR_COLORS, SECTOR_DOT_CLASS, pill_cls

    sid = report.get("sector_id", "")
    dot_color = SECTOR_COLORS.get(sid, "#b8860b")
    dot_cls = SECTOR_DOT_CLASS.get(sid, "optical")
    conf = report.get("confidence_score")
    vs = report.get("validation_status", "")
    date_str = to_hkt_short(report["created_at"])

    c_dot, c_name, c_score, c_btn = st.columns([0.4, 3.5, 1.2, 0.6])

    with c_dot:
        st.markdown(
            f'<div class="sector-dot-box {dot_cls}" style="margin-top:4px">'
            f'<div class="sector-dot {dot_cls}"></div></div>',
            unsafe_allow_html=True)
    with c_name:
        st.markdown(f"**{report['sector_name']}**")
        caption_parts = [date_str]
        if vs:
            caption_parts.append(vs.lower())
        st.caption(" · ".join(caption_parts))
    with c_score:
        score_html = (
            f'<div style="text-align:right;margin-top:4px">'
            f'<span style="font-family:Manrope,sans-serif;font-weight:800;'
            f'font-size:0.9rem;color:#0f172a">{conf}'
            f'<span style="font-size:0.625rem;color:#cbd5e1;font-weight:700;'
            f'margin-left:2px">/10</span></span>'
        )
        if vs:
            score_html += (
                f'<br><span style="font-size:0.5625rem;font-weight:800;'
                f'color:#b8860b;text-transform:uppercase;letter-spacing:0.05em">'
                f'{vs.lower()}</span>'
            )
        score_html += '</div>'
        st.markdown(score_html, unsafe_allow_html=True) if conf else st.markdown("—")
    with c_btn:
        st.button("→", key=btn_key,
                  on_click=open_callback, args=(report["id"],),
                  type="secondary")
