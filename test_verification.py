"""
Verification Test — checks all fixes before live run.

Tests:
1. Database schema (new columns exist)
2. save_report() accepts all new parameters
3. Technical analysis module works
4. Keyword matching (no false positives)
5. Sector keywords pull news (especially Optical)
6. Objective confidence scoring
7. Analyst accepts technicals parameter
8. Prompts format technicals correctly
"""

import sys
import json

def run_all():
    results = []

    # ── Test 1: Database schema ────────────────────────────────────
    print("\n🔍 Test 1: Database schema...")
    try:
        from database.reports_db import _get_conn
        conn = _get_conn()
        cursor = conn.execute("PRAGMA table_info(reports)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        required = {"technicals_snapshot", "news_snapshot", "filings_snapshot", "timing_snapshot"}
        missing = required - columns
        if missing:
            print(f"   ❌ Missing columns: {missing}")
            results.append(("DB Schema", False, f"Missing: {missing}"))
        else:
            print(f"   ✅ All new columns present: {required}")
            results.append(("DB Schema", True, ""))
    except Exception as e:
        print(f"   ❌ {e}")
        results.append(("DB Schema", False, str(e)))

    # ── Test 2: save_report() with all params ──────────────────────
    print("\n🔍 Test 2: save_report() with all parameters...")
    try:
        from database.reports_db import save_report, get_report_by_id
        report_id = save_report(
            sector_id="test_sector",
            sector_name="Test Sector",
            analysis="Test analysis content",
            validation="PASSED",
            prices=[{"ticker": "TEST", "price": 100.0, "change_1w_pct": 1.5}],
            news_count=5,
            confidence_score=7.5,
            technicals=[{"ticker": "TEST", "rsi_14": 55.3, "macd_bullish": True}],
            news_articles=[{"title": "Test Article", "source": "Test Feed", "summary": "Test"}],
            filings=[{"ticker": "TEST", "type": "10-K", "date": "2025-02-10", "description": "Annual"}],
            timing={"total_seconds": 45.2, "steps": [{"name": "Test Step", "seconds": 10.0}]},
        )

        # Verify it was stored correctly
        report = get_report_by_id(report_id)
        ta_stored = json.loads(report["technicals_snapshot"])
        news_stored = json.loads(report["news_snapshot"])
        filings_stored = json.loads(report["filings_snapshot"])
        timing_stored = json.loads(report["timing_snapshot"])

        assert ta_stored[0]["rsi_14"] == 55.3, "Technicals not stored correctly"
        assert news_stored[0]["title"] == "Test Article", "News not stored correctly"
        assert filings_stored[0]["type"] == "10-K", "Filings not stored correctly"
        assert timing_stored["total_seconds"] == 45.2, "Timing not stored correctly"

        print(f"   ✅ Report #{report_id} saved with ALL raw data")
        results.append(("save_report()", True, ""))
    except Exception as e:
        print(f"   ❌ {e}")
        results.append(("save_report()", False, str(e)))

    # ── Test 3: Technical analysis module ──────────────────────────
    print("\n🔍 Test 3: Technical analysis (NVDA)...")
    try:
        from data_sources.technical_analysis import compute_technicals
        ta = compute_technicals("NVDA")
        if ta.get("error"):
            print(f"   ❌ {ta['error']}")
            results.append(("Technical Analysis", False, ta["error"]))
        else:
            indicators = ["rsi_14", "macd_line", "bb_position", "sma_20", "volume_ratio", "support_level"]
            present = [k for k in indicators if ta.get(k) is not None]
            missing = [k for k in indicators if ta.get(k) is None]
            print(f"   ✅ Got {len(present)}/{len(indicators)} key indicators")
            print(f"      RSI={ta['rsi_14']}, MACD={'BULL' if ta.get('macd_bullish') else 'BEAR'}, "
                  f"Vol Z={ta.get('volume_zscore')}")
            print(f"      Summary: {ta.get('summary', 'N/A')}")
            if missing:
                print(f"      ⚠ Missing: {missing}")
            results.append(("Technical Analysis", True, f"{len(present)}/{len(indicators)} indicators"))
    except Exception as e:
        print(f"   ❌ {e}")
        results.append(("Technical Analysis", False, str(e)))

    # ── Test 4: Keyword matching (no false positives) ──────────────
    print("\n🔍 Test 4: Keyword false-positive check...")
    try:
        from data_sources.rss_fetcher import _is_relevant

        # Should NOT match (false positive test)
        false_articles = [
            {"title": "Apple launches new iPhone", "summary": "Consumer electronics"},
            {"title": "Tesla launches Model Y in Europe", "summary": "EV market"},
            {"title": "Netflix launch party for new series", "summary": "Entertainment"},
        ]
        from config.sectors import SECTORS
        space_kw = SECTORS["space_rockets"]["keywords"]
        space_tickers = SECTORS["space_rockets"]["tickers"]

        false_positives = []
        for article in false_articles:
            if _is_relevant(article, space_kw, space_tickers):
                false_positives.append(article["title"])

        if false_positives:
            print(f"   ❌ False positives detected: {false_positives}")
            results.append(("Keyword Matching", False, f"FP: {false_positives}"))
        else:
            print(f"   ✅ No false positives (0/{len(false_articles)} false articles matched)")
            results.append(("Keyword Matching", True, ""))

        # Should MATCH (true positive test)
        true_articles = [
            {"title": "Rocket Lab launches Electron rocket from New Zealand", "summary": "Space launch"},
            {"title": "SpaceX Starlink satellite constellation expansion", "summary": "LEO orbit deployment"},
        ]
        true_positives = []
        for article in true_articles:
            if _is_relevant(article, space_kw, space_tickers):
                true_positives.append(article["title"])
        print(f"   ✅ True positives: {len(true_positives)}/{len(true_articles)} matched")

    except Exception as e:
        print(f"   ❌ {e}")
        results.append(("Keyword Matching", False, str(e)))

    # ── Test 5: RSS news for all sectors ───────────────────────────
    print("\n🔍 Test 5: RSS news fetch for all sectors...")
    try:
        from data_sources.rss_fetcher import fetch_news_for_sector
        from config.sectors import SECTORS

        for sid, sector in SECTORS.items():
            news = fetch_news_for_sector(sector)
            status = "✅" if len(news) > 0 else "⚠️"
            print(f"   {status} {sector['name']}: {len(news)} articles")
            results.append((f"RSS-{sid}", len(news) > 0, f"{len(news)} articles"))
    except Exception as e:
        print(f"   ❌ {e}")
        results.append(("RSS Fetch", False, str(e)))

    # ── Test 6: Objective confidence scoring ───────────────────────
    print("\n🔍 Test 6: Objective confidence scoring...")
    try:
        from workflows.weekly_analysis import _compute_objective_confidence

        # Scenario A: Excellent data
        score_a = _compute_objective_confidence(
            news=[{"title": f"Article {i}"} for i in range(10)],  # 9+ articles = 3 pts
            prices=[{"ticker": "A", "price": 100}] * 5,  # 100% valid = 2 pts
            technicals=[{"ticker": "A", "rsi_14": 50}] * 5,  # 100% valid = 2 pts
            filings=[{"type": "10-K"}],  # Has filings = 1 pt
            validation="PASSED",  # Passed = 2 pts
        )

        # Scenario B: Poor data
        score_b = _compute_objective_confidence(
            news=[],  # 0 articles = 0 pts
            prices=[{"ticker": "A", "error": "failed"}] * 5,  # 0% valid = 0 pts
            technicals=[],  # Empty = 0 pts
            filings=[],  # No filings = 0 pts
            validation="FAILED",  # Failed = 0 pts
        )

        print(f"   Excellent data scenario: {score_a}/10")
        print(f"   Poor data scenario:      {score_b}/10")

        if score_a >= 8 and score_b <= 2:
            print(f"   ✅ Scoring range is reasonable")
            results.append(("Confidence Scoring", True, f"Range: {score_b}-{score_a}"))
        else:
            print(f"   ⚠️ Scoring may need tuning")
            results.append(("Confidence Scoring", False, f"Range: {score_b}-{score_a}"))
    except Exception as e:
        print(f"   ❌ {e}")
        results.append(("Confidence Scoring", False, str(e)))

    # ── Test 7: Prompt includes technicals ─────────────────────────
    print("\n🔍 Test 7: Prompt includes technical analysis data...")
    try:
        from utils.prompts import build_analysis_prompt
        from config.sectors import SECTORS

        sector = SECTORS["ai_semiconductors"]
        technicals = [{"ticker": "NVDA", "rsi_14": 62.5, "macd_bullish": True,
                       "current_price": 190.0, "sma_20": 185.0, "sma_50": 170.0,
                       "bb_position": 0.7, "volume_ratio": 1.3, "volume_zscore": 0.5,
                       "change_5d_pct": 2.1, "change_10d_pct": 5.3, "change_20d_pct": 8.1,
                       "support_level": 175.0, "resistance_level": 195.0,
                       "52w_high": 200.0, "52w_low": 100.0, "pct_from_52w_high": -5.0,
                       "volatility_20d": 2.5, "macd_line": 1.5, "macd_signal": 1.2,
                       "above_sma_50": True, "summary": "RSI=62.5 | MACD: BULLISH"}]

        prompt = build_analysis_prompt(
            sector, news=[], prices=[], filings=[], technicals=technicals
        )

        checks = ["TECHNICAL INDICATORS", "RSI(14)", "MACD", "Bollinger", "SMA20", "Volume Ratio"]
        found = [c for c in checks if c in prompt]
        missing = [c for c in checks if c not in prompt]

        if len(found) >= 4:
            print(f"   ✅ Prompt contains {len(found)}/{len(checks)} expected sections")
            results.append(("Prompt Technicals", True, ""))
        else:
            print(f"   ⚠️ Missing from prompt: {missing}")
            results.append(("Prompt Technicals", False, f"Missing: {missing}"))
    except Exception as e:
        print(f"   ❌ {e}")
        results.append(("Prompt Technicals", False, str(e)))

    # ── Test 8: Analyst function signature ─────────────────────────
    print("\n🔍 Test 8: Analyst accepts technicals parameter...")
    try:
        import inspect
        from agents.analyst import analyze_sector
        sig = inspect.signature(analyze_sector)
        params = list(sig.parameters.keys())
        if "technicals" in params:
            print(f"   ✅ analyze_sector() has 'technicals' parameter")
            results.append(("Analyst Signature", True, ""))
        else:
            print(f"   ❌ 'technicals' not in params: {params}")
            results.append(("Analyst Signature", False, f"Params: {params}"))
    except Exception as e:
        print(f"   ❌ {e}")
        results.append(("Analyst Signature", False, str(e)))

    # ── Summary ────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  VERIFICATION SUMMARY")
    print(f"{'='*60}")
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)

    for name, ok, detail in results:
        icon = "✅" if ok else "❌"
        suffix = f" — {detail}" if detail else ""
        print(f"  {icon} {name}{suffix}")

    print(f"\n  {passed} passed, {failed} failed out of {len(results)} tests")
    print(f"{'='*60}\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
