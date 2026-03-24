"""
Anomaly Detection — flag unusual market signals from technical data.

Scans technicals for Z-score volume spikes, extreme RSI, unusual price
moves, and Bollinger Band breakouts. These alerts are injected into the
analysis prompt so the LLM pays special attention to them.

This is deterministic — no LLM involved. Pure math on the technicals dict.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Thresholds ───────────────────────────────────────────────────

VOLUME_ZSCORE_THRESHOLD = 2.0   # Z > 2 → unusual volume
RSI_OVERBOUGHT = 70             # RSI > 70 → overbought
RSI_OVERSOLD = 30               # RSI < 30 → oversold
BB_UPPER_THRESHOLD = 0.95       # Bollinger position > 0.95 → at upper band
BB_LOWER_THRESHOLD = 0.05       # Bollinger position < 0.05 → at lower band
PRICE_MOVE_THRESHOLD = 5.0      # |5-day change| > 5% → big move


@dataclass
class Anomaly:
    """A single detected anomaly."""
    ticker: str
    signal_type: str        # "volume_spike" | "rsi_extreme" | "bollinger_breakout" | "price_move"
    severity: str           # "high" | "medium" | "low"
    description: str        # Human-readable explanation
    value: float | None = None
    threshold: float | None = None


@dataclass
class AnomalyReport:
    """Collection of all detected anomalies for a sector."""
    anomalies: list[Anomaly] = field(default_factory=list)

    @property
    def high_count(self) -> int:
        return sum(1 for a in self.anomalies if a.severity == "high")

    @property
    def has_anomalies(self) -> bool:
        return len(self.anomalies) > 0

    def format_for_prompt(self, max_alerts: int = 10) -> str:
        """Format anomalies as text to inject into the LLM prompt."""
        if not self.anomalies:
            return ""

        lines = ["## ⚡ ANOMALY ALERTS (auto-detected from technical data)\n"]
        lines.append("Pay special attention to these unusual signals:\n")

        for a in sorted(self.anomalies, key=lambda x: {"high": 0, "medium": 1, "low": 2}[x.severity])[:max_alerts]:
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}[a.severity]
            lines.append(f"- {icon} **{a.ticker}** [{a.signal_type}]: {a.description}")

        lines.append("")
        return "\n".join(lines)

    def to_dict_list(self) -> list[dict]:
        """Serialize for storage in PipelineState."""
        return [
            {
                "ticker": a.ticker,
                "signal_type": a.signal_type,
                "severity": a.severity,
                "description": a.description,
                "value": a.value,
                "threshold": a.threshold,
            }
            for a in self.anomalies
        ]


def detect_anomalies(technicals: list[dict]) -> AnomalyReport:
    """
    Scan all technicals for anomalies.

    Args:
        technicals: List of technical indicator dicts from compute_sector_technicals()

    Returns:
        AnomalyReport with all detected anomalies.
    """
    report = AnomalyReport()

    for ta in technicals:
        if ta.get("error"):
            continue

        ticker = ta.get("ticker", "UNKNOWN")

        # ── Volume spike ────────────────────────────────────
        vz = ta.get("volume_zscore")
        if vz is not None and abs(vz) > VOLUME_ZSCORE_THRESHOLD:
            severity = "high" if abs(vz) > 3.0 else "medium"
            direction = "spike" if vz > 0 else "drought"
            report.anomalies.append(Anomaly(
                ticker=ticker,
                signal_type="volume_spike",
                severity=severity,
                description=f"Volume {direction} (Z-score={vz:.1f}, threshold=±{VOLUME_ZSCORE_THRESHOLD}). "
                            f"Latest volume vs 20-day avg ratio: {ta.get('volume_ratio', 'N/A')}x",
                value=vz,
                threshold=VOLUME_ZSCORE_THRESHOLD,
            ))

        # ── RSI extreme ─────────────────────────────────────
        rsi = ta.get("rsi_14")
        if rsi is not None:
            if rsi > RSI_OVERBOUGHT:
                report.anomalies.append(Anomaly(
                    ticker=ticker,
                    signal_type="rsi_extreme",
                    severity="medium" if rsi < 80 else "high",
                    description=f"RSI={rsi:.1f} — OVERBOUGHT (>{RSI_OVERBOUGHT}). "
                                f"Potential reversal or momentum exhaustion.",
                    value=rsi,
                    threshold=RSI_OVERBOUGHT,
                ))
            elif rsi < RSI_OVERSOLD:
                report.anomalies.append(Anomaly(
                    ticker=ticker,
                    signal_type="rsi_extreme",
                    severity="medium" if rsi > 20 else "high",
                    description=f"RSI={rsi:.1f} — OVERSOLD (<{RSI_OVERSOLD}). "
                                f"Potential bounce or continued weakness.",
                    value=rsi,
                    threshold=RSI_OVERSOLD,
                ))

        # ── Bollinger Band breakout ─────────────────────────
        bb_pos = ta.get("bb_position")
        if bb_pos is not None:
            if bb_pos > BB_UPPER_THRESHOLD:
                report.anomalies.append(Anomaly(
                    ticker=ticker,
                    signal_type="bollinger_breakout",
                    severity="medium",
                    description=f"Trading at upper Bollinger Band (position={bb_pos:.2f}). "
                                f"Price may be overextended.",
                    value=bb_pos,
                    threshold=BB_UPPER_THRESHOLD,
                ))
            elif bb_pos < BB_LOWER_THRESHOLD:
                report.anomalies.append(Anomaly(
                    ticker=ticker,
                    signal_type="bollinger_breakout",
                    severity="medium",
                    description=f"Trading at lower Bollinger Band (position={bb_pos:.2f}). "
                                f"Price may be oversold or in freefall.",
                    value=bb_pos,
                    threshold=BB_LOWER_THRESHOLD,
                ))

        # ── Large price move ────────────────────────────────
        change_5d = ta.get("change_5d_pct")
        if change_5d is not None and abs(change_5d) > PRICE_MOVE_THRESHOLD:
            direction = "surge" if change_5d > 0 else "drop"
            report.anomalies.append(Anomaly(
                ticker=ticker,
                signal_type="price_move",
                severity="high" if abs(change_5d) > 10.0 else "medium",
                description=f"5-day {direction} of {change_5d:+.1f}% (threshold=±{PRICE_MOVE_THRESHOLD}%). "
                            f"Investigate catalyst (earnings, news, sector rotation).",
                value=change_5d,
                threshold=PRICE_MOVE_THRESHOLD,
            ))

    if report.has_anomalies:
        logger.info("Detected %d anomalies (%d high severity)",
                    len(report.anomalies), report.high_count)
    else:
        logger.info("No anomalies detected in technicals")

    return report
