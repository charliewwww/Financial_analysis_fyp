"""
Dashboard page — KPI row, recent reports, sector health, run analysis CTA.

Background execution: analysis runs in a threading.Thread so the Streamlit
event loop can still rerun and poll progress.  A shared dict in
st.session_state tracks log lines, results, and completion status.
"""

import streamlit as st
import html
import threading
import time as _time

_MAX_ANALYSIS_SECONDS = 1800  # 30-minute hard timeout

from config.sectors import SECTORS
# NOTE: workflow / LLM imports are LAZY (inside _analysis_worker)
# to avoid loading langgraph + chromadb + yfinance on every page render.
from database.reports_db import get_reports_list, get_prediction_accuracy, get_report_count
from data_sources.yahoo_finance import get_sector_prices
from ui.components import SECTOR_COLORS, SECTOR_DOT_CLASS, ring_svg, report_row
from utils.time_utils import to_hkt_short


# ── Cached loaders (thin wrappers) ───────────────────────────────

@st.cache_data(ttl=30)
def _cached_reports_list(sector_id: str | None = None, limit: int = 50):
    return get_reports_list(sector_id=sector_id, limit=limit)


@st.cache_data(ttl=30)
def _cached_prediction_stats():
    return get_prediction_accuracy()


@st.cache_data(ttl=30)
def _cached_report_count():
    return get_report_count()


@st.cache_data(ttl=300)
def _cached_sector_prices():
    """Fetch current prices for all sector tickers (cached 5 min)."""
    all_tickers = []
    ticker_sector = {}
    for sid, sec in SECTORS.items():
        for t in sec["tickers"]:
            all_tickers.append(t)
            ticker_sector[t] = sid
    snapshots = get_sector_prices(all_tickers)
    return snapshots, ticker_sector


def _open_report(report_id: int):
    st.session_state.page = "Analysis"
    st.session_state.selected_report_id = report_id


# ── Market Pulse & Delta helpers ──────────────────────────────────

@st.cache_data(ttl=60)
def _cached_market_pulse():
    """Load key signals, anomalies, and theses from latest report per sector."""
    from database.reports_db import get_report_by_id
    from ui.components import extract_signals, extract_thesis, load_state

    reports = _cached_reports_list(limit=50)
    if not reports:
        return {"signals": [], "anomalies": [], "theses": [], "last_analysis": None}

    seen_sectors = set()
    signals, anomalies, theses = [], [], []
    last_analysis = reports[0]["created_at"] if reports else None

    for r in reports:
        sid = r["sector_id"]
        if sid in seen_sectors:
            continue
        seen_sectors.add(sid)

        full = get_report_by_id(r["id"])
        if not full:
            continue

        analysis = full.get("analysis", "")
        thesis = extract_thesis(analysis)
        if thesis:
            theses.append({"sector": r["sector_name"], "sector_id": sid, "thesis": thesis})

        for s in extract_signals(analysis)[:3]:
            s["sector"] = r["sector_name"]
            signals.append(s)

        state = load_state(full)
        if state:
            for a in state.get("anomaly_alerts", []):
                a["sector"] = r["sector_name"]
                anomalies.append(a)

    return {
        "signals": signals,
        "anomalies": anomalies,
        "theses": theses,
        "last_analysis": last_analysis,
    }


@st.cache_data(ttl=60)
def _cached_sector_deltas():
    """Compare latest vs previous report per sector."""
    reports = _cached_reports_list(limit=50)
    if not reports:
        return []

    by_sector: dict[str, list] = {}
    for r in reports:
        sid = r["sector_id"]
        by_sector.setdefault(sid, []).append(r)

    deltas = []
    for sid, rpts in by_sector.items():
        if len(rpts) < 2:
            continue
        latest, prev = rpts[0], rpts[1]
        conf_now = latest.get("confidence_score") or 0
        conf_prev = prev.get("confidence_score") or 0
        deltas.append({
            "sector": latest["sector_name"],
            "sector_id": sid,
            "current": conf_now,
            "previous": conf_prev,
            "delta": round(conf_now - conf_prev, 1),
        })
    return deltas


def _render_market_pulse(pulse: dict):
    """Render the Market Pulse section — key alerts and signals."""
    anomaly_count = len(pulse["anomalies"])
    high_sev = [a for a in pulse["anomalies"] if a.get("severity") == "high"]
    bullish = [s for s in pulse["signals"] if s.get("direction") == "BULLISH"]
    bearish = [s for s in pulse["signals"] if s.get("direction") == "BEARISH"]

    with st.container(border=True):
        hdr_l, hdr_r = st.columns([3, 1])
        with hdr_l:
            st.markdown('<span class="section-title" style="font-size:1.1rem">⚡ Market Pulse</span>',
                        unsafe_allow_html=True)
        with hdr_r:
            if pulse["last_analysis"]:
                st.caption(f"Last scan: {to_hkt_short(pulse['last_analysis'])}")

        # Summary stat bar
        stat_parts = []
        if high_sev:
            stat_parts.append(f'<span style="color:#ef4444;font-weight:700">🔴 {len(high_sev)} critical alert{"s" if len(high_sev)!=1 else ""}</span>')
        elif anomaly_count:
            stat_parts.append(f'<span style="color:#f59e0b;font-weight:700">⚠️ {anomaly_count} anomal{"ies" if anomaly_count!=1 else "y"}</span>')
        if bullish:
            stat_parts.append(f'<span style="color:#22c55e;font-weight:700">📈 {len(bullish)} bullish</span>')
        if bearish:
            stat_parts.append(f'<span style="color:#ef4444;font-weight:700">📉 {len(bearish)} bearish</span>')
        if stat_parts:
            st.markdown(
                '<div style="display:flex;gap:16px;flex-wrap:wrap;font-size:0.85rem;margin-bottom:0.5rem">'
                + " ".join(stat_parts) + '</div>',
                unsafe_allow_html=True)

        # High-severity anomaly alerts
        for a in high_sev[:3]:
            st.markdown(
                f'🔴 **{a.get("ticker", "?")}** [{a.get("signal_type", "?")}] — '
                f'{a.get("description", "N/A")}')

        # Sector theses
        for t in pulse["theses"]:
            thesis_short = t["thesis"][:180] + ("…" if len(t["thesis"]) > 180 else "")
            st.markdown(f'📋 **{t["sector"]}** — {thesis_short}')

        # Top signal cards (compact grid)
        top_signals = pulse["signals"][:6]
        if top_signals:
            cols = st.columns(min(len(top_signals), 3))
            for i, sig in enumerate(top_signals):
                with cols[i % len(cols)]:
                    d = sig.get("direction", "NEUTRAL")
                    icon = {"BULLISH": "📈", "BEARISH": "📉"}.get(d, "➡️")
                    color = {"BULLISH": "#22c55e", "BEARISH": "#ef4444"}.get(d, "#94a3b8")
                    move_text = f' · {html.escape(sig["move"])}' if sig.get("move") else ""
                    st.markdown(
                        f'<div style="padding:8px 12px;border-radius:10px;'
                        f'border:1px solid var(--outline-variant);margin-bottom:4px">'
                        f'<span style="font-weight:800;font-family:Manrope,sans-serif">'
                        f'{html.escape(sig["ticker"])}</span> '
                        f'<span style="color:{color};font-weight:700;font-size:0.82rem">'
                        f'{icon} {d}{move_text}</span></div>',
                        unsafe_allow_html=True)


def _render_sector_deltas(deltas: list[dict]):
    """Render the 'What Changed' section showing evidence score movement."""
    if not deltas:
        return
    with st.container(border=True):
        st.markdown('<span class="section-title">📊 What Changed</span>',
                    unsafe_allow_html=True)
        st.caption("Evidence score movement since previous analysis")
        for d in deltas:
            arrow = "↑" if d["delta"] > 0 else ("↓" if d["delta"] < 0 else "→")
            color = "#22c55e" if d["delta"] > 0 else ("#ef4444" if d["delta"] < 0 else "#94a3b8")
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:0.5rem 0;border-bottom:1px solid var(--outline-variant)">'
                f'<span style="font-weight:600;font-size:0.88rem">{html.escape(d["sector"])}</span>'
                f'<span style="font-weight:700;color:{color};font-size:0.88rem">'
                f'{d["previous"]:.1f} → {d["current"]:.1f} '
                f'<span style="font-size:0.75rem">{arrow} {d["delta"]:+.1f}</span></span></div>',
                unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# PAGE ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def render():
    # Invisible heading for structure — page title is in the top bar area
    st.markdown('<h2 style="font-family:Manrope,sans-serif;font-weight:800;'
                'letter-spacing:-0.03em;color:var(--on-surface);margin-bottom:0.5rem">'
                'Overview</h2>', unsafe_allow_html=True)
    st.caption("Market intelligence and second-order signal detection")

    all_rpts = _cached_reports_list(limit=50)
    stats = _cached_prediction_stats()

    # ── First-run welcome ─────────────────────────────────────────
    if not all_rpts:
        st.markdown(
            '<div style="background:linear-gradient(135deg,rgba(184,134,11,0.06) 0%,'
            'rgba(212,175,55,0.04) 100%);border:1px solid rgba(184,134,11,0.15);'
            'border-radius:1.5rem;padding:2rem 2.5rem;margin-bottom:1.5rem">'
            '<h3 style="font-family:Manrope,sans-serif;font-weight:800;'
            'letter-spacing:-0.02em;margin:0 0 0.5rem 0;color:var(--on-surface)">'
            'Welcome to MarketPulse</h3>'
            '<p style="color:var(--on-surface-variant);font-size:0.9rem;line-height:1.7;margin:0">'
            'Your AI-powered finance intelligence platform. It analyses stocks across '
            '<strong>3 sectors</strong> using multi-agent reasoning — pulling live news, '
            'SEC filings, technical indicators, and macroeconomic data — then validates '
            'every claim against real numbers.<br><br>'
            '👇 <strong>Click Run Analysis below</strong> to generate your first report.</p>'
            '</div>',
            unsafe_allow_html=True)

    avg_conf = 0.0
    if all_rpts:
        confs = [r["confidence_score"] for r in all_rpts if r.get("confidence_score")]
        avg_conf = round(sum(confs) / len(confs), 1) if confs else 0

    # ── Storage warning (reports auto-purge at MAX_REPORTS) ────────
    from config.settings import MAX_REPORTS
    report_total = _cached_report_count()
    warn_threshold = int(MAX_REPORTS * 0.8)  # warn at 80% capacity
    if report_total >= warn_threshold:
        remaining = max(MAX_REPORTS - report_total, 0)
        if remaining == 0:
            st.warning(
                "⚠️ **Storage full — oldest reports will be deleted** when new ones are created. "
                "Download any reports you want to keep from the Reports page. "
                "Predictions are always preserved.",
                icon="📥")
        else:
            st.info(
                f"📦 **{report_total}/{MAX_REPORTS} report slots used** — {remaining} left before auto-cleanup. "
                "Download reports you want to keep. Predictions are always preserved.")

    # ── Compact Run Analysis bar ──────────────────────────────────
    all_sector_ids = list(SECTORS.keys())
    all_sector_names = [SECTORS[s]["name"] for s in all_sector_ids]

    with st.container(border=True):
        cta_l, cta_r = st.columns([4, 1])
        with cta_l:
            selected_names = st.multiselect(
                "Sectors to analyse",
                options=all_sector_names,
                default=all_sector_names,
                label_visibility="collapsed",
            )
        with cta_r:
            _name_to_id = {SECTORS[s]["name"]: s for s in all_sector_ids}
            selected_ids = [_name_to_id[n] for n in selected_names if n in _name_to_id]
            run = st.button("🚀 Run Analysis", type="primary",
                            disabled=len(selected_ids) == 0,
                            use_container_width=True)

    if run and selected_ids:
        _start_background_analysis(selected_ids)

    # ── Show progress / results from background thread ────────────
    _render_analysis_progress()

    st.write("")

    # ── Market Pulse (key signals from latest reports) ────────────
    if all_rpts:
        pulse = _cached_market_pulse()
        if pulse["signals"] or pulse["anomalies"] or pulse["theses"]:
            _render_market_pulse(pulse)
            st.write("")

    # ── KPI row ───────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    kpi_data = [
        (k1, "Reports Generated", str(len(all_rpts)), ""),
        (k2, "Evidence Score", f"{avg_conf}", "/ 10.0"),
        (k3, "Active Predictions", str(stats['total_predictions']), ""),
        (k4, "Verified Accuracy", f"{stats['checked']}", f"/ {stats['total_predictions']}"),
    ]
    for col, label, value, sub in kpi_data:
        with col:
            st.markdown(
                f'<div class="kpi-card">'
                f'<div class="kpi-label">{label}</div>'
                f'<div style="display:flex;align-items:baseline;gap:0.5rem">'
                f'<span class="kpi-value">{value}</span>'
                f'<span class="kpi-sub">{sub}</span>'
                f'</div></div>',
                unsafe_allow_html=True)

    st.write("")

    # ── Sector Snapshot — live price ticker strip ─────────────────
    try:
        snapshots, ticker_sector = _cached_sector_prices()
        valid = [s for s in snapshots if not s.get("error") and s.get("price")]
        if valid:
            chips_html = '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:1rem">'
            for s in valid:
                sid = ticker_sector.get(s["ticker"], "")
                dot_cls = SECTOR_DOT_CLASS.get(sid, "optical")
                chg = s.get("change_1w_pct")
                if chg is not None:
                    chg_color = "#22c55e" if chg >= 0 else "#ef4444"
                    chg_str = f'<span style="color:{chg_color};font-weight:700;font-size:0.72rem">' \
                              f'{"+" if chg >= 0 else ""}{chg:.1f}%</span>'
                else:
                    chg_str = ""
                chips_html += (
                    f'<div style="display:flex;align-items:center;gap:8px;'
                    f'background:var(--surface-card);border:1px solid var(--outline-variant);'
                    f'border-radius:12px;padding:8px 14px;font-family:Manrope,sans-serif">'
                    f'<span class="sector-dot {dot_cls}" style="width:6px;height:6px"></span>'
                    f'<span style="font-weight:800;font-size:0.8rem;color:var(--on-surface);'
                    f'letter-spacing:-0.01em">{html.escape(s["ticker"])}</span>'
                    f'<span style="font-weight:700;font-size:0.8rem;color:var(--on-surface)">'
                    f'${s["price"]:.2f}</span>'
                    f'{chg_str}'
                    f'</div>'
                )
            chips_html += '</div>'
            st.markdown(chips_html, unsafe_allow_html=True)
    except Exception:
        pass  # graceful degradation — network issues shouldn't break dashboard

    # ── Two-column body ───────────────────────────────────────────
    col_left, col_right = st.columns([7, 5])

    with col_left:
        with st.container(border=True):
            # Header row: title + "View All Activity" link
            hdr_l, hdr_r = st.columns([3, 1])
            with hdr_l:
                st.markdown('<span class="section-title" style="font-size:1.35rem">' 
                            'Intelligence Feed</span>', unsafe_allow_html=True)
            with hdr_r:
                if st.button("View All →", key="view_all_rpts", type="tertiary"):
                    st.session_state.page = "Analysis"
                    st.rerun()

            st.write("")
            recent = all_rpts[:8]
            if not recent:
                st.caption("No reports yet — run your first analysis above.")
            else:
                for r in recent:
                    report_row(r, f"dash_{r['id']}", _open_report)
                if len(all_rpts) > 8:
                    st.caption(f"Showing 8 of {len(all_rpts)} — see Reports page for all.")

    with col_right:
        # ── Confidence Index card (designer style) ────────────
        with st.container(border=True):
            ci_l, ci_r = st.columns([1, 1])
            with ci_l:
                st.markdown('<span class="section-title">Evidence Score</span>',
                            unsafe_allow_html=True)
                st.write("")
                st.markdown(ring_svg(avg_conf, size=144), unsafe_allow_html=True)
            with ci_r:
                st.write("")
                st.write("")
                if avg_conf >= 7:
                    st.markdown('<span style="display:inline-block;padding:4px 12px;'
                                'background:rgba(184,134,11,0.1);color:var(--primary);'
                                'font-size:0.625rem;font-weight:800;border-radius:9999px;'
                                'text-transform:uppercase;letter-spacing:0.1em">'
                                'Optimal Range</span>', unsafe_allow_html=True)
                st.caption(f"Objective data-quality score based on "
                           f"**{len(all_rpts)} reports** across all sectors.")

            # ── Confidence Trend (mini chart) ─────────────────
            if len(all_rpts) >= 2:
                import plotly.graph_objects as go
                trend_data = sorted(
                    [r for r in all_rpts if r.get("confidence_score")],
                    key=lambda r: r["id"],
                )[-20:]  # last 20 reports
                if len(trend_data) >= 2:
                    x_vals = list(range(1, len(trend_data) + 1))
                    y_vals = [r["confidence_score"] for r in trend_data]
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=x_vals, y=y_vals, mode="lines+markers",
                        line=dict(color="#b8860b", width=2),
                        marker=dict(size=5, color="#d4af37"),
                        hovertemplate="Report %{x}<br>Confidence: %{y:.1f}<extra></extra>",
                    ))
                    fig.update_layout(
                        height=120, margin=dict(l=0, r=0, t=5, b=20),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                        yaxis=dict(range=[0, 10.5], showgrid=True,
                                   gridcolor="rgba(0,0,0,0.05)", showticklabels=True,
                                   tickfont=dict(size=9, color="#94a3b8"),
                                   zeroline=False),
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        st.write("")

        # ── Asset Health Monitor (sector bars) ──────────────
        with st.container(border=True):
            st.markdown('<span class="section-title">Asset Health Monitor</span>',
                        unsafe_allow_html=True)
            st.write("")
            for sid, sec in SECTORS.items():
                matches = [r for r in all_rpts if r["sector_id"] == sid]
                dot_cls = SECTOR_DOT_CLASS.get(sid, "optical")
                if matches:
                    latest = matches[0]
                    conf = latest.get("confidence_score", 0) or 0
                    pct = conf / 10 * 100
                    right_lbl = f"{pct:.0f}%"
                else:
                    pct, right_lbl = 0, "0%"

                bar_cls = f"bar-{dot_cls}"
                st.markdown(
                    f'<div style="margin-bottom:1.5rem">'
                    f'<div style="display:flex;justify-content:space-between;'
                    f'align-items:center;margin-bottom:0.35rem">'
                    f'<span style="font-size:0.75rem;font-weight:700;'
                    f'text-transform:uppercase;letter-spacing:0.05em;'
                    f'color:var(--on-surface-variant)">{sec["name"]}</span>'
                    f'<span style="font-size:0.75rem;font-weight:700;'
                    f'color:var(--on-surface)">{right_lbl}</span>'
                    f'</div>'
                    f'<div class="bar-track">'
                    f'<div class="bar-fill {bar_cls}" style="width:{pct}%"></div>'
                    f'</div></div>',
                    unsafe_allow_html=True)

    st.write("")

    # ── What Changed (delta between latest and previous) ──────────
    if all_rpts:
        deltas = _cached_sector_deltas()
        if deltas:
            _render_sector_deltas(deltas)

    st.write("")


# ═══════════════════════════════════════════════════════════════════
# BACKGROUND ANALYSIS ENGINE
# ═══════════════════════════════════════════════════════════════════

_JOB_KEY = "_analysis_job"          # session-state key for the shared dict
_job_lock = threading.Lock()        # protects mutation of shared dicts


def _new_job() -> dict:
    """Thread-safe job dict stored in session_state."""
    return {
        "running": True,
        "error": None,
        "log": [],           # list of (icon, text) tuples
        "results": [],       # sector result dicts
        "started_at": _time.time(),
        "finished_at": None,
        "cancel": threading.Event(),  # set() to request cancellation
        "cancelled": False,
        "total_sectors": 0,
        "completed_sectors": 0,
        "active_node": None,          # currently executing graph node
        "completed_nodes": [],        # list of node names already finished
    }


def _start_background_analysis(selected_ids: list[str] | None = None):
    """Launch the analysis in a daemon thread so the UI can poll."""
    if st.session_state.get(_JOB_KEY, {}).get("running"):
        return  # Already running — don't double-start

    job = _new_job()
    st.session_state[_JOB_KEY] = job

    t = threading.Thread(target=_analysis_worker, args=(job, selected_ids), daemon=True)
    t.start()


def _analysis_worker(job: dict, selected_ids: list[str] | None = None):
    """Runs in a background thread — writes progress into `job` dict."""
    # Lazy imports — only loaded when analysis actually runs
    from workflows.weekly_analysis import run_sector_analysis, check_old_predictions
    from agents.llm_client import (
        check_llm_health, LLMHealthCheckError, PipelineCancelled,
        request_cancellation, reset_cancellation,
    )
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from config.settings import LLM_PROVIDER

    # Clear any stale cancellation from a previous run
    reset_cancellation()

    # Filter sectors if user selected specific ones
    sectors_to_run = {
        sid: sec for sid, sec in SECTORS.items()
        if selected_ids is None or sid in selected_ids
    }

    def _log(icon, text):
        with _job_lock:
            job["log"].append((icon, text))

    def _run_one(sid: str, sector: dict, idx: int, total: int):
        """Run a single sector analysis (called from thread pool)."""
        label = f"[{idx}/{total}] 📈 {sector['name']}"
        _log("⏳", label)

        def on_progress(event_type, message, _name=sector["name"]):
            if event_type == "node":
                _log("  ↳", f"{_name}: {message}")
                # Track active node for the live pipeline graph
                node_map = {
                    "📡": "fetch", "📝": "summarize", "🤔": "reflect",
                    "🧠": "analyze", "✅": "validate", "📊": "score",
                    "💾": "save",
                }
                for emoji, node_name in node_map.items():
                    if emoji in message:
                        with _job_lock:
                            prev = job.get("active_node")
                            if prev and prev != node_name and prev not in job["completed_nodes"]:
                                job["completed_nodes"].append(prev)
                            job["active_node"] = node_name
                        break

        result = run_sector_analysis(sid, sector, progress_fn=on_progress)
        # Reset pipeline graph for next sector
        with _job_lock:
            if job.get("active_node") and job["active_node"] not in job["completed_nodes"]:
                job["completed_nodes"].append(job["active_node"])
            job["active_node"] = None
            job["completed_nodes"] = []
        if result.get("error"):
            _log("❌", f"{sector['name']}: {result['error']}")
        else:
            conf = result.get("confidence", 0)
            t = result.get("timing", {}).get("total_seconds", 0)
            news = result.get("news_count", 0)
            _log("✅", f"{sector['name']} — {conf}/10 · {news} articles · {t:.0f}s")
        return result

    try:
        _log("🔍", "Checking LLM connection…")
        check_llm_health()
        _log("✅", "LLM connected")

        _log("🗄️", "Warming up vector database…")
        try:
            from vectordb.chroma_store import warm_up as _chroma_warm_up
            _chroma_warm_up()
            _log("✅", "Vector database ready")
        except Exception:
            _log("⚠️", "Vector database unavailable — continuing without RAG")

        total = len(sectors_to_run)
        # Cloud LLM → run all sectors in parallel; local GPU → one at a time
        if LLM_PROVIDER == "ollama":
            max_parallel = 1
            mode_label = "sequential (local GPU)"
        else:
            max_parallel = total
            mode_label = f"all {total} in parallel (cloud LLM)"
        _log("🚀", f"Running {total} sector{'s' if total != 1 else ''} — {mode_label}")
        with _job_lock:
            job["total_sectors"] = total

        with ThreadPoolExecutor(max_workers=max_parallel) as pool:
            futures = {}
            for i, (sid, sector) in enumerate(sectors_to_run.items(), 1):
                if job["cancel"].is_set():
                    break
                # Stagger sector launches to avoid simultaneous LLM calls
                # hitting rate limits (especially on free-tier providers)
                if i > 1 and max_parallel > 1:
                    _time.sleep(5)
                future = pool.submit(_run_one, sid, sector, i, total)
                futures[future] = sid

            for future in as_completed(futures):
                # Check cancellation
                if job["cancel"].is_set():
                    request_cancellation()
                    job["cancelled"] = True
                    _log("⚠️", "Analysis cancelled by user")
                    break
                # Check hard timeout
                elapsed = _time.time() - job["started_at"]
                if elapsed > _MAX_ANALYSIS_SECONDS:
                    request_cancellation()
                    job["error"] = f"Timed out after {elapsed:.0f}s (limit: {_MAX_ANALYSIS_SECONDS}s)"
                    _log("⏰", "Analysis timed out")
                    break
                try:
                    result = future.result()
                    with _job_lock:
                        job["results"].append(result)
                        job["completed_sectors"] += 1
                except PipelineCancelled:
                    sid = futures[future]
                    name = sectors_to_run[sid]["name"]
                    _log("⚠️", f"{name}: cancelled")
                    job["cancelled"] = True
                except Exception as e:
                    sid = futures[future]
                    name = sectors_to_run[sid]["name"]
                    _log("❌", f"{name}: {e}")
                    with _job_lock:
                        job["results"].append({
                            "sector_id": sid,
                            "sector_name": name,
                            "error": str(e),
                        })

        if not job.get("cancelled") and not job.get("error"):
            check_old_predictions()
    except Exception as e:
        if type(e).__name__ == 'LLMHealthCheckError':
            job["error"] = f"LLM unreachable: {e}"
        else:
            job["error"] = f"Pipeline error: {e}"
    finally:
        job["running"] = False
        job["finished_at"] = _time.time()


_PIPELINE_NODES = [
    ("fetch",     "📡 Fetch"),
    ("summarize", "📝 Summarize"),
    ("reflect",   "🤔 Reflect"),
    ("analyze",   "🧠 Analyze"),
    ("validate",  "✅ Validate"),
    ("score",     "📊 Score"),
    ("save",      "💾 Save"),
]


def _render_live_pipeline_graph(job: dict):
    """Render an HTML pipeline graph with the active node highlighted."""
    with _job_lock:
        active = job.get("active_node")
        completed = list(job.get("completed_nodes", []))

    nodes_html = ""
    for i, (node_id, label) in enumerate(_PIPELINE_NODES):
        if node_id == active:
            bg = "linear-gradient(135deg,#b8860b,#d4af37)"
            color = "#fff"
            border = "2px solid #8b6508"
            shadow = "0 0 12px rgba(184,134,11,0.5)"
            anim = "animation:pulse-node 1.5s ease-in-out infinite;"
        elif node_id in completed:
            bg = "#22c55e"
            color = "#fff"
            border = "2px solid #16a34a"
            shadow = "none"
            anim = ""
        else:
            bg = "var(--bar-track-bg)"
            color = "var(--on-surface-variant)"
            border = "1px solid var(--outline-variant)"
            shadow = "none"
            anim = ""

        nodes_html += (
            f'<div style="display:flex;flex-direction:column;align-items:center;'
            f'min-width:0;flex:1">'
            f'<div style="padding:0.45rem 0.6rem;border-radius:0.6rem;'
            f'background:{bg};color:{color};border:{border};box-shadow:{shadow};'
            f'font-size:0.72rem;font-weight:700;white-space:nowrap;{anim}'
            f'text-align:center">{label}</div>'
            f'</div>'
        )
        # Arrow between nodes
        if i < len(_PIPELINE_NODES) - 1:
            arrow_color = "#22c55e" if node_id in completed else "var(--on-surface-variant)"
            nodes_html += (
                f'<div style="display:flex;align-items:center;color:{arrow_color};'
                f'font-size:0.9rem;font-weight:700;margin:0 2px">→</div>'
            )

    html = (
        '<style>@keyframes pulse-node{'
        '0%,100%{transform:scale(1);opacity:1}'
        '50%{transform:scale(1.06);opacity:0.85}'
        '}</style>'
        '<div style="display:flex;align-items:center;justify-content:center;'
        'gap:0;padding:0.8rem 0.5rem;margin-bottom:0.75rem;'
        'background:var(--surface-card);border-radius:1rem;'
        'border:1px solid var(--outline-variant);overflow-x:auto">'
        f'{nodes_html}'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


@st.fragment(run_every=2)
def _render_analysis_progress():
    """Poll the background job and render progress / results.

    Decorated with @st.fragment(run_every=2) so only this section
    re-renders every 2 seconds — the rest of the page (and sidebar
    navigation) stays responsive while analysis runs.
    """
    job = st.session_state.get(_JOB_KEY)
    if job is None:
        return  # No job has been started

    if job["running"]:
        # ── Still running — show live log + cancel button ─────────
        elapsed = _time.time() - job["started_at"]
        total_s = job["total_sectors"] or 1
        done_s = job["completed_sectors"]
        pct = done_s / total_s

        # Progress bar
        st.progress(pct, text=f"Analyzing {done_s}/{total_s} sectors complete · {elapsed:.0f}s elapsed")

        # ── Live pipeline graph ───────────────────────────────────
        _render_live_pipeline_graph(job)

        with st.status(f"Running LangGraph pipeline … ({elapsed:.0f}s)", expanded=True):
            with _job_lock:
                log_snapshot = list(job["log"])
            # Show only last 15 lines to keep it readable, plus first 3
            if len(log_snapshot) > 18:
                for icon, text in log_snapshot[:3]:
                    st.write(f"{icon} {text}")
                st.caption(f"… {len(log_snapshot) - 18} earlier steps hidden …")
                for icon, text in log_snapshot[-15:]:
                    st.write(f"{icon} {text}")
            else:
                for icon, text in log_snapshot:
                    st.write(f"{icon} {text}")
            timeout_pct = min(elapsed / _MAX_ANALYSIS_SECONDS * 100, 100)
            if timeout_pct > 75:
                st.caption(f"⏰ Timeout at {_MAX_ANALYSIS_SECONDS // 60}min — {100 - timeout_pct:.0f}% remaining")

        if st.button("⛔ Cancel Analysis", key="cancel_analysis", type="secondary"):
            job["cancel"].set()
            st.toast("⏳ Cancellation requested — will stop after current sector finishes.")

        # Fragment auto-reruns every 2 seconds via @st.fragment(run_every=2)
    else:
        # ── Finished — show results and clear running state ───────
        elapsed = (job["finished_at"] or _time.time()) - job["started_at"]

        if job["error"]:
            st.error(f"❌ Analysis failed ({elapsed:.0f}s): {job['error']}")
            st.toast(f"❌ Analysis failed after {elapsed:.0f}s", icon="❌")
            # Offer retry
            if st.button("🔄  Retry Analysis", key="retry_analysis", type="primary"):
                del st.session_state[_JOB_KEY]
                st.rerun()
        elif job.get("cancelled"):
            n = len(job["results"])
            st.warning(f"⚠️ Analysis cancelled — {n} sector{'s' if n != 1 else ''} completed before cancellation ({elapsed:.0f}s)")
            st.toast(f"⚠️ Analysis cancelled ({n} sector{'s' if n != 1 else ''} done)", icon="⚠️")
        else:
            st.success(f"✅ Analysis complete — {len(job['results'])} reports in {elapsed:.0f}s")
            st.toast(f"✅ Analysis complete — {len(job['results'])} reports in {elapsed:.0f}s", icon="✅")

            # Bust cache so new data shows up
            _cached_reports_list.clear()
            _cached_prediction_stats.clear()
            _cached_report_count.clear()

            # Also bust sidebar ChromaDB cache and report detail cache
            st.session_state.pop("_chroma_status", None)
            try:
                from ui.page_reports import _load_full_report
                _load_full_report.clear()
            except Exception:
                pass

            from ui.components import pill_cls
            for res in job["results"]:
                if res.get("error"):
                    st.error(f"{res['sector_name']}: {res['error']}")
                    continue
                with st.container(border=True):
                    _result_card(res)

        # Clear the job so subsequent reruns don't re-render old results
        if st.button("Dismiss", key="dismiss_analysis"):
            del st.session_state[_JOB_KEY]
            st.rerun()


def _result_card(res: dict):
    """Compact card shown on dashboard after running analysis."""
    from ui.components import pill_cls, friendly_status

    conf = res.get("confidence")
    vs = res.get("validation_status", "")
    ds = res.get("data_sufficiency", "")
    ds_color = {"sufficient": "#22c55e", "marginal": "#f59e0b",
                "insufficient": "#ef4444"}.get(ds, "#64748b")

    c1, c2, c3, c4 = st.columns([2.5, 1, 1, 1])
    with c1:
        st.markdown(f"**{res['sector_name']}** · Report #{res.get('report_id', '?')}")
    with c2:
        st.markdown(f"**{conf}/10**" if conf else "—")
    with c3:
        friendly = friendly_status(vs)
        if friendly:
            st.markdown(f'<span class="pill {pill_cls(vs)}">{friendly}</span>',
                        unsafe_allow_html=True)
    with c4:
        st.markdown(f'<span style="color:{ds_color}">● {html.escape(ds.title()) if ds else ""}</span>',
                    unsafe_allow_html=True)

    ns = res.get("news_summary", "")
    if ns:
        st.caption(ns[:300])

    with st.expander("Full Analysis"):
        st.markdown(res.get("analysis", ""))
    with st.expander("Validation"):
        st.markdown(res.get("validation", ""))
