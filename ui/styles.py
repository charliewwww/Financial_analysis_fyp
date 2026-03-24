"""
CSS Styles — "The Intelligent Curator" design system.

Translates the designer's Tailwind/HTML vision into Streamlit-compatible CSS.
Uses tonal layering, glassmorphism, Manrope + Inter font stack, and
gradient-gold CTA surfaces. No 1px border grids — depth via surface shifts.
"""

GLOBAL_CSS = """
<style>
/* ── Google Fonts ─────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Inter:wght@400;500;600&display=swap');

/* ── Design Tokens ────────────────────────────────── */
:root {
    --primary: #b8860b;
    --primary-light: #d4af37;
    --primary-container: #fef3c7;
    --on-surface: #0f172a;
    --on-surface-variant: #64748b;
    --surface: #f8fafc;
    --surface-card: rgba(255, 255, 255, 0.8);
    --outline-variant: #e2e8f0;
    --error: #ef4444;
    --sector-ai: #5C9CE6;
    --sector-space: #9575CD;
    --sector-optical: #b8860b;
    --shadow-premium: 0 20px 50px rgba(0, 0, 0, 0.05);
    --shadow-glass: 0 8px 32px 0 rgba(31, 38, 135, 0.04);
    --radius-card: 1.5rem;
}

/* ── Page ─────────────────────────────────────────── */
.stApp {
    background-color: var(--surface) !important;
    font-family: 'Inter', sans-serif !important;
}
.block-container {
    padding-top: 2rem;
    max-width: 1520px;
    font-family: 'Inter', sans-serif;
}

/* ── Headings — Manrope ───────────────────────────── */
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {
    font-family: 'Manrope', sans-serif !important;
    font-weight: 800 !important;
    color: var(--on-surface) !important;
    letter-spacing: -0.02em;
}

/* ── Sidebar — clean white, no hard border ────────── */
section[data-testid="stSidebar"] {
    background: #FFFFFF !important;
    border-right: none !important;
    box-shadow: 2px 0 20px rgba(0,0,0,0.03);
    font-family: 'Manrope', sans-serif;
}
section[data-testid="stSidebar"] [data-testid="stMarkdown"] {
    font-family: 'Manrope', sans-serif;
}
section[data-testid="stSidebar"] .stRadio > label {
    font-family: 'Manrope', sans-serif !important;
    font-weight: 600 !important;
}

/* ── Cards — glass effect, tonal layering ─────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--surface-card) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(255, 255, 255, 0.4) !important;
    border-radius: var(--radius-card) !important;
    box-shadow: var(--shadow-premium);
    transition: all 0.5s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
    box-shadow: 0 25px 60px rgba(0, 0, 0, 0.07);
}

/* ── Metrics — Manrope numerals ───────────────────── */
[data-testid="stMetric"] {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}
[data-testid="stMetricValue"] > div {
    font-weight: 800; color: var(--on-surface);
    font-family: 'Manrope', sans-serif !important;
    white-space: normal !important; word-break: break-word;
    overflow: visible !important; text-overflow: unset !important;
    font-size: clamp(1.2rem, 2.5vw, 2rem) !important;
    letter-spacing: -0.03em;
}
[data-testid="stMetricLabel"] > div {
    font-size: 0.625rem; color: var(--on-surface-variant);
    text-transform: uppercase; letter-spacing: 0.1em;
    font-weight: 800; white-space: nowrap;
    font-family: 'Inter', sans-serif;
}

/* ── Buttons — gradient gold CTA ──────────────────── */
button[data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 1rem !important;
    font-weight: 700 !important;
    font-family: 'Manrope', sans-serif !important;
    letter-spacing: 0.02em;
    box-shadow: 0 10px 30px rgba(184, 134, 11, 0.2) !important;
    transition: all 0.3s ease !important;
}
button[data-testid="stBaseButton-primary"]:hover {
    box-shadow: 0 15px 40px rgba(184, 134, 11, 0.3) !important;
    transform: translateY(-1px);
}
button[data-testid="stBaseButton-secondary"],
button[data-testid="stBaseButton-minimal"] {
    border: 1px solid var(--outline-variant) !important;
    border-radius: 1rem !important;
    background: #FFFFFF !important;
    color: var(--on-surface) !important;
    font-family: 'Inter', sans-serif !important;
    white-space: nowrap !important; min-width: fit-content !important;
    padding: 0.4rem 1rem !important;
    transition: all 0.3s ease !important;
}
button[data-testid="stBaseButton-secondary"]:hover,
button[data-testid="stBaseButton-minimal"]:hover {
    background: var(--surface) !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.04) !important;
}

/* ── Expanders ────────────────────────────────────── */
[data-testid="stExpander"] {
    background: var(--surface-card);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.4) !important;
    border-radius: 1rem; overflow: hidden;
}

/* ── Selectbox / Multiselect ──────────────────────── */
[data-testid="stSelectbox"] > div > div { border-radius: 1rem !important; }
[data-testid="stMultiSelect"] > div > div { border-radius: 1rem !important; }

/* ── Misc ─────────────────────────────────────────── */
hr { border-color: var(--outline-variant) !important; }

/* ── Status Pills — lowercase, full-round, pastel ── */
.pill {
    display: inline-block; padding: 4px 14px;
    border-radius: 9999px; font-size: 0.68rem;
    font-weight: 800; text-transform: lowercase; letter-spacing: 0.02em;
}
.pill-green  { background: #dcfce7; color: #166534; }
.pill-amber  { background: var(--primary-container); color: #78350f; }
.pill-red    { background: #fee2e2; color: #991b1b; }
.pill-gray   { background: #f1f5f9; color: var(--on-surface-variant); }

/* ── Progress Bars — thin, gradient, full-round ───── */
.bar-track {
    height: 6px; border-radius: 9999px;
    background: #f1f5f9; overflow: hidden; margin: 6px 0;
}
.bar-fill { height: 100%; border-radius: 9999px; }
.bar-amber  { background: linear-gradient(90deg, var(--primary-light), var(--primary)); }
.bar-green  { background: linear-gradient(90deg, #4ade80, #22c55e); }
.bar-blue   { background: linear-gradient(90deg, #60a5fa, #5C9CE6); }
.bar-ai     { background: linear-gradient(90deg, #60a5fa, #5C9CE6); }
.bar-space  { background: linear-gradient(90deg, #a78bfa, #9575CD); }
.bar-optical{ background: linear-gradient(90deg, var(--primary-light), var(--primary)); }

/* ── Glass Card (for HTML injection) ──────────────── */
.glass-card {
    background: rgba(255, 255, 255, 0.8);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.4);
    border-radius: 1.5rem;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.05);
    padding: 2rem;
}

/* ── KPI Card ─────────────────────────────────────── */
.kpi-card {
    background: rgba(255, 255, 255, 0.8);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.4);
    border-radius: 1.5rem; padding: 1.75rem 2rem;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.05);
    transition: all 0.5s ease;
    border-bottom: 4px solid transparent;
}
.kpi-card:hover {
    box-shadow: 0 25px 60px rgba(0, 0, 0, 0.08);
    border-bottom-color: rgba(184, 134, 11, 0.3);
}
.kpi-label {
    font-size: 0.625rem; font-weight: 800;
    color: var(--on-surface-variant);
    text-transform: uppercase; letter-spacing: 0.1em;
    margin-bottom: 0.5rem; font-family: 'Inter', sans-serif;
}
.kpi-value {
    font-size: 2.25rem; font-weight: 800;
    color: var(--on-surface); font-family: 'Manrope', sans-serif;
    letter-spacing: -0.03em; line-height: 1.1;
}
.kpi-sub {
    font-size: 0.75rem; font-weight: 700; color: #cbd5e1;
}

/* ── Intelligence Feed Row ────────────────────────── */
.feed-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 1.25rem; border-radius: 1rem;
    transition: all 0.3s ease;
    border: 1px solid transparent; cursor: default;
}
.feed-row:hover {
    background: var(--surface); border-color: #f1f5f9;
}

/* ── Sector Dot Container ─────────────────────────── */
.sector-dot-box {
    width: 3rem; height: 3rem; border-radius: 0.75rem;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.sector-dot-box.ai      { background: #eff6ff; }
.sector-dot-box.space    { background: #faf5ff; }
.sector-dot-box.optical  { background: #fffbeb; }
.sector-dot {
    width: 0.75rem; height: 0.75rem; border-radius: 9999px;
}
.sector-dot.ai      { background: #5C9CE6; box-shadow: 0 0 10px rgba(92,156,230,0.5); }
.sector-dot.space   { background: #9575CD; box-shadow: 0 0 10px rgba(149,117,205,0.5); }
.sector-dot.optical { background: #b8860b; box-shadow: 0 0 10px rgba(184,134,11,0.5); }

/* ── Chain / Supply Chain ─────────────────────────── */
.chain-row {
    display: flex; align-items: center; padding: 7px 0;
    border-bottom: 1px solid #f1f5f9; gap: 10px; font-size: 0.85rem;
}
.chain-ticker { font-weight: 700; min-width: 60px; }
.chain-role   { color: var(--on-surface-variant); min-width: 160px; font-size: 0.8rem; }
.chain-target {
    display: inline-block; background: #f1f5f9; padding: 2px 10px;
    border-radius: 6px; font-size: 0.78rem; margin: 2px;
}

/* ── Node execution trace ─────────────────────────── */
.node-row {
    display: flex; align-items: center; padding: 9px 0;
    border-bottom: 1px solid #f1f5f9; gap: 10px;
}
.node-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.dot-ok  { background: #22c55e; }
.dot-err { background: var(--error); }

/* ── Report list row ──────────────────────────────── */
.report-row {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 6px; cursor: default;
}

/* ── Source citation links ─────────────────────────── */
.source-link {
    color: var(--primary) !important; text-decoration: none !important;
    font-weight: 600;
}
.source-link:hover {
    color: var(--primary-light) !important; text-decoration: underline !important;
}

/* ── CTA Section ──────────────────────────────────── */
.cta-section {
    background: rgba(255,255,255,0.4);
    backdrop-filter: blur(12px); border-radius: 2rem;
    padding: 2.5rem; border: 1px solid rgba(255,255,255,0.6);
    box-shadow: 0 20px 50px rgba(0,0,0,0.05);
}

/* ── Section Headers ──────────────────────────────── */
.section-title {
    font-family: 'Manrope', sans-serif; font-weight: 800;
    font-size: 1.25rem; color: var(--on-surface);
    letter-spacing: -0.02em;
}
.section-title-lg {
    font-family: 'Manrope', sans-serif; font-weight: 800;
    font-size: 1.75rem; color: var(--on-surface);
    letter-spacing: -0.03em;
}

/* ── Micro-copy label ─────────────────────────────── */
.micro-label {
    font-size: 0.5625rem; font-weight: 800;
    color: var(--on-surface-variant); text-transform: uppercase;
    letter-spacing: 0.15em;
}

/* ── System Health Panel ──────────────────────────── */
.health-panel {
    background: rgba(248,250,252,0.5); border-radius: 1rem;
    padding: 1.25rem;
}
.health-title {
    font-size: 0.5625rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.15em;
    color: var(--on-surface-variant); margin-bottom: 0.75rem;
}
.health-row {
    display: flex; align-items: center; justify-content: space-between;
    font-size: 0.75rem; padding: 0.35rem 0;
}
.health-label { color: var(--on-surface-variant); font-weight: 500; }
.health-value { font-weight: 700; color: var(--primary); }
.health-dot {
    width: 6px; height: 6px; border-radius: 9999px;
    display: inline-block; margin-right: 6px;
}
.health-dot.ok  { background: var(--primary); }
.health-dot.err { background: var(--error); }

/* ── Footer ───────────────────────────────────────── */
.sc-footer {
    display: flex; flex-wrap: wrap; justify-content: space-between;
    align-items: center; padding: 1.5rem 0;
    border-top: 1px solid #f1f5f9; margin-top: 2rem;
}
.sc-footer span {
    font-size: 0.5625rem; font-weight: 800;
    color: var(--on-surface-variant); text-transform: uppercase;
    letter-spacing: 0.15em;
}

/* ── Mobile responsive ─────────────────────────────── */
@media (max-width: 768px) {
    .block-container { padding-top: 1.2rem; padding-left: 0.8rem; padding-right: 0.8rem; }
    [data-testid="stMetricValue"] > div { font-size: 1.25rem !important; }
    .pill { padding: 2px 8px; font-size: 0.65rem; }
    .kpi-card { padding: 1.25rem; }
    .kpi-value { font-size: 1.75rem; }
    .glass-card { padding: 1.25rem; }
    .feed-row { flex-wrap: wrap; padding: 0.75rem; }
    .chain-row { flex-wrap: wrap; }
    button[data-testid="stBaseButton-primary"],
    button[data-testid="stBaseButton-secondary"] {
        min-height: 44px !important;
        font-size: 0.85rem !important;
    }
    [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
    [data-testid="stColumn"] { min-width: 100% !important; flex: 1 1 100% !important; }
}
</style>"""
