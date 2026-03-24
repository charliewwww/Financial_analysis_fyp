"""
Supply Chain Alpha — Dashboard UI.

Thin router — delegates to page modules in ui/ for all rendering.
"""

import streamlit as st

st.set_page_config(
    page_title="Supply Chain Alpha",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inject global CSS ─────────────────────────────────────────────
from ui.styles import GLOBAL_CSS
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ── Imports (after CSS so first paint is fast) ────────────────────
from config.logging_config import setup_logging
setup_logging("INFO")

from config.sectors import SECTORS
from ui import page_dashboard, page_reports, page_predictions, page_supply_chain


# ═══════════════════════════════════════════════════════════════════
# NAVIGATION
# ═══════════════════════════════════════════════════════════════════
PAGES = ["Dashboard", "Supply Chain", "Reports", "Predictions"]


def _init_session():
    if "page" not in st.session_state:
        st.session_state.page = "Dashboard"
    if "selected_report_id" not in st.session_state:
        st.session_state.selected_report_id = None


# ═══════════════════════════════════════════════════════════════════
# SIDEBAR STATUS
# ═══════════════════════════════════════════════════════════════════

def _render_sidebar_status():
    """Show system component health indicators in the designer's panel style."""
    from config.settings import REASONING_MODEL, LLM_PROVIDER

    items = []

    provider_label = "OpenRouter" if LLM_PROVIDER == "openrouter" else "Ollama (local)"
    items.append(("LLM Status", f"{REASONING_MODEL}", True))

    # LangGraph — check once via session state
    if "_langgraph_ok" not in st.session_state:
        try:
            from langgraph.graph import StateGraph  # noqa: F401
            st.session_state._langgraph_ok = True
        except ImportError:
            st.session_state._langgraph_ok = False
    items.append(("LangGraph",
                  "Active" if st.session_state._langgraph_ok else "Not installed",
                  st.session_state._langgraph_ok))

    # ChromaDB — lazy import, cached in session state
    if "_chroma_status" not in st.session_state:
        try:
            from vectordb.chroma_store import is_available, get_store_stats
            if is_available():
                stats = get_store_stats()
                total = stats.get("total_documents", 0)
                st.session_state._chroma_status = (f"{total} docs", True)
            else:
                st.session_state._chroma_status = ("Not installed", False)
        except Exception:
            st.session_state._chroma_status = ("Error", False)
    chroma_label, chroma_ok = st.session_state._chroma_status
    items.append(("ChromaDB", chroma_label, chroma_ok))

    from config.settings import FRED_API_KEY
    if FRED_API_KEY:
        items.append(("FRED Macro", "Key set", True))
    else:
        items.append(("FRED Macro", "No API key", False))

    from config.settings import SEC_EDGAR_EMAIL
    if SEC_EDGAR_EMAIL:
        items.append(("SEC EDGAR", "Configured", True))
    else:
        items.append(("SEC EDGAR", "No email set", False))

    # Render in the designer's health-panel style
    html = '<div class="health-panel">'
    html += '<div class="health-title">System Health</div>'
    for label, value, ok in items:
        dot = "ok" if ok else "err"
        val_color = "#b8860b" if ok else "#ef4444"
        html += (
            f'<div class="health-row">'
            f'<span class="health-label">{label}</span>'
            f'<span style="display:flex;align-items:center;gap:6px;'
            f'font-weight:700;font-size:0.75rem;color:{val_color}">'
            f'<span class="health-dot {dot}"></span>{value}</span>'
            f'</div>'
        )
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    _init_session()

    with st.sidebar:
        # ── Brand header (designer style) ───────────────
        st.markdown(
            '<div style="margin-bottom:2rem">'
            '<h1 style="font-family:Manrope,sans-serif;font-size:1.15rem;'
            'font-weight:800;letter-spacing:-0.02em;line-height:1.3;margin:0">'
            '<span style="color:#b8860b">SUPPLY CHAIN</span><br>'
            '<span style="color:#0f172a">ALPHA</span></h1>'
            '<p style="font-size:0.5625rem;color:#94a3b8;font-weight:800;'
            'letter-spacing:0.2em;text-transform:uppercase;margin-top:0.5rem">'
            'Intelligent Curator</p></div>',
            unsafe_allow_html=True)

        idx = PAGES.index(st.session_state.page) if st.session_state.page in PAGES else 0
        page = st.radio("Navigate", PAGES, index=idx, label_visibility="collapsed")

        if page != st.session_state.page:
            st.session_state.page = page
            if page != "Reports":
                st.session_state.selected_report_id = None
            st.rerun()

        st.write("")
        _render_sidebar_status()

        st.write("")
        st.markdown(
            '<div style="display:flex;align-items:center;gap:8px;'
            'margin-top:auto">'
            '<span class="micro-label">'
            f'{len(SECTORS)} Sectors · '
            f'{sum(len(s["tickers"]) for s in SECTORS.values())} Tickers'
            '</span></div>',
            unsafe_allow_html=True)

    # Route to page module
    {"Dashboard": page_dashboard.render,
     "Supply Chain": page_supply_chain.render,
     "Reports": page_reports.render,
     "Predictions": page_predictions.render}[st.session_state.page]()


if __name__ == "__main__":
    main()
