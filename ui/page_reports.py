"""
Reports page — list view + detail view, driven by session state.
"""

import html
import json
import re
import streamlit as st

from config.sectors import SECTORS
from database.reports_db import get_reports_list, get_report_by_id, delete_report, delete_reports
from utils.markdown_export import export_report_markdown
from ui.components import (
    SECTOR_COLORS, ring_svg, pill_cls, load_state, linkify_sources, report_row,
    friendly_status, extract_signals, extract_thesis, split_analysis_sections,
    extract_highlights, extract_geopolitical_notes,
    plotly_theme,
)
from utils.time_utils import to_hkt, to_hkt_short


# ── Cached loader ─────────────────────────────────────────────────

@st.cache_data(ttl=30)
def _cached_reports_list(sector_id: str | None = None, limit: int = 50):
    return get_reports_list(sector_id=sector_id, limit=limit)


@st.cache_data(ttl=60)
def _load_full_report(report_id: int):
    return get_report_by_id(report_id)


def _open_report(report_id: int):
    st.session_state.page = "Reports"
    st.session_state.selected_report_id = report_id


def _back_to_list():
    st.session_state.selected_report_id = None


def _safe_markdown_html(text: str) -> str:
    """Escape LLM text for safe HTML injection, then restore markdown formatting.

    Converts **bold** → <strong>, bullet lines → list items, and
    double-newlines → <br> for readable rendering inside unsafe_allow_html.
    """
    # Temporarily extract bold phrases before escaping
    bold_re = re.compile(r'\*\*(.+?)\*\*')
    # Use a unique marker that cannot appear in LLM output
    _MARKER = "XBOLD_7f3a9c_"
    # Defense-in-depth: strip any pre-existing marker patterns from input
    text = text.replace(_MARKER, "")
    placeholders: list[str] = []
    def _save_bold(m):
        placeholders.append(m.group(1))
        return f'{_MARKER}{len(placeholders) - 1}_END'
    text = bold_re.sub(_save_bold, text)

    # Escape everything for safety (markers are alphanumeric, unaffected)
    text = html.escape(text)

    # Restore bold placeholders as <strong>
    for i, phrase in enumerate(placeholders):
        text = text.replace(f'{_MARKER}{i}_END', f'<strong>{html.escape(phrase)}</strong>')

    # Convert markdown-style bullets to styled list
    text = re.sub(r'(?m)^[\-\*•]\s+', '• ', text)

    # Paragraphs
    text = text.replace('\n\n', '<br><br>')
    text = text.replace('\n', '<br>')

    return text


# ═══════════════════════════════════════════════════════════════════
# PAGE ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def render():
    sel = st.session_state.get("selected_report_id")
    if sel:
        report = _load_full_report(sel)
        if report:
            _report_detail(report)
        else:
            st.error("Report not found.")
            _back_to_list()
    else:
        _report_list_page()


# ═══════════════════════════════════════════════════════════════════
# LIST VIEW
# ═══════════════════════════════════════════════════════════════════

def _report_list_page():
    st.markdown('<h2 style="font-family:Manrope,sans-serif;font-weight:800;'
                'letter-spacing:-0.03em;color:var(--on-surface)">Analysis</h2>',
                unsafe_allow_html=True)

    c1, _, c_del = st.columns([2, 3, 1])
    with c1:
        filt = st.selectbox(
            "Sector",
            ["All Sectors"] + [s["name"] for s in SECTORS.values()],
            label_visibility="collapsed",
        )

    sid = None
    if filt != "All Sectors":
        for k, v in SECTORS.items():
            if v["name"] == filt:
                sid = k
                break

    reports = _cached_reports_list(sector_id=sid, limit=50)
    if not reports:
        st.info("No reports yet. Run an analysis from the Overview page.")
        return

    with c_del:
        if st.button("🗑️ Delete All", key="delete_all_reports", type="secondary"):
            st.session_state["_confirm_delete_all"] = True

    # Confirmation for delete all
    if st.session_state.get("_confirm_delete_all"):
        label = f"all {len(reports)} reports" if sid is None else f"all {len(reports)} {filt} reports"
        st.warning(f"Delete {label}? This cannot be undone.")
        c_yes, c_no, _ = st.columns([1, 1, 3])
        with c_yes:
            if st.button("Yes, delete all", key="confirm_del_all_yes", type="primary"):
                ids = [r["id"] for r in reports]
                n = delete_reports(ids)
                _cached_reports_list.clear()
                _load_full_report.clear()
                st.session_state.pop("_confirm_delete_all", None)
                st.toast(f"Deleted {n} reports", icon="🗑️")
                st.rerun()
        with c_no:
            if st.button("Cancel", key="confirm_del_all_no"):
                st.session_state.pop("_confirm_delete_all", None)
                st.rerun()

    with st.container(border=True):
        for r in reports:
            report_row(r, f"rlist_{r['id']}", _open_report)


# ═══════════════════════════════════════════════════════════════════
# REPORT DETAIL VIEW — storytelling layout
# ═══════════════════════════════════════════════════════════════════

def _report_detail(report: dict):
    state = load_state(report)

    # ── Header ────────────────────────────────────────────────────
    hdr_left, _, hdr_right = st.columns([2, 1, 2])
    with hdr_left:
        st.button("← Back to reports", on_click=_back_to_list, width="stretch")
    with hdr_right:
        dl_col, del_col = st.columns(2)
        with dl_col:
            md_text = export_report_markdown(report, state)
            sector_slug = report.get("sector_id", "report").replace(" ", "_")
            date_slug = report.get("created_at", "")[:10]
            st.download_button(
                label="📥 Download",
                data=md_text,
                file_name=f"{sector_slug}_{date_slug}.md",
                mime="text/markdown",
                width="stretch",
            )
        with del_col:
            if st.button("🗑️ Delete", key="delete_report", type="secondary", width="stretch"):
                st.session_state["_confirm_delete_report"] = report["id"]

    # Confirmation dialog
    if st.session_state.get("_confirm_delete_report") == report["id"]:
        st.warning(f"Delete report #{report['id']} ({report['sector_name']})? This cannot be undone.")
        c_yes, c_no, _ = st.columns([1, 1, 3])
        with c_yes:
            if st.button("Yes, delete", key="confirm_del_yes", type="primary"):
                delete_report(report["id"])
                _cached_reports_list.clear()
                _load_full_report.clear()
                st.session_state.pop("_confirm_delete_report", None)
                st.toast(f"Report #{report['id']} deleted", icon="🗑️")
                _back_to_list()
                st.rerun()
        with c_no:
            if st.button("Cancel", key="confirm_del_no"):
                st.session_state.pop("_confirm_delete_report", None)
                st.rerun()

    conf = report.get("confidence_score", 0) or 0
    date_str = to_hkt(report["created_at"])
    st.markdown(f'<h2 style="font-family:Manrope,sans-serif;font-weight:800;'
                f'letter-spacing:-0.03em;color:var(--on-surface);margin-bottom:0">{report["sector_name"]}</h2>',
                unsafe_allow_html=True)
    st.caption(f"Report #{report['id']} · {date_str}")

    # ── Thesis banner ───────────────────────────────────────────────
    analysis_text = report.get("analysis", "")
    thesis = extract_thesis(analysis_text)
    if thesis:
        st.markdown(
            f'<div class="thesis-banner">'
            f'<div class="thesis-label">Thesis</div>'
            f'<div class="thesis-text">{html.escape(thesis)}</div></div>',
            unsafe_allow_html=True,
        )

    # ── Signal cards (buy / sell / hold) ──────────────────────────
    signals = extract_signals(analysis_text)
    if signals:
        cards_html = '<div class="signal-grid">'
        for sig in signals:
            d = sig["direction"].lower()
            css_cls = d if d in ("bullish", "bearish", "neutral") else "neutral"
            move_html = f'<div class="signal-move">{html.escape(sig["move"])}</div>' if sig["move"] else ""
            reason_html = f'<div class="signal-reason">{html.escape(sig["reasoning"])}</div>' if sig["reasoning"] else ""
            cards_html += (
                f'<div class="signal-card {css_cls}">'
                f'<div class="signal-ticker">{html.escape(sig["ticker"])}</div>'
                f'<span class="signal-dir {css_cls}">{html.escape(sig["direction"])}</span>'
                f'{move_html}{reason_html}</div>'
            )
        cards_html += '</div>'
        st.markdown(cards_html, unsafe_allow_html=True)

    # ── Compact metric strip ────────────────────────────────────────
    vs = report.get("validation_status", "")
    n_articles = report.get("news_used", 0)
    ds = report.get("data_sufficiency", "")
    ds_label = ds.title() if ds else "N/A"
    macro_status = "—"
    if state:
        mm = state.get("macro_data", {}).get("_meta", {})
        if mm.get("api_status") == "ok":
            macro_status = f"{mm.get('indicators_fetched', 0)} ind."
        elif mm.get("api_status") == "partial":
            macro_status = "Partial"
    rag_hits = state.get("rag_metadata", {}).get("total_results", 0) if state else 0
    timing_json = report.get("timing_snapshot")
    total_t = 0
    if timing_json:
        t_data = json.loads(timing_json) if isinstance(timing_json, str) else timing_json
        total_t = t_data.get("total_seconds", 0)

    friendly_vs = friendly_status(vs) or "N/A"
    pill = pill_cls(vs)

    strip_html = (
        '<div class="metric-strip">'
        f'<div class="metric-chip">'
        f'<div class="metric-chip-label">Evidence</div>'
        f'<div class="metric-chip-value">{conf}<span style="font-size:0.7rem;color:var(--on-surface-variant)">/ 10</span></div></div>'
        f'<div class="metric-chip">'
        f'<div class="metric-chip-label">Validation</div>'
        f'<div><span class="pill {pill}" style="font-size:0.7rem">{friendly_vs}</span></div></div>'
        f'<div class="metric-chip">'
        f'<div class="metric-chip-label">Articles</div>'
        f'<div class="metric-chip-value">{n_articles}</div></div>'
        f'<div class="metric-chip">'
        f'<div class="metric-chip-label">Data Quality</div>'
        f'<div class="metric-chip-value" style="font-size:0.95rem">{html.escape(ds_label)}</div></div>'
        f'<div class="metric-chip">'
        f'<div class="metric-chip-label">Macro</div>'
        f'<div class="metric-chip-value" style="font-size:0.95rem">{macro_status}</div>'
        f'<div class="metric-chip-sub">{rag_hits} RAG</div></div>'
        f'<div class="metric-chip">'
        f'<div class="metric-chip-label">Pipeline</div>'
        f'<div class="metric-chip-value">{total_t:.0f}s</div></div>'
        '</div>'
    )
    st.markdown(strip_html, unsafe_allow_html=True)

    st.write("")

    # ── Anomaly alerts (high-urgency — shown before analysis text) ─
    if state:
        anomalies = state.get("anomaly_alerts", [])
        if anomalies:
            with st.container(border=True):
                st.markdown('<span class="section-title">⚡ Anomaly Alerts</span>',
                            unsafe_allow_html=True)
                st.caption("Auto-detected unusual signals from technical data")
                for a in anomalies:
                    sev = a.get("severity", "?")
                    icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
                    st.markdown(
                        f"{icon} **{a.get('ticker', '?')}** "
                        f"[{a.get('signal_type', '?')}] — "
                        f"{a.get('description', 'N/A')}"
                    )
            st.write("")

    # ── Segmented analysis sections ─────────────────────────────────
    news_json = report.get("news_snapshot")
    articles_for_links = []
    if news_json:
        try:
            articles_for_links = json.loads(news_json) if isinstance(news_json, str) else news_json
        except (json.JSONDecodeError, TypeError):
            pass

    sections = split_analysis_sections(analysis_text)
    # Decide where to insert technicals inline (after 2nd section or halfway)
    tech_insert_idx = min(2, max(len(sections) - 1, 0))

    SECTION_ICONS = {
        "KEY DEVELOPMENTS": "📰",
        "DEEP CONTEXT": "🔍",
        "MACRO": "📊",
        "MACROECONOMIC CONTEXT": "📊",
        "SUPPLY CHAIN": "🔗",
        "SUPPLY CHAIN ANALYSIS": "🔗",
        "COMPANY SPOTLIGHT": "🏢",
        "RISK FACTORS": "⚠️",
        "OVERVIEW": "📋",
    }

    for idx, (heading, content) in enumerate(sections):
        icon = SECTION_ICONS.get(heading.upper(), "📄")
        with st.container(border=True):
            st.markdown(
                f'<div class="report-section-header">{icon} {html.escape(heading)}</div>',
                unsafe_allow_html=True,
            )

            # Render section content: escape for safety, then restore
            # markdown bold → <strong> and line breaks for readability.
            safe_content = _safe_markdown_html(content)
            linked = linkify_sources(safe_content, articles_for_links)
            st.markdown(linked, unsafe_allow_html=True)

            # Macro gauge visual — inject into macro section
            is_macro = heading.upper() in ("MACRO", "MACROECONOMIC CONTEXT",
                                           "MACRO ENVIRONMENT")
            if is_macro and state:
                _render_macro_gauge(state)
                # Geopolitical news callout
                geo_notes = extract_geopolitical_notes(analysis_text)
                if geo_notes:
                    geo_items = "".join(f"• {html.escape(n)}<br>" for n in geo_notes)
                    st.markdown(
                        f'<div class="geo-callout">'
                        f'<div class="geo-callout-title">🌍 Geopolitical & Event Impact</div>'
                        f'{geo_items}</div>',
                        unsafe_allow_html=True,
                    )

        # Insert technical analysis inline after the chosen section
        if idx == tech_insert_idx:
            with st.container(border=True):
                st.markdown(
                    '<div class="report-section-header">📈 Technical Analysis</div>',
                    unsafe_allow_html=True,
                )
                _render_technicals(report)

    # Fallback if no sections were parsed
    if not sections:
        with st.container(border=True):
            st.markdown('<span class="section-title">✨ Analysis</span>',
                        unsafe_allow_html=True)
            linked_analysis = linkify_sources(
                analysis_text or "*No analysis available.*", articles_for_links
            )
            st.markdown(linked_analysis, unsafe_allow_html=True)

    st.write("")

    # ── Side-by-side: Confidence breakdown + Supply chain ─────────
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.markdown('<span class="section-title">Evidence Breakdown</span>',
                        unsafe_allow_html=True)
            st.caption("Objective score — calculated from data quality, not AI self-assessment")
            _render_confidence_breakdown(report, state)

    with right:
        with st.container(border=True):
            st.markdown('<span class="section-title">Supply Chain Map</span>',
                        unsafe_allow_html=True)
            chain = None
            if state and state.get("sector_supply_chain_map"):
                chain = state["sector_supply_chain_map"]
            else:
                sector = SECTORS.get(report.get("sector_id", ""), {})
                chain = sector.get("supply_chain_map")
            if chain:
                _render_supply_chain(chain)
            else:
                st.caption("No supply chain data available.")

    st.write("")

    # ── Validation report ─────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<span class="section-title">Validation Report</span>',
                    unsafe_allow_html=True)
        vs = report.get("validation_status", "")
        if vs:
            st.markdown(f'<span class="pill {pill_cls(vs)}">{friendly_status(vs)}</span>',
                        unsafe_allow_html=True)
        validation = report.get("validation", "")
        if validation:
            st.markdown(validation)
        else:
            st.caption("No validation data for this report.")
        if state:
            for iss in state.get("validation_issues", []):
                st.warning(iss)

    st.write("")

    # ── Evidence trail ────────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<span class="section-title">Evidence Trail</span>',
                    unsafe_allow_html=True)
        st.caption("How data sources support each conclusion")
        _render_evidence(report, state)

    st.write("")

    # ── Deep dives — developer tools behind toggle ─────────────
    st.write("")
    show_advanced = st.toggle("Show Advanced Details", value=False, key=f"adv_{report['id']}")
    if show_advanced:
        st.markdown("##### Deep Dive")
        with st.expander("RAG Historical Context"):
            _detail_rag(state)
        with st.expander("Macro Environment"):
            _detail_macro(state)
        with st.expander("All News Sources & Links"):
            _detail_news(report)
        with st.expander("SEC Filings"):
            _detail_filings(report)
        with st.expander("LLM Prompts & Responses"):
            _detail_llm_io(state)
        with st.expander("Pipeline Execution Trace"):
            _detail_trace(state)
        with st.expander("Pipeline Timing"):
            _detail_timing(report)


# ═══════════════════════════════════════════════════════════════════
# RENDER HELPERS
# ═══════════════════════════════════════════════════════════════════

def _render_confidence_breakdown(report: dict, state: dict | None):
    """
    Show per-dimension confidence breakdown.

    If the state contains `confidence_breakdown` (new scoring), use it directly.
    Otherwise fall back to re-computing from raw report data (legacy reports).
    """
    stored_breakdown = (state or {}).get("confidence_breakdown", {})

    if stored_breakdown:
        # ── New-format breakdown (stored by score_node) ──────────
        label_map = {
            "news_coverage":    ("News Coverage",      2.5),
            "price_data":       ("Price Data",         2.0),
            "technicals":       ("Technical Analysis", 1.0),
            "filings":          ("SEC Filings",        0.5),
            "macro_data":       ("Macro Data",         1.0),
            "source_diversity": ("Source Diversity",    1.0),
            "validation":       ("Validation",         2.0),
        }
        total = 0.0
        for key, (label, mx) in label_map.items():
            pts = stored_breakdown.get(key, 0.0)
            total += pts
            pct = pts / mx * 100 if mx else 0
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:baseline">'
                f'<span style="font-size:0.88rem">{label}</span>'
                f'<span style="font-weight:600;font-size:0.88rem">{pts:.1f}/{mx:.1f}</span></div>'
                f'<div class="bar-track"><div class="bar-fill bar-amber" style="width:{pct:.0f}%"></div></div>',
                unsafe_allow_html=True)
        total = min(round(total, 1), 10.0)
        st.markdown(
            f'<div style="text-align:right;font-weight:700;font-size:1.1rem;margin-top:4px">'
            f'Total  {total} / 10</div>', unsafe_allow_html=True)
        return

    # ── Legacy fallback: re-compute from raw snapshots ───────────
    nc = report.get("news_used", 0)
    prices = json.loads(report["prices_snapshot"]) if report.get("prices_snapshot") else []
    techs = json.loads(report["technicals_snapshot"]) if report.get("technicals_snapshot") else []
    fils = json.loads(report["filings_snapshot"]) if report.get("filings_snapshot") else []
    vs = (report.get("validation_status") or "").upper()

    news_pts = 2.5 if nc >= 9 else (1.5 if nc >= 4 else (0.5 if nc >= 1 else 0))
    vp = [p for p in prices if not p.get("error")]
    price_pts = round(len(vp) / max(len(prices), 1) * 2, 1)
    vt = [t for t in techs if not t.get("error")]
    ta_pts = round(len(vt) / max(len(techs), 1) * 1.0, 1)
    vf = [f for f in fils if "error" not in f]
    filing_pts = 0.5 if vf else 0.0

    macro_pts = 0.0
    macro_note = "No macro data"
    if state:
        macro_meta = state.get("macro_data", {}).get("_meta", {})
        if macro_meta.get("api_status") == "ok":
            fetched = macro_meta.get("indicators_fetched", 0)
            macro_pts = min(round(fetched / 6 * 1.0, 1), 1.0)
            macro_note = f"{fetched} indicators"
        elif macro_meta.get("api_status") == "partial":
            macro_pts = 0.3
            macro_note = "Partial data"

    val_pts = 0.0 if "FAILED" in vs else (1.0 if "WARNING" in vs else (2.0 if "PASSED" in vs else 1.0))
    total = min(round(news_pts + price_pts + ta_pts + filing_pts + macro_pts + val_pts, 1), 10)

    rows = [
        ("News Coverage", news_pts, 2.5, f"{nc} articles"),
        ("Price Data", price_pts, 2, f"{len(vp)}/{len(prices)} tickers"),
        ("Technical Analysis", ta_pts, 1.0, f"{len(vt)}/{len(techs)} tickers"),
        ("SEC Filings", filing_pts, 0.5, f"{len(vf)} filings"),
        ("Macro Data", macro_pts, 1.0, macro_note),
        ("Validation", val_pts, 2, report.get("validation_status") or "Unknown"),
    ]
    for label, pts, mx, note in rows:
        pct = pts / mx * 100 if mx else 0
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:baseline">'
            f'<span style="font-size:0.88rem">{label}</span>'
            f'<span style="font-weight:600;font-size:0.88rem">{pts}/{mx}</span></div>'
            f'<div class="bar-track"><div class="bar-fill bar-amber" style="width:{pct}%"></div></div>'
            f'<div style="font-size:0.75rem;color:var(--on-surface-variant);margin-bottom:8px">{note}</div>',
            unsafe_allow_html=True)

    st.markdown(
        f'<div style="text-align:right;font-weight:700;font-size:1.1rem;margin-top:4px">'
        f'Total  {total} / 10</div>', unsafe_allow_html=True)


def _render_supply_chain(chain_map: dict):
    html = []
    for ticker, info in chain_map.items():
        role = info.get("role", "")
        targets = info.get("supplies_to", [])
        pills = "".join(f'<span class="chain-target">{t}</span>' for t in targets)
        html.append(
            f'<div class="chain-row">'
            f'<span class="chain-ticker">{ticker}</span>'
            f'<span class="chain-role">{role}</span>'
            f'<span style="color:#C8A951">→</span>{pills}</div>')
    st.markdown("".join(html), unsafe_allow_html=True)


def _render_macro_gauge(state: dict):
    """Render a compact macro indicators gauge row with direction arrows."""
    macro = state.get("macro_data", {})
    if not macro:
        return

    arrow_map = {"rising": "↑", "falling": "↓", "stable": "→", "unknown": "?"}
    color_map = {"rising": "#22c55e", "falling": "#ef4444", "stable": "#94a3b8", "unknown": "#94a3b8"}

    indicator_keys = [k for k in macro if k != "_meta"]
    if not indicator_keys:
        return

    gauges = []
    for key in indicator_keys:
        d = macro[key]
        trend = d.get("trend", "unknown")
        arrow = arrow_map.get(trend, "?")
        color = color_map.get(trend, "#94a3b8")
        val = d.get("value", "N/A")
        unit = d.get("unit", "")
        name = d.get("name", key.replace("_", " ").title())
        # Shorten name for display
        short = name.split("(")[0].strip()
        if len(short) > 20:
            words = short.split()
            short = " ".join(words[:3])

        change = d.get("change")
        delta_html = ""
        if change is not None:
            delta_color = "#22c55e" if change > 0 else ("#ef4444" if change < 0 else "#94a3b8")
            delta_html = f'<div class="macro-gauge-delta" style="color:{delta_color}">{change:+.2f}{unit}</div>'

        gauges.append(
            f'<div class="macro-gauge">'
            f'<div class="macro-gauge-arrow" style="color:{color}">{arrow}</div>'
            f'<div class="macro-gauge-name">{short}</div>'
            f'<div class="macro-gauge-val">{val}{unit}</div>'
            f'{delta_html}</div>'
        )

    st.markdown(
        f'<div class="macro-gauge-row">{"".join(gauges)}</div>',
        unsafe_allow_html=True,
    )


def _render_technicals(report: dict):
    ta_json = report.get("technicals_snapshot")
    if not ta_json:
        st.caption("No technical data stored for this report.")
        return
    technicals = json.loads(ta_json) if isinstance(ta_json, str) else ta_json
    valid = [t for t in technicals if not t.get("error")]
    if not valid:
        st.caption("No valid technical data.")
        return

    tickers = [t["ticker"] for t in valid]
    selected = st.selectbox("Ticker", tickers,
                            key=f"ta_{report['id']}", label_visibility="collapsed")
    ta = next(t for t in valid if t["ticker"] == selected)

    if ta.get("summary"):
        st.caption(ta["summary"])

    # ── KPI row ───────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Price", f"${ta.get('current_price', 'N/A')}")
        rsi = ta.get("rsi_14")
        note = ""
        if rsi and rsi > 70:
            note = " (OB)"
        elif rsi and rsi < 30:
            note = " (OS)"
        st.metric("RSI 14", f"{rsi}{note}" if rsi else "N/A")
    with c2:
        st.metric("SMA 20", f"${ta.get('sma_20', 'N/A')}")
        st.metric("SMA 50", f"${ta.get('sma_50', 'N/A')}")
    with c3:
        st.metric("MACD", "Bullish ↑" if ta.get("macd_bullish") else "Bearish ↓")
        vr = ta.get("volume_ratio")
        st.metric("Volume", f"{vr}x avg" if vr else "N/A")
    with c4:
        st.metric("Support", f"${ta.get('support_level', 'N/A')}")
        st.metric("Resistance", f"${ta.get('resistance_level', 'N/A')}")

    d1, d2, d3, d4 = st.columns(4)
    with d1:
        st.metric("5-Day Δ", f"{ta.get('change_5d_pct', 'N/A')}%")
    with d2:
        st.metric("10-Day Δ", f"{ta.get('change_10d_pct', 'N/A')}%")
    with d3:
        st.metric("20-Day Δ", f"{ta.get('change_20d_pct', 'N/A')}%")
    with d4:
        st.metric("From 52W High", f"{ta.get('pct_from_52w_high', 'N/A')}%")

    # ── Interactive price + indicator charts ───────────────────────
    _render_price_chart(selected, ta)

    errors = [t for t in technicals if t.get("error")]
    if errors:
        st.caption(f"⚠ Data unavailable for: {', '.join(e['ticker'] for e in errors)}")


def _render_price_chart(ticker: str, ta: dict):
    """Render interactive Plotly charts: candlestick + volume, RSI, MACD."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    try:
        from data_sources.yahoo_finance import get_price_history
        hist = get_price_history(ticker, period="6mo")
        if hist.empty or len(hist) < 10:
            st.caption("Insufficient price history for charts.")
            return
    except Exception:
        st.caption("Could not load price history for charts.")
        return

    # ── Build 4-panel chart: Price+BB, Volume, RSI, MACD ─────────
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.45, 0.15, 0.2, 0.2],
        subplot_titles=("", "", "RSI (14)", "MACD"),
    )

    dates = hist.index
    close = hist["Close"]
    high = hist["High"]
    low = hist["Low"]
    opn = hist["Open"]
    volume = hist["Volume"]

    # ── Panel 1: Candlestick + Bollinger Bands + SMA ──────────────
    fig.add_trace(go.Candlestick(
        x=dates, open=opn, high=high, low=low, close=close,
        name=ticker, increasing_line_color="#22c55e",
        decreasing_line_color="#ef4444",
    ), row=1, col=1)

    # Bollinger Bands
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    bb_upper = sma20 + 2 * std20
    bb_lower = sma20 - 2 * std20

    fig.add_trace(go.Scatter(
        x=dates, y=bb_upper, name="BB Upper", line=dict(width=1, color="rgba(100,116,139,0.3)"),
        showlegend=False,
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=dates, y=bb_lower, name="BB Lower", line=dict(width=1, color="rgba(100,116,139,0.3)"),
        fill="tonexty", fillcolor="rgba(100,116,139,0.06)", showlegend=False,
    ), row=1, col=1)

    # SMA 20 & 50
    fig.add_trace(go.Scatter(
        x=dates, y=sma20, name="SMA 20", line=dict(width=1.5, color="#b8860b", dash="dot"),
    ), row=1, col=1)
    if len(close) >= 50:
        sma50 = close.rolling(50).mean()
        fig.add_trace(go.Scatter(
            x=dates, y=sma50, name="SMA 50", line=dict(width=1.5, color="#5C9CE6", dash="dot"),
        ), row=1, col=1)

    # ── Panel 2: Volume bars ──────────────────────────────────────
    colors = ["#22c55e" if c >= o else "#ef4444" for c, o in zip(close, opn)]
    fig.add_trace(go.Bar(
        x=dates, y=volume, name="Volume", marker_color=colors, showlegend=False,
    ), row=2, col=1)

    # ── Panel 3: RSI ──────────────────────────────────────────────
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    fig.add_trace(go.Scatter(
        x=dates, y=rsi, name="RSI 14", line=dict(width=1.5, color="#9575CD"),
        showlegend=False,
    ), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", line_width=1, row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="#22c55e", line_width=1, row=3, col=1)
    fig.add_hrect(y0=30, y1=70, fillcolor="rgba(100,116,139,0.05)",
                  line_width=0, row=3, col=1)

    # ── Panel 4: MACD ─────────────────────────────────────────────
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9).mean()
    macd_hist = macd_line - signal_line

    hist_colors = ["#22c55e" if v >= 0 else "#ef4444" for v in macd_hist]
    fig.add_trace(go.Bar(
        x=dates, y=macd_hist, name="MACD Histogram",
        marker_color=hist_colors, showlegend=False,
    ), row=4, col=1)
    fig.add_trace(go.Scatter(
        x=dates, y=macd_line, name="MACD", line=dict(width=1.5, color="#b8860b"),
        showlegend=False,
    ), row=4, col=1)
    fig.add_trace(go.Scatter(
        x=dates, y=signal_line, name="Signal", line=dict(width=1.5, color="#5C9CE6"),
        showlegend=False,
    ), row=4, col=1)

    # ── Layout ────────────────────────────────────────────────────
    _theme = plotly_theme()
    fig.update_layout(
        height=680,
        margin=dict(l=10, r=10, t=30, b=10),
        font=dict(family="Inter, system-ui, sans-serif", size=11, color=_theme["font_color"]),
        paper_bgcolor=_theme["paper_bgcolor"],
        plot_bgcolor=_theme["plot_bgcolor"],
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(size=11, color=_theme["font_color"]),
                    bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
    )
    # Style all axes
    for i in range(1, 5):
        fig.update_xaxes(gridcolor=_theme["gridcolor"], row=i, col=1)
        fig.update_yaxes(gridcolor=_theme["gridcolor"], row=i, col=1)
    fig.update_yaxes(title_text="Price ($)", row=1, col=1)
    fig.update_yaxes(range=[0, 100], row=3, col=1)
    # Subplot title colors
    for ann in fig.layout.annotations:
        ann.font = dict(color=_theme["font_color"], size=12)

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_evidence(report: dict, state: dict | None):
    if not state:
        news_json = report.get("news_snapshot")
        if news_json:
            news = json.loads(news_json) if isinstance(news_json, str) else news_json
            sources = list(set(a.get("source", "") for a in news))
            st.markdown(f"Analysis drew from **{len(news)} articles** across "
                        f"**{len(sources)} sources**: {', '.join(sources)}")
        else:
            st.caption("No source mapping available.")
        return

    articles = state.get("articles", [])
    bullets = state.get("summary_bullet_points", [])

    if bullets:
        for bp in bullets:
            st.markdown(f"• {bp}")
        st.write("")

    if articles:
        sources = list(set(a.get("source", "") for a in articles))
        used = sum(1 for a in articles if a.get("used_in_analysis", True))
        st.caption(f"{used} of {len(articles)} articles used · from {len(sources)} sources")

        for art in articles[:12]:
            title = art.get("title", "Untitled")
            source = art.get("source", "")
            link = art.get("link", "")
            icon = "✓" if art.get("used_in_analysis", True) else "✗"
            if link:
                source_html = (f'<a href="{link}" target="_blank" '
                               f'style="color:#C8A951;font-weight:700;text-decoration:none">'
                               f'{source} ↗</a>')
            else:
                source_html = f'<strong>{source}</strong>'
            st.markdown(
                f'<span style="color:var(--on-surface-variant);font-size:0.82rem">{icon}</span> '
                f'{source_html} — {title}',
                unsafe_allow_html=True)
        if len(articles) > 12:
            st.caption(f"… and {len(articles) - 12} more (expand News Sources below)")

    reasoning = state.get("sufficiency_reasoning", "")
    gaps = state.get("data_gaps", [])
    if reasoning or gaps:
        st.divider()
        st.markdown("**Data Sufficiency Reasoning**")
        if reasoning:
            st.markdown(reasoning)
        for g in gaps:
            st.markdown(f"- ⚠ {g}")


# ═══════════════════════════════════════════════════════════════════
# DEEP-DIVE SECTIONS
# ═══════════════════════════════════════════════════════════════════

def _detail_news(report: dict):
    raw = report.get("news_snapshot")
    if not raw:
        st.caption("No news data stored for this report.")
        return
    news = json.loads(raw) if isinstance(raw, str) else raw
    st.caption(f"{len(news)} articles fed to the AI")

    for i, a in enumerate(news, 1):
        title = a.get("title", "Untitled")
        source = a.get("source", "Unknown")
        published = (a.get("published") or "")[:10]
        summary = (a.get("summary") or "")[:400]
        condensed = a.get("condensed_summary", "")
        link = a.get("link", "")
        relevance = a.get("relevance", "")

        if link:
            st.markdown(f"**{i}. [{title}]({link})**")
        else:
            st.markdown(f"**{i}. {title}**")
        source_display = f"[{source} ↗]({link})" if link else f"_{source}_"
        parts = [source_display]
        if published:
            parts.append(published)
        if relevance:
            parts.append(f"`{relevance}`")
        st.caption(" · ".join(parts))

        if condensed:
            st.success(f"AI Summary: {condensed}")
        if summary:
            st.markdown(f"> {summary}")
        st.markdown("---")


def _detail_rag(state: dict | None):
    if not state:
        st.caption("No RAG context available for this report.")
        return

    rag_context = state.get("rag_context", "")
    rag_meta = state.get("rag_metadata", {})

    try:
        from vectordb.chroma_store import get_store_stats, is_available
        if not is_available():
            st.info(
                "💡 **Enable historical memory with ChromaDB!**\n\n"
                "Install chromadb to let the system remember previous analyses:\n"
                "```\npip install chromadb\n```\n\n"
                "Once installed, each run builds context for smarter future analyses."
            )
            return

        stats = get_store_stats()
        if stats.get("available"):
            cols = st.columns(4)
            col_names = ["news_articles", "sec_filings", "analysis_reports"]
            col_labels = ["📰 News", "📄 Filings", "🧠 Analyses"]
            for i, (cn, cl) in enumerate(zip(col_names, col_labels)):
                with cols[i]:
                    count = stats.get("collections", {}).get(cn, {}).get("count", 0)
                    st.metric(cl, count)
            with cols[3]:
                st.metric("📊 Total", stats.get("total_documents", 0))
    except Exception:
        pass

    st.write("")

    if rag_meta:
        st.caption(
            f"Query results: {rag_meta.get('total_results', 0)} docs retrieved "
            f"({rag_meta.get('news_hits', 0)} news, "
            f"{rag_meta.get('filing_hits', 0)} filings, "
            f"{rag_meta.get('analysis_hits', 0)} analyses) "
            f"in {rag_meta.get('query_time_seconds', 0):.1f}s"
        )
    else:
        st.caption("No RAG query was performed for this run.")

    if rag_context:
        st.markdown("---")
        st.markdown("**Context injected into LLM prompt:**")
        st.markdown(rag_context)
    else:
        st.caption(
            "No historical context was found. This is expected on the first run "
            "for a sector — context accumulates over subsequent analyses."
        )


def _detail_macro(state: dict | None):
    if not state:
        st.caption("No macro data available for this report.")
        return

    macro = state.get("macro_data", {})
    meta = macro.get("_meta", {})

    if meta.get("api_status") == "unavailable":
        st.caption(
            f"Macro data was not available for this run. "
            f"Reason: {meta.get('reason', 'unknown')}"
        )
        st.info(
            "💡 **Get richer analysis with macroeconomic context!**\n\n"
            "1. Get a free FRED API key at https://fred.stlouisfed.org/docs/api/api_key.html\n"
            "2. Add `FRED_API_KEY=your_key_here` to your `.env` file\n"
            "3. Re-run the analysis — it will include Fed rate, CPI, GDP, and more"
        )
        return

    if meta.get("indicators_fetched", 0) == 0:
        st.caption("No macro indicators were fetched for this run.")
        return

    st.caption(
        f"Source: FRED (Federal Reserve Economic Data) · "
        f"{meta.get('indicators_fetched', 0)} indicators · "
        f"Fetched: {meta.get('fetched_at', 'unknown')[:10]}"
    )

    trend_icons = {"rising": "📈", "falling": "📉", "stable": "➡️", "unknown": "❓"}

    indicator_keys = [k for k in macro if k != "_meta"]

    for key in indicator_keys:
        data = macro[key]
        icon = trend_icons.get(data.get("trend", "unknown"), "❓")
        value = data.get("value", "N/A")
        unit = data.get("unit", "")
        name = data.get("name", key)
        trend = data.get("trend", "unknown")
        change = data.get("change")
        description = data.get("description", "")

        change_str = f" ({change:+.2f})" if change is not None else ""

        with st.container(border=True):
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown(f"### {icon}")
                st.markdown(f"**{value}{unit}**{change_str}")
            with col2:
                st.markdown(f"**{name}** — *{trend}*")
                st.caption(description[:200])

                interp = data.get("interpretation", {})
                if trend in interp:
                    st.markdown(f"🔍 {interp[trend]}")


def _detail_filings(report: dict):
    raw = report.get("filings_snapshot")
    if not raw:
        st.caption("No filings stored for this report.")
        return
    filings = json.loads(raw) if isinstance(raw, str) else raw
    valid = [f for f in filings if "error" not in f]
    if not valid:
        st.caption("No valid filings found.")
        return

    with_text = [f for f in valid if f.get("text_total_chars", 0) > 0]
    st.caption(
        f"{len(valid)} SEC filings · {len(with_text)} with extracted text content"
    )

    st.info(
        "💡 **New to SEC filings?** Learn how to read them: "
        "[SEC Investor Guide →](https://www.investor.gov/introduction-investing/general-resources/"
        "news-alerts/alerts-bulletins/investor-bulletins/how-read)"
    )

    for f in valid:
        ftype = f.get("type", "")
        ticker = f.get("ticker", "")
        date = f.get("date", "")
        type_name = f.get("type_name", ftype)

        with st.container(border=True):
            st.markdown(f"### {ticker} — {ftype} ({type_name})")
            st.caption(f"Filed: {date}")

            explanation = f.get("type_explanation", "")
            why_matters = f.get("type_why_it_matters", "")
            learn_url = f.get("learn_more_url", "")

            if explanation or why_matters:
                with st.expander(f"ℹ️ What is a {ftype}?"):
                    if explanation:
                        st.markdown(f"**What it is:** {explanation}")
                    if why_matters:
                        st.markdown(f"**Why it matters:** {why_matters}")
                    if learn_url:
                        st.markdown(f"[Learn more about {ftype} filings →]({learn_url})")

            desc = f.get("description", "")
            if desc:
                st.markdown(f"*{desc}*")

            sections = f.get("text_sections", [])
            if sections:
                for sec in sections:
                    with st.expander(f"📄 {sec.get('name', 'Section')}"):
                        st.markdown(sec.get("text", ""))
            else:
                note = f.get("text_extraction_note", "")
                if note:
                    st.caption(f"⚠️ {note}")

            url = f.get("url", "")
            if url:
                st.markdown(f"[View full filing on SEC.gov →]({url})")


def _detail_llm_io(state: dict | None):
    if not state:
        st.caption("No LLM data available.")
        return
    nodes = state.get("node_executions", [])
    llm_nodes = [n for n in nodes
                 if n.get("llm_model")
                 and (n.get("llm_prompt_tokens", 0) > 0
                      or n.get("llm_completion_tokens", 0) > 0)]
    if not llm_nodes:
        st.caption("No LLM calls with data recorded.")
        return

    st.caption(f"{len(llm_nodes)} LLM calls in this pipeline run")
    for n in llm_nodes:
        name = n.get("node_name", "?")
        model = n.get("llm_model", "?")
        pt = n.get("llm_prompt_tokens", 0)
        ct = n.get("llm_completion_tokens", 0)

        st.markdown(f"**{name}** · `{model}` · {pt:,} prompt → {ct:,} completion tokens")

        prompt = (n.get("llm_user_prompt") or "").strip()
        resp = (n.get("llm_raw_response") or "").strip()

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Prompt →**")
            if prompt:
                st.code(prompt[:3000], language="text")
            else:
                st.caption("(system-level prompt — not captured)")
        with c2:
            st.markdown("**← Response**")
            if resp:
                st.code(resp[:3000], language="text")
            else:
                st.caption("(response stored in structured fields)")
        st.markdown("---")


def _detail_trace(state: dict | None):
    if not state:
        st.caption("No pipeline trace available.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Run ID", state.get("run_id", "?"))
    with c2:
        st.metric("Status", state.get("pipeline_status", "?"))
    with c3:
        total_tok = (state.get("total_llm_prompt_tokens", 0)
                     + state.get("total_llm_completion_tokens", 0))
        st.metric("LLM Tokens", f"{total_tok:,}")

    st.write("")
    for n in state.get("node_executions", []):
        name = n.get("node_name", "?")
        dur = n.get("duration_seconds", 0)
        ns = n.get("status", "?")
        decision = n.get("decision", "")
        model = n.get("llm_model", "")
        dot_cls = "dot-ok" if ns == "completed" else "dot-err"
        model_tag = f' · <span style="color:var(--on-surface-variant)">{model}</span>' if model else ""
        dec_tag = f' → <strong>{decision}</strong>' if decision else ""

        st.markdown(
            f'<div class="node-row">'
            f'<div class="node-dot {dot_cls}"></div>'
            f'<span><strong>{name}</strong>{model_tag}</span>'
            f'<span style="margin-left:auto;color:var(--on-surface-variant)">{dur:.1f}s{dec_tag}</span>'
            f'</div>', unsafe_allow_html=True)


def _detail_timing(report: dict):
    raw = report.get("timing_snapshot")
    if not raw:
        st.caption("No timing data stored.")
        return
    timing = json.loads(raw) if isinstance(raw, str) else raw
    total = timing.get("total_seconds", 0)
    st.metric("Total", f"{total:.1f}s")

    for s in timing.get("steps", []):
        name = s.get("name", "?")
        sec = s.get("seconds", 0)
        pct = sec / max(total, 0.1) * 100
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;font-size:0.88rem">'
            f'<span>{name}</span>'
            f'<span style="color:var(--on-surface-variant)">{sec:.1f}s ({pct:.0f}%)</span></div>'
            f'<div class="bar-track">'
            f'<div class="bar-fill bar-blue" style="width:{min(pct, 100)}%"></div></div>',
            unsafe_allow_html=True)
