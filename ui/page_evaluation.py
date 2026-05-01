"""
Evaluation page — empirical evidence for the anti-hallucination pipeline.

Two tabs:
  1. Prediction Accuracy — statistical breakdown of the AI's directional calls
     with binomial significance test vs 50% random baseline.
  2. Ablation Study — retrospective analysis of validator interventions,
     showing how often Layer 3/4 caught and corrected real errors.
"""

import streamlit as st


# ── Cached loaders ────────────────────────────────────────────────

@st.cache_data(ttl=120)
def _load_prediction_stats():
    from evals.prediction_stats import get_prediction_stats
    return get_prediction_stats()


@st.cache_data(ttl=300)
def _load_ablation(max_reports: int = 100):
    from evals.ablation_study import run_ablation_study
    return run_ablation_study(max_reports=max_reports)


# ── Reusable card renderer ─────────────────────────────────────────

def _kpi_card(col, label: str, value: str, sub: str, color: str = "var(--primary)"):
    col.markdown(
        f'<div style="padding:1rem 1.2rem;background:var(--surface-card);'
        f'border-radius:0.85rem;border:1px solid var(--outline-variant)">'
        f'<div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.1em;color:var(--on-surface-variant);margin-bottom:0.4rem">{label}</div>'
        f'<div style="font-size:1.9rem;font-weight:800;color:{color};'
        f'font-family:Manrope,sans-serif;line-height:1">{value}</div>'
        f'<div style="font-size:0.72rem;color:var(--on-surface-variant);margin-top:0.3rem">{sub}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _section(title: str):
    st.markdown(
        f'<div style="font-family:Manrope,sans-serif;font-size:1rem;font-weight:700;'
        f'color:var(--on-surface);margin:1.5rem 0 0.5rem">{title}</div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════
# TAB 1: PREDICTION ACCURACY
# ═══════════════════════════════════════════════════════════════════

def _render_prediction_accuracy():
    st.caption(
        "The system records a directional call (BULLISH / BEARISH / NEUTRAL) for every ticker "
        "at analysis time, then checks the actual price 1 week later. "
        "This is objective ground truth — the market decides, not the AI."
    )

    with st.spinner("Loading prediction statistics…"):
        stats = _load_prediction_stats()

    if stats.with_direction == 0:
        st.info(
            "No verified directional predictions yet. Predictions are checked after 1 week. "
            "Run the Prediction Tracker page to verify outstanding calls."
        )
        return

    # ── KPI row ───────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    acc_color = "#22c55e" if stats.accuracy_pct >= 50 else "#ef4444"
    _kpi_card(c1, "Verified Directional Calls", str(stats.with_direction),
              f"out of {stats.verified_predictions} verified")
    _kpi_card(c2, "Correct Calls", str(stats.correct),
              f"{stats.accuracy_pct}% accuracy", acc_color)
    _kpi_card(c3, "Random Baseline", "50.0%", "expected if guessing")
    _kpi_card(c4, "Significance", f"p = {stats.p_value}",
              stats.significance_label,
              "#22c55e" if stats.is_significant else "var(--on-surface-variant)")

    st.write("")

    # ── Significance interpretation ───────────────────────────────
    if stats.is_significant and stats.accuracy_pct < 50:
        st.warning(
            f"**Finding:** The AI's directional accuracy ({stats.accuracy_pct}%) is statistically "
            f"significantly *below* random (p={stats.p_value}). "
            f"This indicates a systematic directional bias — the model is contrarian relative to "
            f"actual outcomes. This is a genuine finding worth investigating.",
            icon="⚠️",
        )
    elif stats.is_significant and stats.accuracy_pct > 50:
        st.success(
            f"**Finding:** The AI's directional accuracy ({stats.accuracy_pct}%) is statistically "
            f"significantly *above* random (p={stats.p_value}). ",
            icon="✅",
        )
    else:
        st.info(
            f"**Finding:** Accuracy of {stats.accuracy_pct}% is not significantly different "
            f"from random (p={stats.p_value}, 95% CI: [{stats.ci_lower}%, {stats.ci_upper}%]). "
            f"More verified predictions are needed for a definitive conclusion.",
            icon="ℹ️",
        )

    # ── Confidence interval ───────────────────────────────────────
    st.caption(
        f"95% confidence interval: [{stats.ci_lower}%, {stats.ci_upper}%] &nbsp;·&nbsp; "
        f"Random baseline: 50% &nbsp;·&nbsp; n={stats.with_direction}"
    )

    # ── Direction breakdown table ─────────────────────────────────
    _section("Accuracy by Direction (BULLISH / BEARISH / NEUTRAL)")
    if stats.by_direction:
        import pandas as pd
        df_dir = pd.DataFrame([
            {
                "Direction": row.direction,
                "Total Calls": row.total,
                "Correct": row.correct,
                "Accuracy %": f"{row.accuracy}%",
                "Share of Calls": f"{round(row.total / stats.with_direction * 100, 1)}%",
            }
            for row in stats.by_direction
        ])
        st.dataframe(df_dir, use_container_width=True, hide_index=True)

        # Bias insight
        if stats.bullish_rate > 60:
            st.caption(
                f"Bias note: {stats.bullish_rate}% of calls are BULLISH — the model is "
                f"systematically optimistic. This may explain below-random accuracy in bearish markets."
            )
        elif stats.bearish_rate > 60:
            st.caption(
                f"Bias note: {stats.bearish_rate}% of calls are BEARISH — the model is "
                f"systematically pessimistic."
            )

    # ── Sector breakdown table ─────────────────────────────────────
    _section("Accuracy by Sector")
    if stats.by_sector:
        import pandas as pd
        df_sec = pd.DataFrame([
            {
                "Sector": row.sector,
                "Calls": row.total,
                "Correct": row.correct,
                "Accuracy %": f"{row.accuracy}%",
            }
            for row in stats.by_sector
        ])
        st.dataframe(df_sec, use_container_width=True, hide_index=True)

    # ── Accuracy over time chart ───────────────────────────────────
    if len(stats.accuracy_over_time) >= 3:
        _section("Cumulative Accuracy Over Time")
        import pandas as pd
        import plotly.graph_objects as go

        df_time = pd.DataFrame(stats.accuracy_over_time)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_time["date"],
            y=df_time["cumulative_accuracy"],
            mode="lines+markers",
            name="Cumulative Accuracy",
            line=dict(color="#00B4D8", width=2),
            marker=dict(size=5),
        ))
        fig.add_hline(y=50, line_dash="dash", line_color="#ef4444",
                      annotation_text="Random baseline (50%)", annotation_position="top right")
        fig.update_layout(
            height=280,
            margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(title="Accuracy %", range=[0, 100], gridcolor="rgba(255,255,255,0.08)"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
            font=dict(color="var(--on-surface)"),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            f"Avg absolute weekly price movement: {stats.avg_actual_change_all}% &nbsp;·&nbsp; "
            f"Avg movement on correct calls: {stats.avg_actual_change_correct}% &nbsp;·&nbsp; "
            f"Avg movement on wrong calls: {stats.avg_actual_change_wrong}%"
        )


# ═══════════════════════════════════════════════════════════════════
# TAB 2: ABLATION STUDY
# ═══════════════════════════════════════════════════════════════════

def _render_ablation():
    st.caption(
        "This ablation study mines stored pipeline states to measure what the validation pipeline "
        "actually caught. Every report's full provenance is stored — including pre-correction drafts — "
        "so we can compare the raw AI output against the validated output empirically."
    )

    n_reports = st.slider("Reports to scan (most recent)", 10, 200, 100, 10)

    with st.spinner(f"Scanning {n_reports} reports for validation events…"):
        ab = _load_ablation(max_reports=n_reports)

    if ab.total_reports_analyzed == 0:
        st.info("No reports found in the database.")
        return

    # ── KPI row ───────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    _kpi_card(c1, "Reports Scanned", str(ab.total_reports_analyzed),
              f"{ab.reports_with_pipeline_state} with full state")
    _kpi_card(c2, "Intervention Rate", f"{ab.intervention_rate_pct}%",
              "reports with validator flag",
              "#FFA500" if ab.intervention_rate_pct > 0 else "var(--on-surface-variant)")
    _kpi_card(c3, "Self-Correction Loops", str(len(ab.retry_events)),
              "Layer 4 retries triggered",
              "#00B4D8" if ab.retry_events else "var(--on-surface-variant)")
    _kpi_card(c4, "Avg Citation Rate", f"{ab.avg_citation_rate_pct:.0f}%",
              "paragraphs with source link (Layer 1)")

    st.write("")

    # ── Summary bullets ────────────────────────────────────────────
    if ab.summary_bullets:
        _section("Key Findings")
        for bullet in ab.summary_bullets:
            st.markdown(f"- {bullet}")

    # ── Validation status distribution ────────────────────────────
    _section("Validation Status Distribution (all reports)")
    if ab.status_counts:
        import pandas as pd
        status_rows = []
        for status, count in sorted(ab.status_counts.items()):
            pct = round(count / ab.total_reports_analyzed * 100, 1) if ab.total_reports_analyzed else 0
            status_rows.append({"Status": status, "Count": count, "Share": f"{pct}%"})
        st.dataframe(pd.DataFrame(status_rows), use_container_width=False, hide_index=True)

    # ── Numerical correction table ─────────────────────────────────
    if ab.numerical_comparisons:
        _section("Numerical Claim Correction (Layer 3 + Layer 4)")
        c_before, c_after = st.columns(2)
        c_before.metric(
            "Avg discrepancies per report (before correction)",
            f"{ab.avg_discrepancies_before:.2f}",
        )
        c_after.metric(
            "Avg discrepancies per report (after correction)",
            f"{ab.avg_discrepancies_after:.2f}",
            delta=f"-{ab.discrepancy_reduction_pct:.0f}%",
        )

        st.caption(
            "These numbers are computed by running the deterministic numerical validator "
            "(Layer 3) on both the original first-draft analysis and the corrected final "
            "analysis stored in each report's pipeline state."
        )

        import pandas as pd
        rows = []
        for nc in ab.numerical_comparisons[:20]:  # show at most 20
            rows.append({
                "Report #": nc.report_id,
                "Sector": nc.sector_name,
                "Discrepancies Before": nc.discrepancies_before,
                "Discrepancies After": nc.discrepancies_after,
                "Reduction": nc.discrepancies_before - nc.discrepancies_after,
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Retry event details ────────────────────────────────────────
    if ab.retry_events:
        _section(f"Self-Correction Retry Events ({len(ab.retry_events)} total)")
        for ev in ab.retry_events[:10]:  # show at most 10
            with st.expander(f"Report #{ev.report_id} · {ev.sector_name} · {ev.created_at}"):
                st.markdown(
                    f"**Original draft:** {ev.original_analysis_chars:,} chars &nbsp; → &nbsp; "
                    f"**Corrected draft:** {ev.corrected_analysis_chars:,} chars"
                )
                if ev.issues_found:
                    st.markdown("**Issues the validator flagged:**")
                    for issue in ev.issues_found:
                        st.markdown(f"- {issue}")
                else:
                    st.caption("Issue details not available for this report.")
    elif ab.reports_with_pipeline_state > 0:
        st.info(
            "No self-correction loops were triggered in the scanned reports. "
            "This means the Analyst agent's first drafts passed numerical + reasoning checks. "
            "Increase the scan range or run more analyses to capture retry events."
        )
    else:
        st.info(
            "No pipeline_state JSON found — these reports were saved before full state capture was "
            "implemented. More recent reports will have the full provenance data."
        )


# ═══════════════════════════════════════════════════════════════════
# PAGE ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def render():
    st.markdown(
        '<h1 style="font-family:Manrope,sans-serif;font-size:1.75rem;'
        'font-weight:800;letter-spacing:-0.03em;margin-bottom:0.5rem">'
        '🔬 Evaluation</h1>',
        unsafe_allow_html=True,
    )
    st.caption("Empirical measurement of prediction accuracy and anti-hallucination pipeline effectiveness")

    tab_pred, tab_ablation = st.tabs(["Prediction Accuracy", "Ablation Study"])

    with tab_pred:
        _render_prediction_accuracy()

    with tab_ablation:
        _render_ablation()
