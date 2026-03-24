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
                'letter-spacing:-0.03em;color:#0f172a">Prediction Tracker</h2>',
                unsafe_allow_html=True)
    st.caption("AI directional predictions with reasoning — verified against actual prices after 1 week")

    stats = _cached_prediction_stats()
    k1, k2, k3, k4, k5 = st.columns(5)
    kpi_items = [
        (k1, "Total", str(stats["total_predictions"]), ""),
        (k2, "Verified", str(stats["checked"]), ""),
        (k3, "Pending", str(stats["unchecked"]), ""),
        (k4, "Avg |Weekly Δ|",
         f"{stats.get('avg_absolute_weekly_change', 0):.1f}%"
         if stats.get('avg_absolute_weekly_change') else "N/A", ""),
        (k5, "AI Accuracy",
         f"{stats.get('direction_accuracy_pct')}%"
         if stats.get('direction_accuracy_pct') is not None else "N/A", ""),
    ]
    for col, label, value, sub in kpi_items:
        with col:
            st.markdown(
                f'<div class="kpi-card">'
                f'<div class="kpi-label">{label}</div>'
                f'<div class="kpi-value" style="font-size:1.75rem">{value}</div>'
                f'</div>', unsafe_allow_html=True)

    st.write("")

    # ── Prediction Accuracy Chart ─────────────────────────────────
    accuracy_data = _cached_accuracy_over_time()
    _render_accuracy_chart(accuracy_data)

    st.write("")

    reports = _cached_reports_list(limit=50)
    for rpt in reports:
        preds = _cached_predictions(rpt["id"])
        if not preds:
            continue
        checked = sum(1 for p in preds if p.get("price_1w_later") is not None)
        has_ai = any(p.get("ai_direction") for p in preds)
        icon = "●" if checked == len(preds) else "○"
        ai_badge = " · 🤖 AI predictions" if has_ai else ""
        with st.container(border=True):
            st.markdown(f"**{icon}  {rpt['sector_name']}** · "
                        f"{to_hkt_short(rpt['created_at'])} · "
                        f"{checked}/{len(preds)} verified{ai_badge}")
            _render_predictions_table(preds)


# ═══════════════════════════════════════════════════════════════════
# PREDICTIONS TABLE
# ═══════════════════════════════════════════════════════════════════

def _render_predictions_table(preds: list[dict]):
    h1, h2, h3, h4 = st.columns([1.5, 1.8, 2.5, 1.2])
    with h1:
        st.caption("TICKER / AI CALL")
    with h2:
        st.caption("AT REPORT")
    with h3:
        st.caption("1 WEEK LATER")
    with h4:
        st.caption("RESULT")

    dir_colors = {"BULLISH": "#22c55e", "BEARISH": "#ef4444", "NEUTRAL": "#64748b"}
    dir_icons = {"BULLISH": "📈", "BEARISH": "📉", "NEUTRAL": "➡️"}

    for pred in preds:
        ai_dir = pred.get("ai_direction")
        ai_change = pred.get("ai_predicted_change", "")
        ai_reasoning = pred.get("ai_reasoning", "")
        ai_risk = pred.get("ai_risk", "")

        c1, c2, c3, c4 = st.columns([1.5, 1.8, 2.5, 1.2])
        with c1:
            st.markdown(f"**{pred['ticker']}**")
            if ai_dir:
                color = dir_colors.get(ai_dir, "#9C9C9C")
                icon = dir_icons.get(ai_dir, "")
                st.markdown(
                    f'<span style="color:{color};font-weight:700;font-size:0.85rem">'
                    f'{icon} {ai_dir}</span>',
                    unsafe_allow_html=True)
                if ai_change:
                    st.caption(f"Expected: {ai_change}")
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
            elif pred.get("checked_at"):
                st.caption(pred["checked_at"][:10])

        # Show AI reasoning below the row
        if ai_reasoning:
            st.markdown(
                f'<div style="margin:-8px 0 8px 0;padding:10px 14px;background:#f8fafc;'
                f'border-radius:1rem;font-size:0.85rem;border:1px solid rgba(255,255,255,0.4)">'
                f'💭 <strong>Reasoning:</strong> {ai_reasoning}'
                f'{"<br>⚠️ <strong>Key Risk:</strong> " + ai_risk if ai_risk else ""}'
                f'</div>',
                unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# PREDICTION ACCURACY CHART
# ═══════════════════════════════════════════════════════════════════

def _render_accuracy_chart(accuracy_data: list[dict]):
    """Bar + line chart showing per-report accuracy and cumulative correct rate."""
    # Only show chart if we have verified predictions
    checked = [d for d in accuracy_data if d["accuracy_pct"] is not None]
    if not checked:
        with st.container(border=True):
            st.markdown("**📊 Prediction Accuracy Over Time**")
            st.caption("Chart will appear once predictions are verified against actual prices (after 1 week).")
        return

    with st.container(border=True):
        st.markdown("**📊 Prediction Accuracy Over Time**")

        # --- Per-report accuracy bar chart ---
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

        # Render with Streamlit native charts via a mini dataframe
        import pandas as pd
        chart_df = pd.DataFrame({
            "Report": labels,
            "Accuracy (%)": accuracies,
            "Correct": correct_counts,
            "Wrong": wrong_counts,
            "Pending": pending_counts,
            "Cumulative Accuracy (%)": cumulative_rates,
        })

        # Show two charts side by side
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
