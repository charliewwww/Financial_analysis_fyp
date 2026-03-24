"""
Reports page — list view + detail view, driven by session state.
"""

import json
import streamlit as st

from config.sectors import SECTORS
from database.reports_db import get_reports_list, get_report_by_id
from utils.markdown_export import export_report_markdown
from ui.components import (
    SECTOR_COLORS, ring_svg, pill_cls, load_state, linkify_sources, report_row,
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
                'letter-spacing:-0.03em;color:#0f172a">Reports</h2>',
                unsafe_allow_html=True)

    c1, _ = st.columns([2, 4])
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
        st.info("No reports yet. Run an analysis from the Dashboard.")
        return

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
        md_text = export_report_markdown(report, state)
        sector_slug = report.get("sector_id", "report").replace(" ", "_")
        date_slug = report.get("created_at", "")[:10]
        st.download_button(
            label="📥 Download Markdown",
            data=md_text,
            file_name=f"{sector_slug}_{date_slug}.md",
            mime="text/markdown",
            width="stretch",
        )

    conf = report.get("confidence_score", 0) or 0
    date_str = to_hkt(report["created_at"])
    st.markdown(f'<h2 style="font-family:Manrope,sans-serif;font-weight:800;'
                f'letter-spacing:-0.03em;color:#0f172a;margin-bottom:0">{report["sector_name"]}</h2>',
                unsafe_allow_html=True)
    st.caption(f"Report #{report['id']} · {date_str}")

    # ── Key takeaway banner ───────────────────────────────────────
    ns = report.get("news_summary", "")
    if ns:
        st.info(ns)

    # ── Metric cards row ──────────────────────────────────────────
    m1, m2, m3, m4, m5, m6 = st.columns([1.2, 1, 1, 1, 1, 1])
    with m1:
        with st.container(border=True):
            st.markdown(ring_svg(conf, size=110), unsafe_allow_html=True)
    with m2:
        with st.container(border=True):
            vs = report.get("validation_status", "")
            st.markdown('<span class="micro-label">Validation</span>',
                        unsafe_allow_html=True)
            st.markdown(f'<span class="pill {pill_cls(vs)}">{vs or "N/A"}</span>',
                        unsafe_allow_html=True)
    with m3:
        with st.container(border=True):
            n_articles = report.get("news_used", 0)
            prices_json = report.get("prices_snapshot")
            n_tickers = 0
            if prices_json:
                p_list = json.loads(prices_json) if isinstance(prices_json, str) else prices_json
                n_tickers = len([p for p in p_list if not p.get("error")])
            st.metric("Articles", n_articles)
            st.caption(f"{n_tickers} tickers tracked")
    with m4:
        with st.container(border=True):
            ds = report.get("data_sufficiency", "")
            ds_color = {"sufficient": "#22c55e", "marginal": "#f59e0b",
                        "insufficient": "#ef4444"}.get(ds, "#64748b")
            st.markdown('<span class="micro-label">Data Quality</span>',
                        unsafe_allow_html=True)
            st.markdown(
                f'<span style="color:{ds_color};font-weight:800;font-size:1.1rem;'
                f'font-family:Manrope,sans-serif">'
                f'● {ds.title() if ds else "N/A"}</span>',
                unsafe_allow_html=True)
    with m5:
        with st.container(border=True):
            macro_status = "—"
            macro_count = 0
            if state:
                mm = state.get("macro_data", {}).get("_meta", {})
                if mm.get("api_status") == "ok":
                    macro_count = mm.get('indicators_fetched', 0)
                    macro_status = f"{macro_count} ind."
                elif mm.get("api_status") == "partial":
                    macro_status = "Partial"
            st.markdown('<span class="micro-label">Macro</span>',
                        unsafe_allow_html=True)
            st.markdown(
                f'<span style="font-weight:800;font-size:1.5rem;color:#0f172a;'
                f'font-family:Manrope,sans-serif">'
                f'{macro_status}</span>',
                unsafe_allow_html=True)
            rag_hits = 0
            if state:
                rag_hits = state.get("rag_metadata", {}).get("total_results", 0)
            st.caption(f"{rag_hits} RAG docs" if rag_hits else "No RAG context")
    with m6:
        with st.container(border=True):
            timing_json = report.get("timing_snapshot")
            total_t = 0
            if timing_json:
                t = json.loads(timing_json) if isinstance(timing_json, str) else timing_json
                total_t = t.get("total_seconds", 0)
            st.markdown('<span class="micro-label">Pipeline</span>',
                        unsafe_allow_html=True)
            st.markdown(
                f'<span style="font-weight:800;font-size:1.5rem;color:#0f172a;'
                f'font-family:Manrope,sans-serif">'
                f'{total_t:.0f}s</span>',
                unsafe_allow_html=True)
            n_nodes = 0
            if state:
                n_nodes = len(state.get("node_executions", []))
            st.caption(f"{n_nodes} nodes executed")

    st.write("")

    # ── Analysis card ─────────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<span class="section-title">✨ Analysis</span>',
                    unsafe_allow_html=True)
        st.write("")
        analysis_text = report.get("analysis", "*No analysis available.*")

        # Build article list for linkification
        news_json = report.get("news_snapshot")
        articles_for_links = []
        if news_json:
            try:
                articles_for_links = json.loads(news_json) if isinstance(news_json, str) else news_json
            except (json.JSONDecodeError, TypeError):
                pass

        # Make [SOURCE: ...] citations clickable
        linked_analysis = linkify_sources(analysis_text, articles_for_links)
        st.markdown(linked_analysis, unsafe_allow_html=True)

    st.write("")

    # ── Side-by-side: Confidence breakdown + Supply chain ─────────
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.markdown('<span class="section-title">Confidence Breakdown</span>',
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
            st.markdown(f'<span class="pill {pill_cls(vs)}">{vs}</span>',
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

    # ── Anomaly alerts ────────────────────────────────────────────
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

    # ── Technical analysis ────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<span class="section-title">Technical Analysis</span>',
                    unsafe_allow_html=True)
        _render_technicals(report)

    st.write("")

    # ── Evidence trail ────────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<span class="section-title">Evidence Trail</span>',
                    unsafe_allow_html=True)
        st.caption("How data sources support each conclusion")
        _render_evidence(report, state)

    st.write("")

    # ── Deep dives ────────────────────────────────────────────────
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
            f'<div style="font-size:0.75rem;color:#9C9C9C;margin-bottom:8px">{note}</div>',
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

    errors = [t for t in technicals if t.get("error")]
    if errors:
        st.caption(f"⚠ Data unavailable for: {', '.join(e['ticker'] for e in errors)}")


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
                f'<span style="color:#9C9C9C;font-size:0.82rem">{icon}</span> '
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
        model_tag = f' · <span style="color:#9C9C9C">{model}</span>' if model else ""
        dec_tag = f' → <strong>{decision}</strong>' if decision else ""

        st.markdown(
            f'<div class="node-row">'
            f'<div class="node-dot {dot_cls}"></div>'
            f'<span><strong>{name}</strong>{model_tag}</span>'
            f'<span style="margin-left:auto;color:#9C9C9C">{dur:.1f}s{dec_tag}</span>'
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
            f'<span style="color:#9C9C9C">{sec:.1f}s ({pct:.0f}%)</span></div>'
            f'<div class="bar-track">'
            f'<div class="bar-fill bar-blue" style="width:{min(pct, 100)}%"></div></div>',
            unsafe_allow_html=True)
