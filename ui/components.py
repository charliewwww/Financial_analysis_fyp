"""
Shared UI components — used across multiple pages.

Small, reusable rendering functions that don't belong to any one page.
"""

import json
import re
import streamlit as st
from utils.time_utils import to_hkt, to_hkt_short


# ── Theme helpers ─────────────────────────────────────────────────

def is_dark_mode() -> bool:
    """Check if dark mode is currently enabled."""
    return bool(st.session_state.get("dark_mode"))


def plotly_theme() -> dict:
    """Return consistent Plotly layout kwargs for the current theme."""
    dark = is_dark_mode()
    return {
        "font_color": "#e2e8f0" if dark else "#1e293b",
        "gridcolor": "rgba(148,163,184,0.15)" if dark else "rgba(226,232,240,0.5)",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
    }


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
    dark = is_dark_mode()
    track_color = "#334155" if dark else "#f1f5f9"
    score_fill = "#e2e8f0" if dark else "#0f172a"
    sub_fill = "#94a3b8" if dark else "#64748b"
    return (
        f'<div style="text-align:center">'
        f'<svg width="{size}" height="{size}" viewBox="0 0 144 144">'
        f'<circle cx="72" cy="72" r="{r}" stroke="{track_color}" stroke-width="8" fill="none"/>'
        f'<circle cx="72" cy="72" r="{r}" stroke="{color}" stroke-width="12" fill="none"'
        f' stroke-dasharray="{circ:.1f}" stroke-dashoffset="{offset:.1f}"'
        f' transform="rotate(-90 72 72)" stroke-linecap="round"/>'
        f'<text x="72" y="66" text-anchor="middle" dominant-baseline="central"'
        f' font-size="32" font-weight="800" fill="{score_fill}"'
        f' font-family="Manrope, sans-serif">{pct_display}'
        f'<tspan font-size="14" dy="-4">%</tspan></text>'
        f'<text x="72" y="92" text-anchor="middle" font-size="10" fill="{sub_fill}"'
        f' font-family="Inter, sans-serif">{score}/{max_score:.0f}</text>'
        f'</svg></div>')


def pill_cls(status: str) -> str:
    """Map validation status to pill CSS class."""
    s = (status or "").upper()
    if "FAILED" in s:
        return "pill-amber"  # amber, not red — soft visual
    if "WARNING" in s:
        return "pill-amber"
    if "PASSED" in s:
        return "pill-green"
    return "pill-gray"


def friendly_status(status: str) -> str:
    """User-facing label for validation status."""
    s = (status or "").upper()
    if "FAILED" in s:
        return "Needs Review"
    if "WARNING" in s:
        return "Reviewed"
    if "PASSED" in s:
        return "Verified"
    return ""


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
        st.caption(date_str)
    with c_score:
        friendly = friendly_status(vs)
        score_html = (
            f'<div style="text-align:right;margin-top:4px">'
            f'<span style="font-family:Manrope,sans-serif;font-weight:800;'
            f'font-size:0.9rem;color:var(--on-surface)">{conf}'
            f'<span style="font-size:0.625rem;color:var(--on-surface-variant);font-weight:700;'
            f'margin-left:2px">/10</span></span>'
        )
        if friendly:
            score_html += (
                f'<br><span style="font-size:0.5625rem;font-weight:800;'
                f'color:var(--primary);text-transform:uppercase;letter-spacing:0.05em">'
                f'{friendly}</span>'
            )
        score_html += '</div>'
        st.markdown(score_html, unsafe_allow_html=True) if conf else st.markdown("—")
    with c_btn:
        st.button("→", key=btn_key,
                  on_click=open_callback, args=(report["id"],),
                  type="secondary")


# ── Signal extraction ────────────────────────────────────────────

def extract_signals(analysis_text: str) -> list[dict]:
    """Parse PRICE PREDICTIONS section to extract buy/sell/hold signals.

    Returns list of dicts: {ticker, direction, move, reasoning, risk}
    """
    if not analysis_text:
        return []

    signals = []
    # Find the PRICE PREDICTIONS section
    pred_match = re.search(
        r'##\s*PRICE PREDICTIONS.*?\n(.*?)(?=\n##\s|\Z)',
        analysis_text, re.DOTALL | re.IGNORECASE
    )
    if not pred_match:
        return []

    block = pred_match.group(1)

    # Parse each ticker prediction:
    # **NVDA**: BULLISH | Expected move: +3% to +7%
    ticker_pattern = re.compile(
        r'\*{0,2}(\w+)\*{0,2}\s*:\s*(BULLISH|BEARISH|NEUTRAL)\s*'
        r'(?:\|\s*Expected\s+move\s*:\s*([^\n]*?))?(?:\n|$)',
        re.IGNORECASE
    )
    for m in ticker_pattern.finditer(block):
        ticker = m.group(1).upper()
        direction = m.group(2).upper()
        move = (m.group(3) or "").strip()

        # Find reasoning (next line starting with "- Reasoning:")
        pos = m.end()
        reasoning = ""
        risk = ""
        remaining = block[pos:pos + 500]
        for line in remaining.split("\n"):
            line_s = line.strip().lstrip("-•* ")
            if line_s.lower().startswith("reasoning:"):
                reasoning = line_s[len("reasoning:"):].strip()
            elif line_s.lower().startswith("key risk:"):
                risk = line_s[len("key risk:"):].strip()
            elif re.match(r'\*{0,2}\w+\*{0,2}\s*:', line_s):
                break  # next ticker

        signals.append({
            "ticker": ticker,
            "direction": direction,
            "move": move,
            "reasoning": reasoning,
            "risk": risk,
        })

    return signals


def extract_thesis(analysis_text: str) -> str:
    """Extract the one-line THESIS from the analysis."""
    if not analysis_text:
        return ""
    m = re.search(r'##\s*THESIS\s*\n+(.+?)(?:\n\n|\n##)', analysis_text, re.DOTALL)
    if m:
        return m.group(1).strip().split("\n")[0].strip()
    return ""


def split_analysis_sections(analysis_text: str) -> list[tuple[str, str]]:
    """Split analysis into (heading, content) pairs by ## headers.

    Skips PRICE PREDICTIONS, CONFIDENCE SCORE, and THESIS (shown separately).
    """
    if not analysis_text:
        return []

    skip = {"PRICE PREDICTIONS", "CONFIDENCE SCORE", "THESIS",
            "PRICE PREDICTIONS (1-WEEK OUTLOOK)"}
    sections = []
    parts = re.split(r'\n(?=##\s)', analysis_text)

    for part in parts:
        m = re.match(r'##\s*(.+?)\s*\n(.*)', part, re.DOTALL)
        if m:
            heading = m.group(1).strip()
            # Strip common suffixes for comparison
            heading_check = re.sub(r'\s*\(.*?\)\s*$', '', heading).upper()
            if heading_check not in skip:
                sections.append((heading, m.group(2).strip()))
        elif not sections:
            # Content before first heading (preamble)
            stripped = part.strip()
            if stripped:
                sections.append(("Overview", stripped))

    return sections


def extract_highlights(content: str, n: int = 2) -> list[str]:
    """Extract the 1-2 most important highlighted phrases from a section.

    Looks for bold text (**...**), then falls back to the first sentence.
    """
    if not content:
        return []

    # Collect bold phrases
    bolds = re.findall(r'\*\*(.+?)\*\*', content)
    # Filter out very short (single word labels) and very long ones
    bolds = [b.strip() for b in bolds if 8 < len(b.strip()) < 200]

    if bolds:
        return bolds[:n]

    # Fallback: first non-empty sentence
    sentences = re.split(r'(?<=[.!?])\s+', content.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
    return sentences[:n]


def extract_geopolitical_notes(analysis_text: str) -> list[str]:
    """Extract geopolitical/event-driven notes from the analysis.

    Looks for sentences mentioning geopolitical keywords.
    """
    if not analysis_text:
        return []

    geo_keywords = re.compile(
        r'(?:tariff|sanction|geopolit|iran|china|trade\s+war|conflict|embargo|'
        r'war|tension|military|nato|opec|oil\s+price|crude|invasion|missile|'
        r'nuclear|diplomatic|treaty|election|government|policy\s+shift|'
        r'regulation|ban|restrict)',
        re.IGNORECASE
    )

    notes = []
    # Split into sentences
    for sentence in re.split(r'(?<=[.!?])\s+', analysis_text):
        sentence = sentence.strip()
        if geo_keywords.search(sentence) and 20 < len(sentence) < 400:
            # Clean markdown
            clean = re.sub(r'\*+', '', sentence).strip()
            clean = re.sub(r'\[SOURCE:[^\]]*\]', '', clean).strip()
            if clean and clean not in notes:
                notes.append(clean)
            if len(notes) >= 3:
                break

    return notes
