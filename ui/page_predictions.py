"""
Predictions page — AI directional predictions with reasoning + accuracy tracking.
"""

import streamlit as st

from database.reports_db import (
    get_reports_list,
    get_prediction_accuracy,
    get_predictions_for_report,
    get_prediction_accuracy_over_time,
)
from utils.time_utils import to_hkt_short


# ── Cached loaders ────────────────────────────────────────────────

@st.cache_data(ttl=30)
def _cached_reports_list(limit: int = 50):
    return get_reports_list(limit=limit)


@st.cache_data(ttl=30)
def _cached_prediction_stats():
    return get_prediction_accuracy()


@st.cache_data(ttl=30)
def _cached_predictions(report_id: int):
    return get_predictions_for_report(report_id)


@st.cache_data(ttl=30)
def _cached_accuracy_over_time():
    return get_prediction_accuracy_over_time()


# ═══════════════════════════════════════════════════════════════════
# PAGE ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def render():
    st.markdown('<h2 style="font-family:Manrope,sans-serif;font-weight:800;'
                'letter-spacing:-0.03em;color:var(--on-surface)">Prediction Tracker</h2>',
                unsafe_allow_html=True)
    st.caption("AI directional predictions with reasoning — verified against actual prices after 1 week")

    stats = _cached_prediction_stats()

    # ── KPI row — 2x2 on mobile, 4 cols on desktop ───────────────
    k1, k2, k3, k4 = st.columns(4)
    kpi_items = [
        (k1, "Total Predictions", str(stats["total_predictions"]),
         "across all reports"),
        (k2, "Verified",
         f"{stats['checked']} / {stats['total_predictions']}",
         "checked against actuals"),
        (k3, "AI Accuracy",
         f"{stats.get('direction_accuracy_pct')}%"
         if stats.get('direction_accuracy_pct') is not None else "—",
         f"{stats.get('direction_correct', 0)} correct calls"
         if stats.get('direction_correct') else "pending verification"),
        (k4, "Avg |Weekly Δ|",
         f"{stats.get('avg_absolute_weekly_change', 0):.1f}%"
         if stats.get('avg_absolute_weekly_change') else "—",
         "absolute price movement"),
    ]
    for col, label, value, sub in kpi_items:
        with col:
            st.markdown(
                f'<div class="kpi-card">'
                f'<div class="kpi-label">{label}</div>'
                f'<div class="kpi-value" style="font-size:1.75rem">{value}</div>'
                f'<div style="font-size:0.7rem;color:var(--on-surface-variant);margin-top:0.25rem">{sub}</div>'
                f'</div>', unsafe_allow_html=True)

    st.write("")

    # ── Accuracy chart (with fallback for no verified data) ───────
    accuracy_data = _cached_accuracy_over_time()
    _render_accuracy_chart(accuracy_data)

    st.write("")

    # ── Report selector ───────────────────────────────────────────
    reports = _cached_reports_list(limit=50)
    # Filter to reports that have predictions
    reports_with_preds = []
    for rpt in reports:
        preds = _cached_predictions(rpt["id"])
        if preds:
            reports_with_preds.append((rpt, preds))

    if not reports_with_preds:
        st.info(
            "**No predictions yet.** Run an analysis from the Overview page — "
            "the AI will generate directional predictions for each stock "
            "in the analysed sectors."
        )
        return

    # Build selector options: "Sector · Date"
    selector_options = [
        f"{rpt['sector_name']} · {to_hkt_short(rpt['created_at'])}"
        for rpt, _ in reports_with_preds
    ]

    col_sel, _ = st.columns([3, 3])
    with col_sel:
        selected_idx = st.selectbox(
            "Select Report",
            range(len(selector_options)),
            format_func=lambda i: selector_options[i],
            label_visibility="collapsed",
        )

    rpt, preds = reports_with_preds[selected_idx]
    checked = sum(1 for p in preds if p.get("price_1w_later") is not None)
    total_preds = len(preds)
    ai_preds = [p for p in preds if p.get("ai_direction")]
    no_ai_preds = [p for p in preds if not p.get("ai_direction")]
    status_icon = "✅" if checked == total_preds else ("⏳" if checked == 0 else "🔄")

    with st.container(border=True):
        # Header row with sector + summary
        hdr_l, hdr_r = st.columns([3, 1])
        with hdr_l:
            st.markdown(
                f"**{rpt['sector_name']}** · "
                f"{to_hkt_short(rpt['created_at'])}")
        with hdr_r:
            st.markdown(
                f'<div style="text-align:right;font-size:0.8rem;color:var(--on-surface-variant)">'
                f'{status_icon} {checked}/{total_preds} verified'
                f'</div>', unsafe_allow_html=True)

        # AI Prediction cards
        if ai_preds:
            _render_ai_predictions(ai_preds)
        if no_ai_preds:
            _render_no_prediction_cards(no_ai_preds)
        if not ai_preds and not no_ai_preds:
            _render_predictions_table(preds)


# ═══════════════════════════════════════════════════════════════════
# AI PREDICTION CARDS (new layout — reasoning-first)
# ═══════════════════════════════════════════════════════════════════

_DIR_STYLE = {
    "BULLISH":  {"bg": "rgba(34,197,94,0.08)",  "border": "#22c55e", "icon": "📈", "color": "#16a34a"},
    "BEARISH":  {"bg": "rgba(239,68,68,0.08)",  "border": "#ef4444", "icon": "📉", "color": "#dc2626"},
    "NEUTRAL":  {"bg": "rgba(100,116,139,0.08)","border": "#94a3b8", "icon": "➡️", "color": "#64748b"},
}


def _render_ai_predictions(preds: list[dict]):
    """Render AI predictions as visual cards with reasoning front-and-center."""
    # Group predictions into rows of 2–3
    cols_per_row = min(len(preds), 3)
    for row_start in range(0, len(preds), cols_per_row):
        row_preds = preds[row_start:row_start + cols_per_row]
        cols = st.columns(len(row_preds))

        for col, pred in zip(cols, row_preds):
            with col:
                ai_dir = pred.get("ai_direction", "NEUTRAL")
                style = _DIR_STYLE.get(ai_dir, _DIR_STYLE["NEUTRAL"])
                ticker = pred.get("ticker", "?")
                ai_change = pred.get("ai_predicted_change", "")
                ai_reasoning = pred.get("ai_reasoning", "")
                # Truncate long reasoning to keep cards compact
                if len(ai_reasoning) > 150:
                    ai_reasoning = ai_reasoning[:147] + "..."
                ai_risk = pred.get("ai_risk", "")
                if len(ai_risk) > 80:
                    ai_risk = ai_risk[:77] + "..."
                price_at = pred.get("price_at_report")
                price_1w = pred.get("price_1w_later")
                actual_ch = pred.get("actual_change_1w")
                correct = pred.get("prediction_correct")

                # Result badge
                result_html = ""
                if correct is not None:
                    if correct == 1:
                        result_html = '<span class="pill pill-green" style="margin-left:8px">✓ Correct</span>'
                    else:
                        result_html = '<span class="pill pill-red" style="margin-left:8px">✗ Wrong</span>'
                elif price_1w is None:
                    result_html = '<span class="pill pill-gray" style="margin-left:8px">pending</span>'

                # Price movement
                price_html = ""
                if price_at:
                    price_html = f'<div style="font-size:0.78rem;color:var(--on-surface-variant);margin-top:4px">${price_at:.2f}'
                    if price_1w is not None and actual_ch is not None:
                        arrow = "↑" if actual_ch > 0 else ("↓" if actual_ch < 0 else "→")
                        ch_color = "#16a34a" if actual_ch > 0 else ("#dc2626" if actual_ch < 0 else "var(--on-surface-variant)")
                        price_html += (f' → ${price_1w:.2f} '
                                       f'<span style="color:{ch_color};font-weight:700">'
                                       f'{arrow} {actual_ch:+.1f}%</span>')
                    else:
                        price_html += ' → <span style="color:var(--on-surface-variant)">awaiting</span>'
                    price_html += '</div>'

                # Card HTML
                st.markdown(
                    f'<div style="background:{style["bg"]};border-left:4px solid {style["border"]};'
                    f'border-radius:1rem;padding:1rem 1.25rem;margin-bottom:0.5rem">'
                    # Ticker + Direction header
                    f'<div style="display:flex;align-items:center;justify-content:space-between;'
                    f'margin-bottom:0.5rem">'
                    f'<span style="font-weight:800;font-size:1.1rem;font-family:Manrope,sans-serif">'
                    f'{ticker}</span>'
                    f'<span style="color:{style["color"]};font-weight:700;font-size:0.85rem">'
                    f'{style["icon"]} {ai_dir}'
                    f'{" · " + ai_change if ai_change else ""}</span>'
                    f'</div>'
                    # Result + Price
                    f'<div style="display:flex;align-items:center;flex-wrap:wrap">'
                    f'{result_html}'
                    f'</div>'
                    f'{price_html}'
                    # Reasoning (visible by default!)
                    f'{"<div style=" + chr(34) + "margin-top:0.75rem;font-size:0.82rem;line-height:1.6;color:var(--on-surface-variant)" + chr(34) + ">💭 " + ai_reasoning + "</div>" if ai_reasoning else ""}'
                    # Risk
                    f'{"<div style=" + chr(34) + "margin-top:0.35rem;font-size:0.78rem;color:#f59e0b" + chr(34) + ">⚠️ " + ai_risk + "</div>" if ai_risk else ""}'
                    f'</div>',
                    unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# "NO PREDICTION" CARDS — tickers without AI directional prediction
# ═══════════════════════════════════════════════════════════════════

def _render_no_prediction_cards(preds: list[dict]):
    """Render cards for tickers where the AI couldn't make a confident prediction."""
    cols_per_row = min(len(preds), 3)
    for row_start in range(0, len(preds), cols_per_row):
        row_preds = preds[row_start:row_start + cols_per_row]
        cols = st.columns(len(row_preds))

        for col, pred in zip(cols, row_preds):
            with col:
                ticker = pred.get("ticker", "?")
                price_at = pred.get("price_at_report")
                price_1w = pred.get("price_1w_later")
                actual_ch = pred.get("actual_change_1w")

                # Price line
                price_html = ""
                if price_at:
                    price_html = f'<div style="font-size:0.78rem;color:var(--on-surface-variant);margin-top:4px">${price_at:.2f}'
                    if price_1w is not None and actual_ch is not None:
                        arrow = "↑" if actual_ch > 0 else ("↓" if actual_ch < 0 else "→")
                        ch_color = "#16a34a" if actual_ch > 0 else ("#dc2626" if actual_ch < 0 else "var(--on-surface-variant)")
                        price_html += (f' → ${price_1w:.2f} '
                                       f'<span style="color:{ch_color};font-weight:700">'
                                       f'{arrow} {actual_ch:+.1f}%</span>')
                    else:
                        price_html += ' → <span style="color:var(--on-surface-variant)">awaiting</span>'
                    price_html += '</div>'

                st.markdown(
                    f'<div style="background:rgba(100,116,139,0.05);border-left:4px solid var(--on-surface-variant);'
                    f'border-radius:1rem;padding:1rem 1.25rem;margin-bottom:0.5rem">'
                    f'<div style="display:flex;align-items:center;justify-content:space-between;'
                    f'margin-bottom:0.5rem">'
                    f'<span style="font-weight:800;font-size:1.1rem;font-family:Manrope,sans-serif">'
                    f'{ticker}</span>'
                    f'<span style="color:var(--on-surface-variant);font-weight:700;font-size:0.75rem;'
                    f'text-transform:uppercase;letter-spacing:0.05em">No prediction</span>'
                    f'</div>'
                    f'{price_html}'
                    f'<div style="margin-top:0.5rem;font-size:0.78rem;color:var(--on-surface-variant)">'
                    f'Mixed signals — no confident directional call'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# FALLBACK TABLE (for reports without AI predictions)
# ═══════════════════════════════════════════════════════════════════

def _render_predictions_table(preds: list[dict]):
    h1, h2, h3, h4 = st.columns([1.5, 1.8, 2.5, 1.2])
    with h1:
        st.caption("TICKER")
    with h2:
        st.caption("AT REPORT")
    with h3:
        st.caption("1 WEEK LATER")
    with h4:
        st.caption("RESULT")

    for pred in preds:
        c1, c2, c3, c4 = st.columns([1.5, 1.8, 2.5, 1.2])
        with c1:
            st.markdown(f"**{pred['ticker']}**")
        with c2:
            p = pred.get("price_at_report")
            st.write(f"${p:.2f}" if p else "—")
        with c3:
            if pred.get("price_1w_later"):
                ch = pred.get("actual_change_1w", 0)
                arrow = "↑" if ch > 0 else ("↓" if ch < 0 else "→")
                color = "#22c55e" if ch > 0 else ("#ef4444" if ch < 0 else "#64748b")
                st.markdown(
                    f'${pred["price_1w_later"]:.2f} '
                    f'<span style="color:{color};font-weight:700">{arrow} {ch:+.1f}%</span>',
                    unsafe_allow_html=True)
            else:
                st.caption("Pending…")
        with c4:
            correct = pred.get("prediction_correct")
            if correct is not None:
                if correct == 1:
                    st.markdown('<span class="pill pill-green">✓ Correct</span>',
                                unsafe_allow_html=True)
                else:
                    st.markdown('<span class="pill pill-red">✗ Wrong</span>',
                                unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# PREDICTION ACCURACY CHART
# ═══════════════════════════════════════════════════════════════════

def _render_accuracy_chart(accuracy_data: list[dict]):
    """Bar + line chart showing per-report accuracy and cumulative correct rate."""
    checked = [d for d in accuracy_data if d["accuracy_pct"] is not None]

    with st.container(border=True):
        st.markdown("**📊 Prediction Accuracy Over Time**")

        if not checked:
            # Helpful fallback instead of dead end
            st.markdown(
                '<div style="padding:1.5rem;text-align:center;color:var(--on-surface-variant)">'
                '<div style="font-size:2rem;margin-bottom:0.5rem">📋</div>'
                '<div style="font-size:0.9rem;font-weight:600;margin-bottom:0.5rem">'
                'Accuracy tracking activates automatically</div>'
                '<div style="font-size:0.82rem;line-height:1.6">'
                'After each analysis, the system records AI price predictions.<br>'
                'One week later, it checks actual prices and scores accuracy.<br>'
                '<strong>You don\'t need to do anything</strong> — just run analyses and check back.'
                '</div></div>',
                unsafe_allow_html=True)

            # Still show unverified predictions summary if available
            unverified = [d for d in accuracy_data]
            if unverified:
                total_p = sum(d.get("correct", 0) + d.get("wrong", 0) + d.get("pending", 0) for d in unverified)
                st.caption(f"📌 {total_p} predictions waiting for verification (need 7+ days to mature)")
            return

        # --- Charts ---
        labels = []
        accuracies = []
        correct_counts = []
        wrong_counts = []
        pending_counts = []
        cumulative_correct = 0
        cumulative_total = 0
        cumulative_rates = []

        for d in accuracy_data:
            short_date = to_hkt_short(d["created_at"])
            sector_short = d["sector_name"][:12]
            labels.append(f"#{d['report_id']} {sector_short}\n{short_date}")
            accuracies.append(d["accuracy_pct"] if d["accuracy_pct"] is not None else 0)
            correct_counts.append(d["correct"])
            wrong_counts.append(d["wrong"])
            pending_counts.append(d["pending"])

            cumulative_correct += d["correct"]
            cumulative_total += d["correct"] + d["wrong"]
            cum_rate = round(cumulative_correct / cumulative_total * 100, 1) if cumulative_total > 0 else 0
            cumulative_rates.append(cum_rate)

        import pandas as pd
        chart_df = pd.DataFrame({
            "Report": labels,
            "Accuracy (%)": accuracies,
            "Correct": correct_counts,
            "Wrong": wrong_counts,
            "Pending": pending_counts,
            "Cumulative Accuracy (%)": cumulative_rates,
        })

        ch1, ch2 = st.columns(2)

        with ch1:
            st.markdown("##### Per-Report Accuracy")
            bar_df = chart_df.set_index("Report")[["Correct", "Wrong", "Pending"]]
            st.bar_chart(bar_df, color=["#66BB6A", "#EF5350", "#BDBDBD"])

        with ch2:
            st.markdown("##### Cumulative Correct Rate")
            line_df = chart_df.set_index("Report")[["Cumulative Accuracy (%)"]]
            st.line_chart(line_df, color=["#5C9CE6"])

        # Summary row
        total_c = sum(correct_counts)
        total_w = sum(wrong_counts)
        total_p = sum(pending_counts)
        overall = round(total_c / (total_c + total_w) * 100, 1) if (total_c + total_w) > 0 else 0
        st.caption(
            f"Overall: **{total_c}** correct · **{total_w}** wrong · "
            f"**{total_p}** pending → **{overall}% accuracy**"
        )
