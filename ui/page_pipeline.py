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
# PIPELINE DIAGRAM — pure HTML/CSS (no external JS)
# ═══════════════════════════════════════════════════════════════════

_PIPELINE_STEPS = [
    ("▶",  "START",    None),
    ("📡", "Fetch",    "News · Prices · SEC · Macro"),
    ("📝", "Summarize","Compress articles"),
    ("🤔", "Reflect",  "Data sufficiency check"),
    ("🧠", "Analyze",  "Deep RAG + LLM analysis"),
    ("✅", "Validate", "Numerical + reasoning checks"),
    ("📊", "Score",    "Confidence 1–10"),
    ("💾", "Save",     "DB + ChromaDB"),
    ("■",  "END",      None),
]

_LOOP_CONNECTIONS = [
    (3, 1, "Insufficient"),   # Reflect → Fetch
    (5, 4, "Failed"),         # Validate → Analyze
]


def _render_pipeline_diagram():
    """Render the LangGraph pipeline as a CSS-Grid flowchart.

    Uses a 2-column grid: column 1 holds nodes/arrows, column 2 holds
    loop-back annotations.  Loop annotations use `grid-row` spans so
    they always line up with the actual rendered node heights — no
    pixel guessing required.

    Grid rows (1-indexed):
        Node i  → row  2*i + 1
        Arrow i → row  2*i + 2   (arrow *after* node i)
    Total rows = 2*N - 1  (N = len(_PIPELINE_STEPS))
    """
    total_rows = 2 * len(_PIPELINE_STEPS) - 1

    # ── column-1 cells: nodes + arrows ────────────────────────────
    cells_html = ""
    for i, (icon, name, desc) in enumerate(_PIPELINE_STEPS):
        row = 2 * i + 1  # 1-indexed grid row for this node
        is_terminal = name in ("START", "END")
        bg = ("linear-gradient(135deg,#b8860b,#d4af37)" if is_terminal
              else "var(--surface-elevated)")
        color = "#fff" if is_terminal else "var(--on-surface)"
        border = ("2px solid #8b6508" if is_terminal
                  else "1.5px solid var(--outline-variant)")
        radius = "9999px" if is_terminal else "0.85rem"
        shadow = ("0 4px 15px rgba(184,134,11,0.3)" if is_terminal
                  else "0 2px 8px rgba(0,0,0,0.04)")
        pad = "0.6rem 1.8rem" if is_terminal else "0.8rem 1.4rem"

        desc_html = ""
        if desc:
            sub_color = ("rgba(255,255,255,0.7)" if is_terminal
                         else "var(--on-surface-variant)")
            desc_html = (f'<div style="font-size:0.68rem;color:{sub_color};'
                         f'margin-top:2px;line-height:1.3">{desc}</div>')

        cells_html += (
            f'<div style="grid-column:1;grid-row:{row};'
            f'display:flex;flex-direction:column;align-items:center">'
            f'<div style="background:{bg};color:{color};border:{border};'
            f'border-radius:{radius};padding:{pad};text-align:center;'
            f'box-shadow:{shadow};min-width:140px;'
            f'font-family:Manrope,sans-serif">'
            f'<div style="font-weight:700;font-size:0.85rem">'
            f'{icon} {name}</div>'
            f'{desc_html}'
            f'</div></div>'
        )

        # Arrow between nodes (not after last)
        if i < len(_PIPELINE_STEPS) - 1:
            arrow_row = row + 1
            cells_html += (
                f'<div style="grid-column:1;grid-row:{arrow_row};'
                f'display:flex;flex-direction:column;align-items:center;'
                f'padding:0.15rem 0">'
                f'<div style="width:2px;height:16px;'
                f'background:var(--on-surface-variant);opacity:0.5"></div>'
                f'<div style="color:var(--on-surface-variant);font-size:0.65rem;'
                f'font-weight:700;opacity:0.6">\u25bc</div>'
                f'</div>'
            )

    # ── column-2 cells: loop-back annotations ─────────────────────
    # Place each annotation in the SAME grid-row as its source node.
    # No spanning — avoids all stretch/alignment issues.
    for src_idx, tgt_idx, label in _LOOP_CONNECTIONS:
        lc = "#ef4444"
        src_row = 2 * src_idx + 1
        tgt_name = _PIPELINE_STEPS[tgt_idx][1]
        cells_html += (
            f'<div style="grid-column:2;grid-row:{src_row};'
            f'display:flex;align-items:center;padding-left:14px;'
            f'font-family:Inter,sans-serif;font-size:0.65rem;'
            f'color:{lc};font-weight:700;white-space:nowrap">'
            # Horizontal dashed connector
            f'<div style="width:20px;border-top:2px dashed {lc}"></div>'
            # Badge + target
            f'<div style="display:flex;flex-direction:column;align-items:center;'
            f'margin-left:6px">'
            f'<div style="border:2px dashed {lc};border-radius:0.5rem;'
            f'padding:3px 10px">{label}</div>'
            f'<div style="font-size:0.58rem;margin-top:3px;opacity:0.85">'
            f'\u21bb back to {tgt_name}</div>'
            f'</div>'
            f'</div>'
        )

    # ── assemble grid ─────────────────────────────────────────────
    st.markdown(
        f'<div style="display:flex;justify-content:center;padding:1rem 0">'
        f'<div style="display:grid;'
        f'grid-template-columns:auto auto;'
        f'grid-template-rows:repeat({total_rows}, auto);'
        f'column-gap:0;row-gap:0;'
        f'justify-items:center;align-items:center">'
        f'{cells_html}'
        f'</div></div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════
# RENDER
# ═══════════════════════════════════════════════════════════════════

def render():
    st.markdown(
        '<h1 style="font-family:Manrope,sans-serif;font-size:1.75rem;'
        'font-weight:800;letter-spacing:-0.03em;margin-bottom:0.5rem">'
        '⚙️ System</h1>',
        unsafe_allow_html=True,
    )
    st.caption("Analysis pipeline · Node details · System configuration")

    # ── Two-column layout: graph + info ───────────────────────────
    col_graph, col_info = st.columns([3, 2], gap="large")

    with col_graph:
        st.subheader("Analysis Pipeline")
        # Pure HTML/CSS pipeline diagram (no external JS dependency)
        _render_pipeline_diagram()

    with col_info:
        st.subheader("Node Reference")
        for icon_name, desc in _NODE_INFO:
            st.markdown(
                f'<div style="margin-bottom:1rem;padding:0.85rem 1rem;'
                f'background:var(--surface-card);border-radius:0.75rem;'
                f'border:1px solid var(--outline-variant);overflow:hidden">'
                f'<div style="font-size:0.85rem;font-weight:700;'
                f'font-family:Manrope,sans-serif;color:var(--on-surface);'
                f'margin-bottom:0.35rem">{icon_name}</div>'
                f'<div style="font-size:0.78rem;color:var(--on-surface-variant);'
                f'line-height:1.5;margin:0">{desc}</div></div>',
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
            f'padding:0.35rem 0;border-bottom:1px solid var(--bar-track-bg)">'
            f'<span style="color:var(--on-surface-variant)">{label}</span>'
            f'<span style="font-weight:600;color:var(--on-surface)">{val}</span></div>'
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
                f'background:var(--surface);border-radius:0.5rem;font-size:0.8rem;'
                f'color:var(--on-surface-variant)">{sector} · {created} — no execution data</div>',
                unsafe_allow_html=True,
            )
            continue

        with st.expander(f"{sector}  ·  {created}", expanded=False):
            # Build a timeline table
            html = (
                '<table style="width:100%;font-size:0.78rem;border-collapse:collapse">'
                '<tr style="border-bottom:2px solid var(--outline-variant);color:var(--on-surface-variant)">'
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
                    f'<tr style="border-bottom:1px solid var(--bar-track-bg)">'
                    f'<td style="padding:4px 8px;font-weight:600">{name}</td>'
                    f'<td style="text-align:right;padding:4px 8px">{dur:.1f}s</td>'
                    f'<td style="text-align:right;padding:4px 8px;color:{status_color}">{status}</td>'
                    f'<td style="text-align:right;padding:4px 8px">{tok:,}</td>'
                    f'</tr>'
                )

            html += (
                f'<tr style="border-top:2px solid var(--outline-variant);font-weight:700">'
                f'<td style="padding:4px 8px">TOTAL</td>'
                f'<td style="text-align:right;padding:4px 8px">{total_dur:.1f}s</td>'
                f'<td style="text-align:right;padding:4px 8px"></td>'
                f'<td style="text-align:right;padding:4px 8px">{total_tokens:,}</td>'
                f'</tr></table>'
            )
            st.markdown(html, unsafe_allow_html=True)

    # ── Admin: LangGraph Official Visualisation ─────────────────────
    st.write("")
    st.write("")
    with st.expander("🔐 Admin — LangGraph Topology (official)", expanded=False):
        try:
            from workflows.weekly_analysis import _get_compiled_graph
            compiled = _get_compiled_graph()
            graph_obj = compiled.get_graph()

            # Try PNG first (uses mermaid.ink API), fall back to mermaid text
            try:
                png_bytes = graph_obj.draw_mermaid_png()
                st.image(png_bytes, caption="LangGraph compiled graph", use_container_width=False)
            except Exception:
                mermaid_src = graph_obj.draw_mermaid()
                st.code(mermaid_src, language="mermaid")
                st.caption("PNG rendering unavailable — raw Mermaid source shown above.")
        except Exception as e:
            st.error(f"Could not load graph: {e}")

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
