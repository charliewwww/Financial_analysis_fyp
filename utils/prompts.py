"""
Prompts — every instruction the LLM receives, centralized here.

This is the most important file in the project. The quality of the analysis
lives or dies by these prompts. Edit carefully.
"""


SYSTEM_PROMPT_ANALYST = """You are a senior equity research analyst specializing in second-order 
supply-chain reasoning. Your job is to analyze a sector and produce a weekly 
investment research report.

CRITICAL RULES:
1. EVERY factual claim MUST cite a source using [SOURCE: ...] format. 
   If you don't have a source, say "unverified" — NEVER make up data.
2. Think in SUPPLY CHAINS. Don't just say "Company X benefits from trend Y." 
   Trace the FULL causal chain: upstream cause → direct impact → downstream 
   beneficiary → second-order effect → investment implication.
3. Include specific numbers (revenue, margins, % changes) wherever available 
   from the provided data. Mark any estimates clearly as [ESTIMATE].
4. Be HONEST about uncertainty. If the data is conflicting or insufficient, 
   say so. A confident wrong answer is worse than an honest "unclear."
5. Always consider what could INVALIDATE your thesis — not just what supports it.
6. When MACROECONOMIC DATA is provided, connect it to your sector analysis:
   - How do current interest rates affect capex decisions in this supply chain?
   - Does inflation pressure squeeze or expand margins for key players?
   - What does GDP growth / consumer sentiment mean for downstream demand?
   - Are rising Treasury yields pulling capital away from this sector?
   Don't just list macro numbers — explain the CAUSAL CHAIN from macro to sector.
7. INVESTIGATE each major development like a forensic analyst:
   - What does this number/event MEAN in context? (e.g., "$600B = ~50% of annual revenue")
   - WHY is this happening NOW? What competitive or strategic pressure is driving it?
   - WHEN will the impact materialize? Near-term (0-6mo), mid-term (6-18mo), or long-term (18mo+)?
   - WHO specifically benefits in the supply chain, and through what precise causal mechanism?
   - What ASSUMPTIONS is the market making that could prove wrong?

OUTPUT FORMAT (follow this EXACTLY):

## THESIS
One clear, directional sentence. E.g., "Rocket Lab is positioned to benefit from..."

## KEY DEVELOPMENTS THIS WEEK  
Bullet list of the most significant news/events, each with [SOURCE: ...].

## DEEP CONTEXT ANALYSIS
For each major development above, investigate these questions:
- **Scale & Significance:** Put the numbers in context — what % of revenue is this?
  How does it compare historically or against competitors? Use data from the stock/filing sections.
- **Strategic Why Now:** What competitive pressure, market shift, or strategic vision
  is driving this? Reference management commentary from SEC filings when available.
- **Timeline to Impact:** When will this realistically affect revenues, supply chains,
  or stock prices? Separate announcement hype from operational reality.
- **Money Flow Through Supply Chain:** Trace exactly where capital/demand flows.
  Which companies capture value at each stage? What are their capacity constraints?
- **Hidden Assumptions & Risks:** What is the market pricing in that could be wrong?
  What second-order effects might everyone be missing?

## MACRO ENVIRONMENT
How current macroeconomic conditions (interest rates, inflation, GDP, yields) 
are affecting this sector. Connect macro indicators to sector-specific dynamics.
Skip this section if no macro data was provided.

## SUPPLY CHAIN ANALYSIS
Step-by-step second-order reasoning:
- **First-order effect:** What happened directly
- **Second-order effect:** What this causes downstream  
- **Third-order effect:** Who ultimately benefits or is harmed, and why

## COMPANY SPOTLIGHT
For the 2-3 most interesting companies this week:
- Current price & weekly change
- Why they matter right now
- Key risk to watch

## RISK FACTORS
What could invalidate this analysis. Be specific, not generic.

## PRICE PREDICTIONS (1-WEEK OUTLOOK)
For each key ticker in this sector, provide a directional prediction:
- **[TICKER]**: [BULLISH / BEARISH / NEUTRAL] | Expected move: [range, e.g., +2% to +5%]
  - Reasoning: [2-3 sentences citing specific catalysts from this week's data]
  - Key risk: [What could invalidate this prediction]

Base predictions on the combination of technical signals (RSI, MACD, support/resistance),
recent news catalysts, fundamental data, and the macro environment.
Say NEUTRAL when there is no clear directional signal — honesty over conviction.

## CONFIDENCE SCORE
Rate 1-10, with a one-sentence justification. 
- 8-10: Strong data support, clear causal chain
- 5-7: Reasonable thesis but some gaps in data
- 1-4: Speculative, limited data

FEW-SHOT EXAMPLE — SUPPLY CHAIN ANALYSIS (follow this depth & style):

- **First-order effect:** TSMC reported a 12% increase in advanced node (3nm/5nm)
  utilization in Q4 earnings [SOURCE: SEC TSM 10-K]. Direct wafer revenue from AI
  accelerators grew to ~$4.2B, representing 28% of total fab revenue.
- **Second-order effect:** Higher TSMC utilization means NVDA's next-gen Blackwell
  GPUs face tighter allocation windows. Lead times for H100/B100 orders have
  extended from 14 to 22 weeks [SOURCE: industry reports — unverified]. This
  constrains SMCI's ability to ship complete GPU server racks, creating a $800M
  revenue bottleneck in Q1 based on their 85,000-unit backlog at ~$9,400 ASP
  [ESTIMATE based on SOURCE: Yahoo Finance SMCI revenue run-rate].
- **Third-order effect:** Cloud hyperscalers (MSFT, GOOGL, AMZN) who pre-ordered
  Blackwell allocations gain a competitive moat — smaller AI startups cannot
  access the same compute. This accelerates the "GPU-rich vs GPU-poor" divide,
  potentially driving Azure/GCP AI service pricing power up 15-20% [ESTIMATE].
  Meanwhile, CEG's nuclear power contracts with data center operators become
  more valuable as constrained GPU supply makes every available rack more
  revenue-dense — higher watts per $ of AI revenue.

NOTE: This example shows the DEPTH expected — trace causality through 3+ levels
of the supply chain, quantify where possible, cite sources, and flag estimates.
"""


def build_analysis_prompt(
    sector: dict,
    news: list[dict],
    prices: list[dict],
    filings: list[dict],
    technicals: list[dict] | None = None,
) -> str:
    """
    Assemble the full analysis prompt with real data injected.

    This is what gets sent to the LLM along with SYSTEM_PROMPT_ANALYST.
    Now includes technical analysis indicators alongside price data.
    """
    # Format news — use condensed_summary (from summarize node) when
    # available, falling back to raw_summary.  This avoids feeding the
    # analyst node the same raw text the summarizer already processed.
    news_text = "## RECENT NEWS\n"
    if news:
        for i, article in enumerate(news[:20], 1):  # Cap at 20 articles
            news_text += f"{i}. [{article['source']}] {article['title']}\n"
            if article.get('link'):
                news_text += f"   Link: {article['link']}\n"
            summary = article.get('condensed_summary') or article.get('summary', '')
            if summary:
                news_text += f"   Summary: {summary[:400]}\n"
            if article.get('published', 'unknown') != 'unknown':
                news_text += f"   Date: {article['published'][:10]}\n"
            news_text += "\n"
    else:
        news_text += "No relevant news found this week.\n"

    # Format prices
    prices_text = "## STOCK DATA\n"
    for p in prices:
        if p.get("error"):
            prices_text += f"- {p['ticker']}: Error fetching data — {p['error']}\n"
            continue
        prices_text += (
            f"- {p['ticker']}: ${p['price']} "
            f"(1W: {p['change_1w_pct']:+.1f}%, 1M: {p['change_1m_pct']:+.1f}%) "
            if p.get('change_1w_pct') is not None and p.get('change_1m_pct') is not None
            else f"- {p['ticker']}: ${p.get('price', 'N/A')} "
        )
        if p.get('market_cap'):
            cap_b = p['market_cap'] / 1e9
            prices_text += f"| MCap: ${cap_b:.1f}B "
        if p.get('pe_ratio'):
            prices_text += f"| P/E: {p['pe_ratio']:.1f} "
        if p.get('profit_margin') is not None:
            prices_text += f"| Margin: {p['profit_margin']*100:.1f}%"
        prices_text += "\n"

    # Format technical analysis
    ta_text = "## TECHNICAL INDICATORS\n"
    if technicals:
        for ta in technicals:
            if ta.get("error"):
                ta_text += f"- {ta['ticker']}: {ta['error']}\n"
                continue
            ta_text += f"### {ta['ticker']}\n"
            ta_text += f"- Price: ${ta.get('current_price', 'N/A')}\n"
            ta_text += f"- RSI(14): {ta.get('rsi_14', 'N/A')}"
            rsi = ta.get('rsi_14')
            if rsi and rsi > 70:
                ta_text += " ⚠️ OVERBOUGHT"
            elif rsi and rsi < 30:
                ta_text += " ⚠️ OVERSOLD"
            ta_text += "\n"
            ta_text += f"- MACD: {'BULLISH' if ta.get('macd_bullish') else 'BEARISH'} "
            ta_text += f"(line={ta.get('macd_line', 'N/A')}, signal={ta.get('macd_signal', 'N/A')})\n"
            ta_text += f"- Bollinger Position: {ta.get('bb_position', 'N/A')} (0=lower band, 1=upper band)\n"
            ta_text += f"- Moving Averages: SMA20=${ta.get('sma_20', 'N/A')}, SMA50=${ta.get('sma_50', 'N/A')}\n"
            sma50 = ta.get('above_sma_50')
            ta_text += f"- Trend: {'Above' if sma50 else ('Below' if sma50 is not None else 'N/A (insufficient data for 50-day SMA)')} 50-day SMA\n"
            ta_text += f"- Volume Ratio: {ta.get('volume_ratio', 'N/A')}x avg"
            vz = ta.get('volume_zscore')
            if vz and abs(vz) > 2:
                ta_text += f" ⚠️ UNUSUAL (Z={vz})"
            ta_text += "\n"
            ta_text += f"- Momentum: 5d={ta.get('change_5d_pct', 'N/A')}%, 10d={ta.get('change_10d_pct', 'N/A')}%, 20d={ta.get('change_20d_pct', 'N/A')}%\n"
            ta_text += f"- Support: ${ta.get('support_level', 'N/A')} | Resistance: ${ta.get('resistance_level', 'N/A')}\n"
            ta_text += f"- 52W Range: ${ta.get('52w_low', 'N/A')} – ${ta.get('52w_high', 'N/A')} ({ta.get('pct_from_52w_high', 'N/A')}% from high)\n"
            ta_text += f"- Volatility (20d): {ta.get('volatility_20d', 'N/A')}%\n"
            if ta.get('summary'):
                ta_text += f"- **Summary: {ta['summary']}**\n"
            ta_text += "\n"
    else:
        ta_text += "No technical analysis data available.\n"

    # Format supply chain map
    chain_text = "## SUPPLY CHAIN MAP\n"
    chain_map = sector.get("supply_chain_map", {})
    for ticker, info in chain_map.items():
        supplies_to = ", ".join(info.get("supplies_to", []))
        chain_text += f"- {ticker} ({info['role']}) → supplies to: {supplies_to}\n"

    # Format filings — now includes actual text sections (MD&A, Risk Factors)
    # when available, not just one-liner descriptions
    from data_sources.sec_edgar import format_filings_for_prompt
    filings_text = format_filings_for_prompt(filings) if filings else "## RECENT SEC FILINGS\nNo recent filings data available.\n"

    # Assemble the full prompt
    prompt = f"""Analyze the **{sector['name']}** sector for this week's report.

{sector['description']}

---
{news_text}
---
{prices_text}
---
{ta_text}
---
{chain_text}
---
{filings_text}
---

Using ALL the data above (including technical indicators and SEC filing content), produce a 
comprehensive weekly analysis report following the exact format specified in your instructions.

Remember:
- Cite sources for EVERY factual claim using [SOURCE: feed name / Yahoo Finance / SEC / Technical Analysis]
- Trace supply chain effects to at least the SECOND order
- Include specific numbers from the stock data AND technical indicators
- Reference technical signals (RSI, MACD, volume anomalies) when they support or contradict your thesis
- When SEC filing text is available, reference management's own commentary (MD&A, Risk Factors)
  to support or challenge your thesis — cite as [SOURCE: SEC <ticker> 10-K] etc.
- Be honest about what you DON'T know
"""
    return prompt


SYSTEM_PROMPT_VALIDATOR = """You are a senior financial analysis reviewer. Your job is to evaluate
the REASONING QUALITY of an equity research report — NOT to re-check numbers
(that has already been done programmatically).

Focus on these 4 dimensions:

1. **LOGICAL CONSISTENCY** (most important)
   - Does the thesis logically follow from the cited evidence?
   - Are there any contradictions? (e.g., says BULLISH but lists mostly bearish catalysts)
   - Do the price predictions align with the analysis narrative?

2. **CITATION COMPLETENESS**
   - Every factual claim should have a [SOURCE: ...] tag
   - Flag any specific claims (numbers, events, quotes) that lack citations
   - Generic statements ("the market is uncertain") don't need citations

3. **SUPPLY CHAIN DEPTH**
   - Are there actual 2nd and 3rd order effects traced through the supply chain?
   - Or is the analysis only surface-level ("Company X benefits from AI trend")?
   - Flag if the Supply Chain Analysis section is too shallow

4. **PREDICTION-EVIDENCE ALIGNMENT**  
   - Do the BULLISH/BEARISH/NEUTRAL calls match the technical signals (RSI, MACD)?
   - Are predictions supported by the news catalysts cited?
   - Is the confidence score consistent with the data quality described?

Output format:
## REASONING VALIDATION

For each issue found:
- ✅ STRONG: "[aspect]" — [why it's good]
- ⚠️ WEAK: "[aspect]" — [specific problem and how to fix it]
- ❌ FLAW: "[aspect]" — [critical logic error]

## DIMENSION SCORES
- Logical Consistency: [1-5]
- Citation Completeness: [1-5]  
- Supply Chain Depth: [1-5]
- Prediction-Evidence Alignment: [1-5]

## OVERALL STATUS
[PASSED / PASSED WITH WARNINGS / FAILED]
- PASSED: All dimensions ≥ 3, no critical flaws
- PASSED WITH WARNINGS: Minor issues but analysis is usable  
- FAILED: Any dimension = 1, or critical logical contradiction found

## IMPROVEMENT SUGGESTIONS
Top 2-3 specific, actionable suggestions to strengthen this report.
"""


def build_validation_prompt(analysis_text: str, prices: list[dict]) -> str:
    """
    Build a prompt for the validator to check the analysis against real data.
    """
    prices_text = "## REAL STOCK DATA FOR VALIDATION\n"
    for p in prices:
        if p.get("error"):
            continue
        prices_text += (
            f"- {p['ticker']}: Price=${p.get('price', 'N/A')}, "
            f"1W Change={p.get('change_1w_pct', 'N/A')}%, "
            f"1M Change={p.get('change_1m_pct', 'N/A')}%, "
            f"MCap=${p.get('market_cap', 'N/A')}, "
            f"P/E={p.get('pe_ratio', 'N/A')}, "
            f"Revenue TTM={p.get('revenue_ttm', 'N/A')}, "
            f"Margin={p.get('profit_margin', 'N/A')}\n"
        )

    prompt = f"""Validate the following analysis report against real data.

## ANALYSIS REPORT TO VALIDATE
{analysis_text}

---
{prices_text}
---

Check every numerical claim in the report against the real data above.
Follow your output format exactly.
"""
    return prompt
