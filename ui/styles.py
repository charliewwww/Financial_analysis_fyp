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

/* ── Design Tokens (Light) ────────────────────────── */
:root {
    --primary: #b8860b;
    --primary-light: #d4af37;
    --primary-container: #fef3c7;
    --on-surface: #0f172a;
    --on-surface-variant: #64748b;
    --surface: #f8fafc;
    --surface-card: rgba(255, 255, 255, 0.8);
    --surface-elevated: #ffffff;
    --outline-variant: #e2e8f0;
    --error: #ef4444;
    --sector-ai: #5C9CE6;
    --sector-space: #9575CD;
    --sector-optical: #b8860b;
    --shadow-premium: 0 20px 50px rgba(0, 0, 0, 0.05);
    --shadow-glass: 0 8px 32px 0 rgba(31, 38, 135, 0.04);
    --radius-card: 1.5rem;
    --bar-track-bg: #f1f5f9;
    --sidebar-bg: #FFFFFF;
    --sidebar-shadow: 2px 0 20px rgba(0,0,0,0.03);
    --code-bg: #f1f5f9;
    --hover-bg: rgba(0,0,0,0.02);
}

/* ── Dark Mode Tokens ─────────────────────────────── */
[data-theme="dark"] {
    --primary: #d4af37;
    --primary-light: #e8c84a;
    --primary-container: #3d2e06;
    --on-surface: #e2e8f0;
    --on-surface-variant: #94a3b8;
    --surface: #0f172a;
    --surface-card: rgba(30, 41, 59, 0.8);
    --surface-elevated: #1e293b;
    --outline-variant: #334155;
    --error: #f87171;
    --shadow-premium: 0 20px 50px rgba(0, 0, 0, 0.3);
    --shadow-glass: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
    --bar-track-bg: #1e293b;
    --sidebar-bg: #1e293b;
    --sidebar-shadow: 2px 0 20px rgba(0,0,0,0.2);
    --code-bg: #1e293b;
    --hover-bg: rgba(255,255,255,0.04);
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

/* ── Sidebar — clean, no hard border ──────────────── */
section[data-testid="stSidebar"] {
    background: var(--sidebar-bg) !important;
    border-right: none !important;
    box-shadow: var(--sidebar-shadow);
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
    border: 1px solid var(--outline-variant) !important;
    border-radius: var(--radius-card) !important;
    box-shadow: var(--shadow-premium);
    transition: all 0.5s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
    box-shadow: var(--shadow-premium);
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
    background: var(--surface-elevated) !important;
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
    border: 1px solid var(--outline-variant) !important;
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
.pill-gray   { background: var(--bar-track-bg); color: var(--on-surface-variant); }

/* ── Progress Bars — thin, gradient, full-round ───── */
.bar-track {
    height: 6px; border-radius: 9999px;
    background: var(--bar-track-bg); overflow: hidden; margin: 6px 0;
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
    background: var(--surface-card);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--outline-variant);
    border-radius: 1.5rem;
    box-shadow: var(--shadow-premium);
    padding: 2rem;
}

/* ── KPI Card ─────────────────────────────────────── */
.kpi-card {
    background: var(--surface-card);
    backdrop-filter: blur(12px);
    border: 1px solid var(--outline-variant);
    border-radius: 1.5rem; padding: 1.75rem 2rem;
    box-shadow: var(--shadow-premium);
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
    font-size: 0.75rem; font-weight: 700; color: var(--on-surface-variant);
}

/* ── Intelligence Feed Row ────────────────────────── */
.feed-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 1.25rem; border-radius: 1rem;
    transition: all 0.3s ease;
    border: 1px solid transparent; cursor: default;
}
.feed-row:hover {
    background: var(--hover-bg); border-color: var(--outline-variant);
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
    border-bottom: 1px solid var(--outline-variant); gap: 10px; font-size: 0.85rem;
}
.chain-ticker { font-weight: 700; min-width: 60px; }
.chain-role   { color: var(--on-surface-variant); min-width: 160px; font-size: 0.8rem; }
.chain-target {
    display: inline-block; background: var(--bar-track-bg); padding: 2px 10px;
    border-radius: 6px; font-size: 0.78rem; margin: 2px;
    color: var(--on-surface);
}

/* ── Node execution trace ─────────────────────────── */
.node-row {
    display: flex; align-items: center; padding: 9px 0;
    border-bottom: 1px solid var(--outline-variant); gap: 10px;
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
    background: var(--surface-card);
    backdrop-filter: blur(12px); border-radius: 2rem;
    padding: 2.5rem; border: 1px solid var(--outline-variant);
    box-shadow: var(--shadow-premium);
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
    background: var(--hover-bg); border-radius: 1rem;
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
    border-top: 1px solid var(--outline-variant); margin-top: 2rem;
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
    .kpi-card { padding: 1rem 1.25rem; }
    .kpi-value { font-size: 1.5rem; }
    .kpi-label { font-size: 0.5rem; }
    .glass-card { padding: 1.25rem; }
    .feed-row { flex-wrap: wrap; padding: 0.75rem; }
    .chain-row { flex-wrap: wrap; }
    .cta-section { padding: 1.25rem; border-radius: 1.25rem; }
    .section-title-lg { font-size: 1.25rem; }
    button[data-testid="stBaseButton-primary"],
    button[data-testid="stBaseButton-secondary"] {
        min-height: 44px !important;
        font-size: 0.85rem !important;
    }
    /* Stack columns into 2-col grid on mobile */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        gap: 0.5rem !important;
    }
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        min-width: 45% !important;
        flex: 1 1 45% !important;
    }
}

/* ── Compact metric strip ────────────────────────────────────────── */
.metric-strip {
    display: flex; flex-wrap: wrap; gap: 10px; margin: 4px 0 14px;
}
.metric-chip {
    flex: 1 1 120px; text-align: center; padding: 10px 12px;
    border-radius: 12px; border: 1px solid var(--outline-variant);
    background: var(--surface-card); font-family: Manrope, sans-serif;
}
.metric-chip-label {
    font-size: 0.55rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.08em; color: var(--on-surface-variant); margin-bottom: 2px;
}
.metric-chip-value {
    font-size: 1.2rem; font-weight: 800; color: var(--on-surface);
}
.metric-chip-sub { font-size: 0.68rem; color: var(--on-surface-variant); }

/* ── Signal cards ───────────────────────────────────────────────── */
.signal-grid { display: flex; flex-wrap: wrap; gap: 12px; margin: 8px 0 16px; }
.signal-card {
    flex: 1 1 220px; max-width: 340px;
    border-radius: 14px; padding: 18px 22px;
    font-family: Manrope, sans-serif; position: relative;
    border: 1.5px solid rgba(0,0,0,0.06);
}
.signal-card.bullish { background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border-color: #bbf7d0; }
.signal-card.bearish { background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); border-color: #fecaca; }
.signal-card.neutral { background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border-color: #e2e8f0; }
.signal-ticker {
    font-size: 1.15rem; font-weight: 800; letter-spacing: -0.02em;
    color: var(--on-surface); margin-bottom: 2px;
}
.signal-dir {
    font-size: 0.7rem; font-weight: 800; letter-spacing: 0.08em;
    text-transform: uppercase; margin-bottom: 6px; display: inline-block;
    padding: 2px 8px; border-radius: 6px;
}
.signal-dir.bullish { background: #22c55e; color: #fff; }
.signal-dir.bearish { background: #ef4444; color: #fff; }
.signal-dir.neutral { background: #94a3b8; color: #fff; }
.signal-move { font-size: 0.82rem; color: var(--on-surface-variant); margin-bottom: 4px; }
.signal-reason { font-size: 0.75rem; color: var(--on-surface-variant); line-height: 1.4; }

/* ── Section header with icon ───────────────────────────────────── */
.report-section-header {
    font-family: Manrope, sans-serif; font-weight: 800;
    font-size: 1.1rem; color: var(--on-surface);
    letter-spacing: -0.02em; margin: 0 0 10px;
    padding-bottom: 8px; border-bottom: 2px solid var(--outline-variant);
}

/* ── Thesis banner ──────────────────────────────────────────────── */
.thesis-banner {
    background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
    color: #f8fafc; border-radius: 14px; padding: 22px 28px;
    font-family: Manrope, sans-serif; margin-bottom: 16px;
}
.thesis-label {
    font-size: 0.65rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: #C8A951; margin-bottom: 6px;
}
.thesis-text {
    font-size: 1.15rem; font-weight: 700; line-height: 1.5;
    letter-spacing: -0.01em;
}

/* ── Section highlight callout ──────────────────────────────────── */
.section-highlight {
    background: var(--primary-container);
    border-left: 4px solid #C8A951; border-radius: 0 10px 10px 0;
    padding: 10px 16px; margin: 10px 0 12px;
    font-family: Manrope, sans-serif; font-size: 0.88rem;
    font-weight: 700; color: var(--on-surface); line-height: 1.45;
}

/* ── Macro gauge row ────────────────────────────────────────────── */
.macro-gauge-row {
    display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0;
}
.macro-gauge {
    flex: 1 1 140px; text-align: center; padding: 12px 10px;
    border-radius: 12px; background: var(--surface); border: 1px solid var(--outline-variant);
    font-family: Manrope, sans-serif;
}
.macro-gauge-arrow { font-size: 1.5rem; margin-bottom: 2px; }
.macro-gauge-name {
    font-size: 0.65rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.05em; color: var(--on-surface-variant); margin-bottom: 2px;
}
.macro-gauge-val {
    font-size: 1rem; font-weight: 800; color: var(--on-surface);
}
.macro-gauge-delta { font-size: 0.7rem; }

/* ── Geopolitical callout ───────────────────────────────────────── */
.geo-callout {
    background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
    border: 1px solid #bae6fd; border-radius: 12px;
    padding: 14px 18px; margin: 8px 0;
    font-family: Inter, sans-serif; font-size: 0.84rem;
    color: #0c4a6e; line-height: 1.5;
}
.geo-callout-title {
    font-family: Manrope, sans-serif; font-weight: 800;
    font-size: 0.78rem; text-transform: uppercase;
    letter-spacing: 0.06em; color: #0369a1; margin-bottom: 6px;
}
</style>"""


# ── Dark mode override (injected conditionally) ──────────────────
DARK_MODE_CSS = """
<style>
:root {
    --primary: #d4af37 !important;
    --primary-light: #e8c84a !important;
    --primary-container: #3d2e06 !important;
    --on-surface: #e2e8f0 !important;
    --on-surface-variant: #94a3b8 !important;
    --surface: #0f172a !important;
    --surface-card: rgba(30, 41, 59, 0.8) !important;
    --surface-elevated: #1e293b !important;
    --outline-variant: #334155 !important;
    --error: #f87171 !important;
    --shadow-premium: 0 20px 50px rgba(0, 0, 0, 0.3) !important;
    --shadow-glass: 0 8px 32px 0 rgba(0, 0, 0, 0.2) !important;
    --bar-track-bg: #1e293b !important;
    --sidebar-bg: #1e293b !important;
    --sidebar-shadow: 2px 0 20px rgba(0,0,0,0.2) !important;
    --code-bg: #1e293b !important;
    --hover-bg: rgba(255,255,255,0.04) !important;
}
/* Dark mode overrides for Streamlit internals */
.stApp { background-color: #0f172a !important; }
section[data-testid="stSidebar"] { background: #1e293b !important; }
[data-testid="stSidebar"] [data-testid="stMarkdown"] p,
[data-testid="stSidebar"] [data-testid="stMarkdown"] span,
[data-testid="stSidebar"] label { color: #e2e8f0 !important; }
.stRadio label span { color: #e2e8f0 !important; }
[data-testid="stVerticalBlockBorderWrapper"] {
    background: rgba(30,41,59,0.8) !important;
    border-color: #334155 !important;
}
[data-testid="stExpander"] {
    background: rgba(30,41,59,0.8) !important;
    border-color: #334155 !important;
}
[data-testid="stExpander"] summary span { color: #e2e8f0 !important; }
.stSelectbox label, .stMultiSelect label,
.stTextInput label, .stNumberInput label { color: #e2e8f0 !important; }
p, li, span { color: #e2e8f0; }
.stCaption, [data-testid="stCaptionContainer"] p { color: #94a3b8 !important; }
hr { border-color: #334155 !important; }
/* Signal cards in dark mode */
.signal-card.bullish { background: linear-gradient(135deg, #064e3b 0%, #065f46 100%) !important; border-color: #047857 !important; }
.signal-card.bearish { background: linear-gradient(135deg, #450a0a 0%, #7f1d1d 100%) !important; border-color: #991b1b !important; }
.signal-card.neutral { background: linear-gradient(135deg, #1e293b 0%, #334155 100%) !important; border-color: #475569 !important; }
/* Thesis banner stays dark in both modes */
/* Pill adjustments */
.pill-green  { background: #065f46 !important; color: #6ee7b7 !important; }
.pill-amber  { background: #3d2e06 !important; color: #fcd34d !important; }
.pill-red    { background: #7f1d1d !important; color: #fca5a5 !important; }
.pill-gray   { background: #334155 !important; color: #94a3b8 !important; }
/* Sector dot box backgrounds */
.sector-dot-box.ai     { background: #1e3a5f !important; }
.sector-dot-box.space  { background: #2d2250 !important; }
.sector-dot-box.optical { background: #3d2e06 !important; }
/* Geo callout */
.geo-callout { background: linear-gradient(135deg, #0c1929 0%, #0f2744 100%) !important; border-color: #1e3a5f !important; color: #93c5fd !important; }
.geo-callout-title { color: #60a5fa !important; }
/* Section highlight */
.section-highlight { background: #3d2e06 !important; color: #fcd34d !important; }
/* Streamlit selectbox / multiselect / toggle */
[data-testid="stSelectbox"] div[data-baseweb] { background: #1e293b !important; color: #e2e8f0 !important; }
[data-testid="stMultiSelect"] div[data-baseweb] { background: #1e293b !important; color: #e2e8f0 !important; }
/* Input fields */
input, textarea { background-color: #1e293b !important; color: #e2e8f0 !important; }
/* Plotly charts — override the white modebar backgrounds */
.js-plotly-plot .plotly .modebar { background: transparent !important; }
.js-plotly-plot .plotly .modebar-btn path { fill: #94a3b8 !important; }
/* Alert boxes */
[data-testid="stAlert"] { background-color: rgba(30,41,59,0.8) !important; border-color: #334155 !important; }
[data-testid="stAlert"] p { color: #e2e8f0 !important; }
/* Streamlit subheader / markdown bold */
.stApp strong, .stApp b { color: #e2e8f0; }
/* Prediction card dark mode backgrounds */
div[style*="rgba(34,197,94,0.08)"] { background: rgba(34,197,94,0.15) !important; }
div[style*="rgba(239,68,68,0.08)"] { background: rgba(239,68,68,0.15) !important; }
div[style*="rgba(100,116,139,0.08)"] { background: rgba(100,116,139,0.12) !important; }
div[style*="rgba(100,116,139,0.05)"] { background: rgba(100,116,139,0.1) !important; }
/* Streamlit divider */
[data-testid="stHorizontalRule"] { border-color: #334155 !important; }
/* Toggle switch */
[data-testid="stToggle"] label span { color: #e2e8f0 !important; }
/* Radio buttons text */
.stRadio > div[role="radiogroup"] label { color: #e2e8f0 !important; }
/* Dropdown menu items */
[data-baseweb="menu"] li { background: #1e293b !important; color: #e2e8f0 !important; }
[data-baseweb="menu"] li:hover { background: #334155 !important; }
/* Popover / tooltip */
[data-baseweb="popover"] { background: #1e293b !important; }
/* Progress bar track */
[data-testid="stProgress"] > div { background: #334155 !important; }
/* Button text in dark mode */
button[data-testid="stBaseButton-secondary"] { color: #e2e8f0 !important; }
button[data-testid="stBaseButton-minimal"] { color: #e2e8f0 !important; }
/* Status widget */
[data-testid="stStatusWidget"] { background: #1e293b !important; border-color: #334155 !important; }
[data-testid="stStatusWidget"] p { color: #e2e8f0 !important; }
/* Toast notifications */
[data-testid="stToast"] { background: #1e293b !important; color: #e2e8f0 !important; border-color: #334155 !important; }
/* Macro gauge dark mode */
.macro-gauge { background: #1e293b !important; border-color: #334155 !important; }
.macro-gauge-name { color: #94a3b8 !important; }
.macro-gauge-val { color: #e2e8f0 !important; }
</style>"""
