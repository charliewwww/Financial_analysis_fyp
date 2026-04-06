"""
Pipeline page — LangGraph topology + Langfuse tracing dashboard.

Shows the analysis pipeline as an interactive Mermaid diagram and
provides quick links/status for Langfuse observability.
"""

import streamlit as st
from config.settings import (
    LANGFUSE_ENABLED, LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY,
    REASONING_MODEL, LLM_PROVIDER,
)


# ═══════════════════════════════════════════════════════════════════
# MERMAID DIAGRAM — mirrors _build_sector_graph() topology
# ═══════════════════════════════════════════════════════════════════

_MERMAID_GRAPH = """\
graph TD
    START([▶ START]) --> fetch["📡 Fetch\\nNews · Prices · SEC · Macro"]
    fetch --> summarize["📝 Summarize\\nCompress articles"]
    summarize --> reflect["🤔 Reflect\\nData sufficiency check"]
    reflect -->|Insufficient| fetch
    reflect -->|Sufficient| analyze["🧠 Analyze\\nDeep RAG + LLM analysis"]
    analyze --> validate["✅ Validate\\nNumerical + reasoning checks"]
    validate -->|Failed| analyze
    validate -->|Passed| score["📊 Score\\nConfidence 1-10"]
    score --> save["💾 Save\\nDB + ChromaDB"]
    save --> END([■ END])

    classDef default fill:#f8fafc,stroke:#64748b,stroke-width:1px,color:#0f172a,font-family:Inter
    classDef startEnd fill:#b8860b,stroke:#8b6508,color:#fff,font-weight:700
    classDef loopBack stroke:#ef4444,stroke-width:2px,stroke-dasharray:5 5

    class START,END startEnd
"""


# ═══════════════════════════════════════════════════════════════════
# NODE DETAILS — what each graph node does
# ═══════════════════════════════════════════════════════════════════

_NODE_INFO = [
    ("📡 Fetch", "Pulls live data from 4 sources: RSS news, Yahoo Finance prices, SEC EDGAR filings, and FRED macroeconomic indicators."),
    ("📝 Summarize", "LLM compresses raw articles into concise bullet summaries for the analysis context window."),
    ("🤔 Reflect", "LLM evaluates whether collected data is sufficient. If not, loops back to Fetch (max 1 retry)."),
    ("🧠 Analyze", "Core analysis node — assembles a RAG prompt with all data + ChromaDB context, then runs deep LLM analysis with directional predictions."),
    ("✅ Validate", "Checks numerical accuracy against real market data and validates reasoning quality. If flaws found, loops back to Analyze (max 1 retry)."),
    ("📊 Score", "LLM assigns a confidence score (1-10) based on data quality, reasoning depth, and prediction conviction."),
    ("💾 Save", "Persists the report + predictions to SQLite and indexes the analysis in ChromaDB for future RAG retrieval."),
]


# ═══════════════════════════════════════════════════════════════════
# RECENT TRACES — from node_executions in the latest reports
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def _get_recent_traces():
    """Load timing data from the most recent reports."""
    import json
    from database.reports_db import get_reports_list
    traces = []
    reports = get_reports_list(limit=6)
    for r in reports:
        raw = r.get("raw_state") or r.get("analysis", "")
        # Try to extract node_executions from raw_state JSON
        if isinstance(raw, str):
            try:
                state_data = json.loads(raw)
                execs = state_data.get("node_executions", [])
            except (json.JSONDecodeError, TypeError):
                execs = []
        elif isinstance(raw, dict):
            execs = raw.get("node_executions", [])
        else:
            execs = []

        traces.append({
            "sector": r.get("sector_name", "Unknown"),
            "created_at": r.get("created_at", ""),
            "report_id": r.get("id"),
            "node_executions": execs,
        })
    return traces


# ═══════════════════════════════════════════════════════════════════
# RENDER
# ═══════════════════════════════════════════════════════════════════

def render():
    st.markdown(
        '<h1 style="font-family:Manrope,sans-serif;font-size:1.75rem;'
        'font-weight:800;letter-spacing:-0.03em;margin-bottom:0.5rem">'
        '⚙️ Pipeline</h1>',
        unsafe_allow_html=True,
    )
    st.caption("LangGraph topology · Node details · Langfuse tracing")

    # ── Two-column layout: graph + info ───────────────────────────
    col_graph, col_info = st.columns([3, 2], gap="large")

    with col_graph:
        st.subheader("Analysis Pipeline")
        # Render Mermaid via mermaid.js CDN embedded in HTML
        import html as _html
        _escaped = _html.escape(_MERMAID_GRAPH)
        st.html(
            f'<div class="mermaid" style="text-align:center">{_escaped}</div>'
            '<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>'
            '<script>mermaid.initialize({startOnLoad:true, theme:"neutral", '
            'flowchart:{curve:"basis",nodeSpacing:30,rankSpacing:40}});</script>'
        )

    with col_info:
        st.subheader("Node Reference")
        for icon_name, desc in _NODE_INFO:
            st.markdown(
                f'<div style="margin-bottom:0.75rem;padding:0.6rem 0.8rem;'
                f'background:rgba(255,255,255,0.6);border-radius:0.75rem;'
                f'border:1px solid #e2e8f0">'
                f'<strong style="font-size:0.85rem">{icon_name}</strong>'
                f'<p style="font-size:0.78rem;color:#64748b;margin:0.25rem 0 0">'
                f'{desc}</p></div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # ── System Info ───────────────────────────────────────────────
    st.subheader("System Configuration")
    provider_label = "OpenRouter" if LLM_PROVIDER == "openrouter" else "Ollama (local)"
    rows = [
        ("LLM Provider", provider_label),
        ("Model", REASONING_MODEL),
        ("Graph Nodes", "7 (fetch → save)"),
        ("Conditional Loops", "2 (reflect→fetch, validate→analyze)"),
    ]
    html = '<div style="font-size:0.82rem;max-width:480px">'
    for label, val in rows:
        html += (
            f'<div style="display:flex;justify-content:space-between;'
            f'padding:0.35rem 0;border-bottom:1px solid #f1f5f9">'
            f'<span style="color:#64748b">{label}</span>'
            f'<span style="font-weight:600;color:#0f172a">{val}</span></div>'
        )
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

    st.divider()

    # ── Recent Pipeline Runs ──────────────────────────────────────
    st.subheader("Recent Pipeline Runs")
    traces = _get_recent_traces()

    if not traces:
        st.info("No analysis runs yet. Run an analysis from the Dashboard to see pipeline traces here.")
        return

    for trace in traces:
        execs = trace["node_executions"]
        sector = trace["sector"]
        created = trace["created_at"]

        if not execs:
            st.markdown(
                f'<div style="padding:0.5rem 0.8rem;margin-bottom:0.5rem;'
                f'background:#f8fafc;border-radius:0.5rem;font-size:0.8rem;'
                f'color:#94a3b8">{sector} · {created} — no execution data</div>',
                unsafe_allow_html=True,
            )
            continue

        with st.expander(f"{sector}  ·  {created}", expanded=False):
            # Build a timeline table
            html = (
                '<table style="width:100%;font-size:0.78rem;border-collapse:collapse">'
                '<tr style="border-bottom:2px solid #e2e8f0;color:#64748b">'
                '<th style="text-align:left;padding:4px 8px">Node</th>'
                '<th style="text-align:right;padding:4px 8px">Duration</th>'
                '<th style="text-align:right;padding:4px 8px">Status</th>'
                '<th style="text-align:right;padding:4px 8px">Tokens</th>'
                '</tr>'
            )
            total_dur = 0.0
            total_tokens = 0
            for ex in execs:
                if isinstance(ex, dict):
                    name = ex.get("node_name", "?")
                    dur = ex.get("duration_seconds", 0)
                    status = ex.get("status", "?")
                    prompt_tok = ex.get("llm_prompt_tokens", 0)
                    comp_tok = ex.get("llm_completion_tokens", 0)
                else:
                    name = getattr(ex, "node_name", "?")
                    dur = getattr(ex, "duration_seconds", 0)
                    status = getattr(ex, "status", "?")
                    prompt_tok = getattr(ex, "llm_prompt_tokens", 0)
                    comp_tok = getattr(ex, "llm_completion_tokens", 0)

                total_dur += dur
                tok = prompt_tok + comp_tok
                total_tokens += tok

                status_color = "#22c55e" if status == "completed" else "#ef4444"
                html += (
                    f'<tr style="border-bottom:1px solid #f1f5f9">'
                    f'<td style="padding:4px 8px;font-weight:600">{name}</td>'
                    f'<td style="text-align:right;padding:4px 8px">{dur:.1f}s</td>'
                    f'<td style="text-align:right;padding:4px 8px;color:{status_color}">{status}</td>'
                    f'<td style="text-align:right;padding:4px 8px">{tok:,}</td>'
                    f'</tr>'
                )

            html += (
                f'<tr style="border-top:2px solid #e2e8f0;font-weight:700">'
                f'<td style="padding:4px 8px">TOTAL</td>'
                f'<td style="text-align:right;padding:4px 8px">{total_dur:.1f}s</td>'
                f'<td style="text-align:right;padding:4px 8px"></td>'
                f'<td style="text-align:right;padding:4px 8px">{total_tokens:,}</td>'
                f'</tr></table>'
            )
            st.markdown(html, unsafe_allow_html=True)

    # ── Admin: Langfuse (hidden by default) ───────────────────────
    st.write("")
    st.write("")
    with st.expander("🔐 Admin — Langfuse Observability", expanded=False):
        if LANGFUSE_ENABLED:
            st.success("Langfuse is **active** — all LLM calls are being traced.", icon="✅")
            dashboard_url = LANGFUSE_HOST.rstrip("/")
            st.markdown(
                f'<a href="{dashboard_url}" target="_blank" '
                f'style="display:inline-block;margin-top:0.5rem;padding:0.5rem 1.2rem;'
                f'background:linear-gradient(135deg,#b8860b,#d4af37);color:#fff;'
                f'border-radius:0.5rem;text-decoration:none;font-weight:700;'
                f'font-size:0.85rem">Open Langfuse Dashboard →</a>',
                unsafe_allow_html=True,
            )
            st.caption("View traces, latency, token usage, and cost per analysis run.")
        else:
            st.warning(
                "Langfuse is **not configured**. Add `LANGFUSE_PUBLIC_KEY` and "
                "`LANGFUSE_SECRET_KEY` to your `.env` file to enable LLM tracing.",
                icon="⚠️",
            )
            st.caption("Sign up free at [cloud.langfuse.com](https://cloud.langfuse.com)")
