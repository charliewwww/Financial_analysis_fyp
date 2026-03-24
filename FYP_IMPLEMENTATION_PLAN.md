# FYP Implementation Plan: Multi-Agentic Workflow for Live Financial News

> **Author:** Wong Tsz Hei Charlie (57141182)
> **Date:** February 2026
> **Design Principles:** Low Cost · Best Analysis · Low Hallucination

---

## Why This Project — And Not Existing Open-Source Alternatives?

Several open-source financial AI projects already exist. Below is a comparison of the most prominent ones and **why none of them solve the specific problem this FYP addresses:**

| Project | Stars | What It Does | What It **Doesn't** Do |
|---|---|---|---|
| **FinGPT** (AI4Finance) | ~18.5k | Fine-tunes LLMs on financial data for sentiment analysis, robo-advising, and quantitative trading | ❌ No multi-agent workflow — single-model, single-pass inference. No self-correction or validation loop. No second-order supply-chain reasoning. Requires cloud GPU fine-tuning (expensive). |
| **FinRobot** (AI4Finance) | ~6k | Multi-agent platform with market forecasting, document analysis, and trade strategies | ❌ Relies on OpenAI API calls ($$$). No anomaly-triggered event workflow. No structured chain-of-thought with source citations. No anti-hallucination validation layer. No supply-chain reasoning. |
| **FinRL** (AI4Finance) | ~13.8k | Reinforcement learning for automated trading (portfolio optimization, market simulation) | ❌ Completely different approach — RL-based, not LLM reasoning. No news analysis, no NLP, no explainability. Black-box decisions; cannot explain "why." |
| **CrewAI / AutoGen** (general) | Various | General-purpose multi-agent frameworks | ❌ Not domain-specific. No financial data connectors, no supply-chain reasoning templates, no anti-hallucination pipeline. Requires significant custom engineering to apply to finance. |
| **Bloomberg GPT** (closed) | N/A | Finance-tuned 50B parameter LLM | ❌ Completely proprietary and inaccessible. Requires Bloomberg Terminal ($24k/year). Not agentic — single-model, no workflow. |

### The Gap This Project Fills

This FYP is **not** another "ChatGPT for stocks." It addresses five specific gaps that no existing project covers simultaneously:

1. **Second-Order Supply-Chain Reasoning** — Existing tools react to *direct* news ("Nvidia launched a chip → Nvidia stock goes up"). This project performs *multi-hop causal reasoning* ("AI boom → more chatbot usage → higher energy consumption → benefit to 24/7 energy providers like Constellation Energy"). No open-source project does this.

2. **Event-Driven Anomaly Detection + Explainable Alpha** — When a stock suddenly moves ±5% without obvious news, existing tools offer no explanation. This project auto-triggers a deep RAG analysis to explain *why*, pulling from SEC filings, macro data, and peer comparisons. FinGPT/FinRobot have no equivalent.

3. **Self-Correcting Anti-Hallucination Pipeline** — LLM hallucination is the #1 barrier to using AI in high-stakes finance. This project implements a 5-layer defense (source grounding → RAG validation → numerical cross-check → self-correction loop → confidence scoring). No open-source financial AI project has a comparable validation architecture.

4. **Fully Local & Free** — FinRobot requires OpenAI API calls. FinGPT requires cloud GPU fine-tuning. Bloomberg GPT costs $24k/year. This project runs entirely on a local RTX 5070 Ti with GLM-4.7-Flash via Ollama and free-tier APIs. During development, the same model is accessed via OpenRouter's free API for convenience and speed — but the production deployment is fully local. **Total cost: $0/month.**

5. **Structured, Auditable Output** — Every analysis follows a rigid format (Thesis → Evidence with citations → Chain of Thought → Risk Factors → Confidence Score → Validation Status). This makes outputs *auditable* and *benchmarkable*, unlike the free-text responses of existing tools.

### In Short

| Dimension | FinGPT | FinRobot | FinRL | **This Project** |
|---|---|---|---|---|
| Multi-agent workflow | ❌ | ✅ | ❌ | ✅ |
| Second-order reasoning | ❌ | ❌ | ❌ | ✅ |
| Anomaly-triggered analysis | ❌ | ❌ | ❌ | ✅ |
| Anti-hallucination validation | ❌ | ❌ | N/A | ✅ (5-layer) |
| Runs fully local (free) | ❌ | ❌ | ✅ | ✅ |
| Explainable + auditable output | ❌ | Partial | ❌ | ✅ |
| Supply-chain reasoning | ❌ | ❌ | ❌ | ✅ |
| Live news + filing ingestion | Partial | Partial | ❌ | ✅ (9 categories) |

---

## Why This Project Matters *Now* (February 2026)

### 1. 2026 Is the Most Complex Financial Era in Modern History

The convergence of multiple unprecedented forces makes traditional analysis tools fundamentally inadequate:

- **AI Spending Bubble Uncertainty** — By early 2026, investors are debating whether AI capex (led by Microsoft, Google, Meta, and Amazon spending $200B+ collectively) will yield returns or become the next dot-com bust. CNBC reports the "AI market is splintering" as investors scrutinize who is spending wisely vs. recklessly. A system that can perform *second-order reasoning* on AI supply chains is no longer a luxury — it's a necessity.

- **Heightened Market Volatility** — 2026 has seen extreme sector rotation, with AI stocks, energy, and defense swinging wildly on policy news. Forbes describes 2026 as shaped by "the continuing momentum of AI, heightened volatility driven by market flows, and ongoing geopolitical tensions." Human analysts cannot keep up with the speed and complexity.

- **Geopolitical Supply-Chain Disruption** — Ongoing US-China tech sanctions, shifting trade tariffs, and energy policy changes create cascading second-order effects that are invisible to first-order analysis tools. When a tariff changes on rare earth minerals, the impact ripples through semiconductors → data centers → AI companies → energy providers. No existing tool traces this chain.

### 2. The "Reasoning Gap" Is Widening

- Retail investors now have access to raw information (news, filings, data) via free tools, but **the gap between *information* and *insight* is growing**. Most AI tools provide "Nvidia stock rose because they launched a chip" — a first-order observation anyone can see. What investors *need* is "Nvidia's new chip will increase power consumption by 40% per data center, which benefits Constellation Energy, whose nuclear plants provide 24/7 baseload power, and their PPA contracts lock in revenue for 10+ years." This is the "Reasoning Gap" your FYP aims to bridge.

- According to the SSRN survey "A Review of LLM Agent Applications in Finance and Banking" (2025), the field has established four core agent functions: **simulation, acting, analysis, and advising**. However, the survey highlights that *safe and effective* deployment remains a key challenge — particularly around hallucination and explainability. Your project directly addresses both.

### 3. AI Hallucination in Finance Is a Critical Unsolved Problem

- In 2025–2026, multiple high-profile cases of AI-generated financial misinformation have eroded trust. AI tools that fabricate earnings numbers, cite non-existent SEC filings, or invent analyst opinions pose real financial risk to users who act on them.

- **No existing open-source project treats hallucination as a first-class architectural concern.** FinGPT and FinRobot generate outputs without validation. Your project's 5-layer anti-hallucination pipeline (with RAG grounding, numerical cross-checks, and self-correction loops) positions it as a pioneering contribution to *trustworthy* financial AI.

### 4. Local LLMs Have Finally Reached "Good Enough" Quality

- As recently as 2024, running a capable reasoning model locally was impractical. But by early 2026:
  - **GLM-4.7-Flash** (ZhipuAI) delivers strong reasoning quality for structured analytical tasks — and is available both as a free OpenRouter API model and as a free Ollama pull for fully local inference
  - **RTX 5070 Ti (16GB VRAM)** can run GLM-4.7-Flash locally at practical speeds via Ollama
  - **Ollama** has matured into a production-ready local inference server
  - **Dual-mode architecture**: OpenRouter API during development (faster iteration), Ollama for production deployment (zero cost, full privacy) — same model, same API format, one config toggle
- This means the "low cost" constraint is *newly achievable*. A year ago, this project would have required $100+/month in API costs. Today, it can run for $0/month — making it feasible as a student FYP.

### 5. Regulatory Tailwinds Demand Explainability

- Financial regulators globally (SEC, MAS, FCA) are increasingly scrutinizing AI-driven investment advice. The trend is toward requiring **explainable, auditable AI decisions**. Your project's structured output format (Thesis → Evidence → CoT → Risk → Confidence → Validation) is inherently audit-friendly — positioning it ahead of regulatory requirements.

### The Timing Argument, Summarized

```
                    2024                    2025                    2026
                      │                       │                       │
  Local LLMs:    Too weak ──────────► Viable ──────────► Production-ready
  Market:        Stable-ish ─────────► Volatile ─────────► Extremely complex
  AI Spend:      Growing ───────────► Booming ──────────► "Bubble or not?"
  Hallucination: Ignored ───────────► Recognized ────────► Critical concern
  Regulation:    Lagging ───────────► Drafting ──────────► Enforcing
                                                              │
                                                     ╔════════╧════════╗
                                                     ║ YOUR FYP LANDS  ║
                                                     ║    RIGHT HERE   ║
                                                     ╚═════════════════╝
```

> **Bottom line:** The combination of (1) newly capable local LLMs, (2) unprecedented market complexity requiring second-order reasoning, (3) an unsolved hallucination problem, and (4) regulatory pressure for explainability creates a **unique window of opportunity** that makes this project both *timely* and *necessary*. A year earlier it wasn't technically feasible; a year later it will be table stakes.

---

## Refined Master Prompt (For LLM Use)

Below is a production-ready prompt you can feed to any LLM to get it to fully understand your project. It embeds rich context, constraints, and structure following LLM best practices (role-setting, explicit constraints, chain-of-thought guidance, and output format specification):

```
You are a senior quantitative research engineer designing a production-grade, 
multi-agentic financial analysis system. Your task is to help architect and 
implement the following system according to these hard constraints:

SYSTEM OVERVIEW:
A LangGraph-based multi-agent workflow that:
1. Periodically fetches live financial news and SEC filings for user-defined sectors
2. Performs second-order supply-chain reasoning (e.g., "AI boom → more chatbot 
   usage → higher energy consumption → benefit to 24/7 energy providers")
3. Detects market anomalies (Z-score > 2, unusual volume) and auto-triggers 
   deep-dive RAG analysis with "Explainable Alpha"
4. Self-validates all reasoning against a vector database of historical data 
   to ensure 100% factual grounding — eliminating hallucinations

THREE HARD CONSTRAINTS (ordered by priority):
1. LOW HALLUCINATION: Every claim must cite a source from the vector DB or 
   a live API. The Critic/Validator agent must cross-reference reasoning 
   against raw SEC filings, FRED macroeconomic data, and peer-company 
   performance before any output is shown to the user.
2. BEST ANALYSIS: Perform multi-hop, second-order causal reasoning using a 
   structured chain-of-thought. Decompose each analysis into: 
   Direct Effect → Downstream Impact → Supply-Chain Beneficiaries → 
   Risk Factors → Confidence Score.
3. LOW COST: Use GLM-4.7-Flash via Ollama (local, RTX 5070 Ti) for all 
   reasoning in production. During development, the same model is accessed 
   via OpenRouter's free API tier for faster iteration. Use free-tier data 
   APIs only (SEC EDGAR, FRED, Yahoo Finance, RSS feeds). The system 
   supports a one-toggle switch between cloud and local inference.

AGENT ARCHITECTURE (LangGraph StateGraph):
- Periodic Workflow: Start → Fetch Source → Summarize → Reflect on Data 
  (loop if insufficient) → Analysis/Reasoning → Validation (loop if flaws) 
  → Store in DB → Generate Report
- Anomaly Workflow: Trigger (Z>2 or volume spike) → Fetch DB Data → 
  Analysis/Reasoning + Alert Users → Validation (loop if flaws) → 
  Simulation → Advise User

DATA CATEGORIES FOR REASONING (detailed in the plan):
- Fundamental Data (10-K/Q, earnings, cash flow, price targets)
- Supply Chain Intelligence (supplier tiers, inventory, defect rates)
- Macroeconomic Data (CPI, interest rates, policy shifts)
- Expert & Sentiment Data (analyst notes, social media, SWOTs)
- Technical & Volume Data (prices, chart patterns, momentum indicators)
- Expert Opinion & Research (earnings call transcripts, research reports)
- Regulatory & Policy Data (government policy changes, trade regulations)
- Alternative/Unconventional Data (patent filings, job postings, web traffic)

When generating analysis, always follow this output format:
1. THESIS: One-sentence directional claim
2. EVIDENCE: Numbered list of data points with source citations
3. CHAIN OF THOUGHT: Step-by-step second-order reasoning
4. RISK FACTORS: What could invalidate this thesis
5. CONFIDENCE: Score from 1-10 with justification
6. VALIDATION STATUS: [PASSED/FAILED] with validator notes
```

---

## PART 1: Complete Essential Data Categories for Analysis/Reasoning

Your project summary lists 5 categories. Below is the **expanded list of 9 data categories** — the original 5 plus 4 additional ones you should incorporate for truly rigorous supply-chain reasoning:

---

### Category 1: Fundamental Data (From Your Summary ✅)
| Data Point | Purpose | Free Source |
|---|---|---|
| 10-K / 10-Q Annual & Quarterly Filings | Ground truth: revenue, margins, risk factors, management discussion | SEC EDGAR API |
| 8-K Current Event Reports | Material events: M&A, leadership changes, restatements | SEC EDGAR API |
| Cash Flow Statements | Assess liquidity, capex trends, free cash flow | SEC EDGAR XBRL |
| Gross / Operating / Net Margins | Profitability trend analysis | FMP Free Tier / Yahoo Finance |
| Price Targets (consensus) | Market expectations benchmark | Finnhub Free Tier |
| Dividend History & Buybacks | Capital return policy signals | Yahoo Finance |

---

### Category 2: Supply Chain Intelligence (From Your Summary ✅)
| Data Point | Purpose | Free Source |
|---|---|---|
| 5–7 Tier Supplier Mapping | Identify hidden vulnerabilities & concentration risk | SEC 10-K "Risk Factors" section (scrape), news cross-reference |
| Inventory Levels (Days Sales of Inventory) | Detect build-up or shortage signals | SEC EDGAR XBRL (computed) |
| Specification Compliance / Defect Rates | Quality trend for manufacturing sectors | SEC filings, FDA databases (for pharma/med-device) |
| Supplier Geographic Concentration | Geopolitical risk exposure | 10-K filings + manual tagging |
| Customer Concentration (top 10% revenue) | Revenue dependency risk | 10-K filings (required disclosure for >10% customers) |

---

### Category 3: Macroeconomic Data (From Your Summary ✅)
| Data Point | Purpose | Free Source |
|---|---|---|
| Interest Rates (Fed Funds, Treasury yields) | Discount rate impact on valuations | FRED API (series: FEDFUNDS, DGS10) |
| CPI / PCE Inflation | Consumer purchasing power, margin pressure | FRED API (series: CPIAUCSL, PCEPI) |
| GDP Growth Rate | Economic expansion/contraction context | FRED API (series: GDP) |
| Unemployment Rate | Consumer spending capacity indicator | FRED API (series: UNRATE) |
| Economic Policy Shifts | Fiscal/monetary regime changes | FRED API + Federal Reserve press releases |
| Natural Resource Prices (Oil, Copper, Lithium) | Input cost for supply-chain reasoning | FRED API / Yahoo Finance commodities |
| PMI (Purchasing Managers' Index) | Leading indicator for manufacturing activity | FRED API (series: MANEMP) / ISM website |
| Housing Starts / Building Permits | Leading economic indicator | FRED API (series: HOUST) |

---

### Category 4: Expert & Sentiment Data (From Your Summary ✅)
| Data Point | Purpose | Free Source |
|---|---|---|
| Analyst Research Notes (summaries) | Market expectations & consensus shifts | Finnhub Free Tier (recommendation trends) |
| Social Media Sentiment (Twitter/X, Reddit) | Retail investor sentiment, crowd wisdom | Reddit API (free), Twitter/X academic API |
| Management Commentary (MD&A sections) | Forward-looking guidance tone analysis | SEC EDGAR 10-K/10-Q Section 7 |
| Former Employee SWOTs | Internal operational quality signals | Glassdoor (scrape with caution), Indeed reviews |
| Short Interest Data | Bearish conviction levels | Finnhub Free Tier |
| Insider Trading (Form 4) | Management conviction signals | SEC EDGAR Form 4 API |
| Options Flow (Put/Call Ratio) | Smart money directional bets | Yahoo Finance / CBOE free data |

---

### Category 5: Technical & Volume Data (From Your Summary ✅)
| Data Point | Purpose | Free Source |
|---|---|---|
| Historical OHLCV Prices | Price trend, pattern recognition | Yahoo Finance (`yfinance` Python lib) |
| Moving Averages (SMA 50/200, EMA) | Trend direction & support/resistance | Computed locally from OHLCV |
| RSI, MACD, Bollinger Bands | Momentum & mean-reversion signals | Computed locally (use `ta` Python lib) |
| Volume Profile & Anomaly Detection | Z-score > 2 triggers for anomaly workflow | Computed locally from volume data |
| Sector Relative Strength | Sector rotation detection | Computed from sector ETF data (Yahoo Finance) |
| Correlation Matrix (cross-asset) | Identify unusual de-correlations | Computed locally |

---

### 🆕 Category 6: Expert Opinion & Professional Research (YOUR ADDITION)
*This is the category you identified as missing — critical for rigorous second-order reasoning.*

| Data Point | Purpose | Free Source |
|---|---|---|
| **Earnings Call Transcripts** | CEO/CFO tone, forward guidance, Q&A reveals hidden risks | **Finnhub Free Tier** (transcripts API), SEC EDGAR 8-K exhibits |
| **Third-Party Research Summaries** | Analyst deep-dives, sector outlooks | **Seeking Alpha** (free articles, RSS), **Motley Fool** (free articles) |
| **Professional Social Context** | Expert discourse, industry insider takes | **LinkedIn** (public posts via RSS), **Substack** financial newsletters |
| **Academic & Institutional Reports** | Peer-reviewed research on sector trends | **SSRN** (free), **NBER Working Papers** (free), **arXiv** (q-fin section) |
| **Central Bank Minutes & Speeches** | Policy direction, "dot plot" analysis | **Federal Reserve** website (free), **ECB** press releases |
| **Congressional & Government Reports** | Policy risk, regulatory direction | **CBO.gov** (free), **GAO.gov** (free), **congress.gov** |
| **Industry Association Reports** | Sector-specific trend data | **SIA**, **AIA**, **NRF** etc. (many publish free executive summaries) |
| **Conference Presentation Decks** | Company strategy reveals at industry events | SEC EDGAR 8-K exhibits (investor presentations) |

---

### 🆕 Category 7: Regulatory & Policy Data
| Data Point | Purpose | Free Source |
|---|---|---|
| FDA Approvals / Clinical Trial Data | Drug pipeline for pharma supply-chain reasoning | **ClinicalTrials.gov** API (free), **FDA openFDA API** |
| Trade Tariff & Sanctions Changes | Import/export cost impact on supply chains | **USITC** (free), **Federal Register** API |
| Environmental Regulations (EPA) | Compliance cost impact for energy/manufacturing | **EPA** public data, **Federal Register** |
| Antitrust / FTC Actions | M&A viability, competitive landscape shifts | **FTC.gov** press releases |
| Patent Grants & Applications | Innovation pipeline, competitive moat signals | **USPTO** bulk data (free) |

---

### 🆕 Category 8: Alternative / Unconventional Data
| Data Point | Purpose | Free Source |
|---|---|---|
| Job Postings Trend (hiring/firing signals) | Expansion vs. contraction proxy | **Indeed/LinkedIn** (scrape public listings) |
| Web Traffic Trends | Consumer demand proxy | **SimilarWeb** (limited free), **Google Trends** API |
| App Download Trends | Product adoption velocity | **Google Trends** (proxy) |
| Satellite / Shipping Data Proxies | Physical activity indicators | **MarineTraffic** (limited free AIS data) |
| Google Search Trends | Public interest & demand signals | **Google Trends** (pytrends library — free) |
| GitHub Activity (for tech companies) | Dev activity as innovation proxy | **GitHub API** (free) |

---

### 🆕 Category 9: Cross-Company & Peer Comparison Data
| Data Point | Purpose | Free Source |
|---|---|---|
| Peer Company Financials | Relative valuation (P/E, EV/EBITDA comps) | Yahoo Finance / FMP Free Tier |
| Sector ETF Holdings & Flows | Money flow into/out of sectors | Yahoo Finance (sector ETFs) |
| M&A Activity in Sector | Consolidation trends, valuation benchmarks | SEC EDGAR (merger proxy filings) |
| Credit Ratings Changes | Default risk signals | SEC EDGAR (8-K filings) |

---

## PART 2: Free News & Data Sources — Complete Mapping

### Tier 1: Official Government / Institutional APIs (Most Reliable — Zero Hallucination Risk)

| Source | What It Provides | API/Access | Rate Limit | Python Library |
|---|---|---|---|---|
| **SEC EDGAR** | 10-K, 10-Q, 8-K, Form 4, 13-F, all filings since 1994 | REST API (free, no key needed) | 10 req/sec | `sec-edgar-downloader`, `edgartools` |
| **FRED (St. Louis Fed)** | 800,000+ macro time series (CPI, GDP, rates, unemployment) | REST API (free key) | 120 req/min | `fredapi` |
| **Federal Reserve** | FOMC minutes, speeches, Beige Book | RSS + web scrape | No limit | `feedparser` + `requests` |
| **ClinicalTrials.gov** | Drug trial data (for pharma supply chains) | REST API (free) | Reasonable | `requests` |
| **USPTO** | Patent data (innovation pipeline) | Bulk download (free) | N/A | `requests` |
| **BLS (Bureau of Labor Statistics)** | Employment, wage, productivity data | REST API (free, key optional) | 500/day | `requests` |

### Tier 2: Financial Data APIs (Free Tier)

| Source | What It Provides | Free Tier Limits | Python Library |
|---|---|---|---|
| **Finnhub** | Real-time quotes, earnings transcripts, company news, analyst recommendations, insider trades | 60 calls/min, most endpoints free | `finnhub-python` |
| **Yahoo Finance** | Historical OHLCV, financials, analyst targets, options chain | Unofficial, no hard limit (be polite) | `yfinance` |
| **Financial Modeling Prep (FMP)** | Fundamentals, ratios, earnings calendar, SEC filings | 250 calls/day (free key) | `requests` |
| **Alpha Vantage** | Intraday/daily prices, technical indicators, fundamentals | 25 calls/day (free key) | `alpha_vantage` |
| **Tiingo** | Clean historical EOD data, IEX real-time, news | 1,000 unique symbols/month (free) | `requests` |
| **Marketaux** | Financial news with sentiment scores | 100 calls/day (free) | `requests` |

### Tier 3: News Sources (RSS Feeds — Completely Free, Unlimited)

| Source | RSS Feed URL | Coverage | Best For |
|---|---|---|---|
| **CNBC** | `https://www.cnbc.com/id/100003114/device/rss/rss.html` (Top News) | US markets, breaking news | Real-time market events |
| **CNBC Business** | `https://www.cnbc.com/id/10001147/device/rss/rss.html` | Business news | Company-specific events |
| **Reuters Business** | `https://www.reutersagency.com/feed/` | Global markets | International coverage |
| **AP News Business** | `https://rsshub.app/apnews/topics/business` | Wire service, factual | Low-bias baseline |
| **Nasdaq News** | `https://www.nasdaq.com/feed/rssoutbound?category=Markets` | Market data, earnings | Earnings & IPOs |
| **Nasdaq Earnings** | `https://www.nasdaq.com/feed/rssoutbound?category=Earnings` | Earnings reports | Earnings triggers |
| **Investor's Business Daily** | `https://www.investors.com/feed` | Growth investing focus | Sector analysis |
| **Seeking Alpha** | `https://seekingalpha.com/market_currents.xml` | Crowd-sourced analysis | Expert opinion |
| **MarketBeat** | `https://www.marketbeat.com/feed` | Analyst ratings, earnings | Consensus tracking |
| **Kiplinger** | `https://www.kiplinger.com/feed/all` | Personal finance, macro | Macro outlook |
| **Naked Capitalism** | `https://www.nakedcapitalism.com/feed` | Critical financial analysis | Contrarian views |
| **Federal Reserve** | `https://www.federalreserve.gov/feeds/press_all.xml` | Fed announcements | Policy analysis |
| **SEC EDGAR RSS** | `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=8-K&dateb=&owner=include&count=40&search_text=&action=getcompany&RSS` | Real-time filings | Filing triggers |

### Tier 4: Sentiment & Social Sources (Free)

| Source | Access Method | What It Provides | Python Library |
|---|---|---|---|
| **Reddit** (r/wallstreetbets, r/stocks, r/investing) | Reddit API (free with app registration) | Retail sentiment, crowd wisdom | `praw` |
| **Google Trends** | Unofficial API | Search interest = demand proxy | `pytrends` |
| **StockTwits** | REST API (free) | Short-form stock sentiment | `requests` |
| **Twitter/X** | API (limited free tier) | Real-time sentiment, breaking news | `tweepy` |

### Tier 5: Academic & Research (Free)

| Source | URL | What It Provides |
|---|---|---|
| **SSRN** | `https://www.ssrn.com` | Pre-print financial research papers |
| **NBER Working Papers** | `https://www.nber.org/papers` | Macro & financial economics research |
| **arXiv (q-fin)** | `https://arxiv.org/list/q-fin/recent` | Quantitative finance papers |
| **Federal Reserve Papers** | `https://www.federalreserve.gov/econres.htm` | Economic research & analysis |
| **IMF Working Papers** | `https://www.imf.org/en/Publications/WP` | Global macro research |
| **World Bank Open Data** | `https://data.worldbank.org` | Global economic indicators |

---

## PART 3: Implementation Architecture

### Tech Stack (All Free / Local)

| Component | Technology | Cost |
|---|---|---|
| **LLM (Reasoning + Summarization)** | GLM-4.7-Flash — dual-mode: Ollama (local, RTX 5070 Ti) for production, OpenRouter API for development | $0 |
| **Agent Framework** | LangGraph (Python) | $0 |
| **Vector Database** | ChromaDB (local) or Qdrant (local Docker) | $0 |
| **Embeddings** | `nomic-embed-text` via Ollama (local) or `all-MiniLM-L6-v2` via sentence-transformers | $0 |
| **Data Fetching** | Python (`requests`, `feedparser`, `yfinance`, `fredapi`) | $0 |
| **Technical Analysis** | `ta` (Technical Analysis library), `pandas`, `numpy` | $0 |
| **Database (Structured)** | SQLite or PostgreSQL (local) | $0 |
| **Scheduling** | `APScheduler` or `cron` | $0 |
| **Frontend (optional)** | Streamlit or Gradio | $0 |

### Recommended Project Structure

```
fyp/
├── agents/
│   ├── __init__.py
│   ├── fetcher.py           # Fetch Source agent (News API, SEC, RSS)
│   ├── summarizer.py        # Summarize raw data into actionable insights
│   ├── reflector.py         # Reflect on data sufficiency (loop if insufficient)
│   ├── analyst.py           # Analysis/Reasoning (second-order CoT)
│   ├── validator.py         # Critic agent — cross-reference with vector DB
│   ├── simulator.py         # Buy/Sell/Hold scenario simulation
│   └── advisor.py           # Generate final user-facing advice
├── data_sources/
│   ├── __init__.py
│   ├── sec_edgar.py         # SEC EDGAR API wrapper
│   ├── fred_macro.py        # FRED macroeconomic data wrapper
│   ├── finnhub_client.py    # Finnhub API wrapper (news, transcripts, recommendations)
│   ├── yahoo_finance.py     # yfinance wrapper (prices, fundamentals)
│   ├── rss_fetcher.py       # RSS feed aggregator (CNBC, Reuters, AP, etc.)
│   ├── reddit_sentiment.py  # Reddit API sentiment fetcher
│   └── google_trends.py     # Google Trends demand signals
├── workflows/
│   ├── __init__.py
│   ├── periodic_workflow.py  # Weekly/daily analysis pipeline (LangGraph)
│   ├── anomaly_workflow.py   # Event-driven anomaly detection pipeline
│   └── state.py              # Shared AgentState TypedDict
├── vectordb/
│   ├── __init__.py
│   ├── ingest.py             # Ingest documents into vector DB
│   ├── query.py              # RAG query interface
│   └── embeddings.py         # Local embedding model setup
├── utils/
│   ├── __init__.py
│   ├── technical_analysis.py # TA indicators (RSI, MACD, Bollinger, Z-score)
│   ├── anomaly_detector.py   # Z-score & volume spike detection
│   └── prompts.py            # All structured prompts (centralized)
├── config/
│   ├── settings.py           # API keys, model configs, thresholds
│   └── sectors.py            # User-defined sectors of interest
├── tests/
│   ├── test_fetcher.py
│   ├── test_analyst.py
│   └── test_validator.py
├── main.py                   # Entry point
├── requirements.txt
└── README.md
```

---

## PART 4: Anti-Hallucination Strategy

This is the most critical part of your FYP. Here is a layered defense:

### Layer 1: Source Grounding (Prevention)
- Every piece of data fed to the analyst agent must have a `source_url` and `retrieval_timestamp`
- The analyst prompt must include: *"Only make claims supported by the provided data. Cite [SOURCE_ID] for every factual claim."*

### Layer 2: RAG Validation (Detection)
- After the analyst produces output, the Validator agent queries the vector DB for each claim
- Uses cosine similarity threshold (e.g., > 0.75) to confirm factual grounding
- If any claim has no supporting document → flag as UNVERIFIED

### Layer 3: Numerical Cross-Check (Verification)
- Extract all numbers from the analysis (revenue, growth %, margins)
- Compare against structured data (SEC XBRL, Yahoo Finance)
- If deviation > 5% → flag as NUMERICAL_ERROR

### Layer 4: Self-Correction Loop (Remediation)
- If Validator finds flaws → return to Analyst with specific correction instructions
- Maximum 3 correction loops before escalating to user with transparency report
- Log all correction iterations for benchmarking hallucination rate

### Layer 5: Confidence Scoring
- Each output gets a confidence score (1–10) based on:
  - Number of corroborating sources (more = higher)
  - Recency of data (older = lower)
  - Consensus alignment (contrarian = lower confidence, not lower validity)

---

## PART 5: Development Roadmap (Aligned to Official FYP Timeline)


### Phase 1 — Research & Feasibility (Jan 26 – Feb 8) 🟩
*Corresponds to: Task 2 — "Research for feasibility and marketing research"*

- [ ] Research LangGraph architecture patterns for multi-agent financial workflows
- [x] Evaluate local LLM options: selected GLM-4.7-Flash (free on Ollama + free on OpenRouter)
- [ ] Survey and test all free data APIs (SEC EDGAR, FRED, Finnhub, Yahoo Finance)
- [ ] Test RSS feed reliability for 10+ financial news sources
- [ ] Research vector DB options (ChromaDB vs Qdrant) — select one
- [ ] Research anti-hallucination techniques (RAG grounding, self-consistency, numerical validation)
- [ ] Document feasibility findings: what's achievable within free-tier limits
- [ ] Finalize the 9 data categories and map each to a concrete free source

---

### Phase 2 — First Prototype in Small Scope (Feb 8 – Mar 8) 🔵
*Corresponds to: Task 3 — "Creating a first prototype in a small scope"*

- [ ] Set up project structure, Git repo, and virtual environment
- [x] Install and configure Ollama with GLM-4.7-Flash (dual-mode: OpenRouter for dev, Ollama for local)
- [ ] Build core data source wrappers:
  - [ ] `sec_edgar.py` — fetch 10-K, 10-Q, 8-K filings
  - [ ] `fred_macro.py` — fetch CPI, interest rates, GDP
  - [ ] `yahoo_finance.py` — fetch OHLCV prices, fundamentals
  - [ ] `finnhub_client.py` — fetch earnings transcripts, analyst recommendations
  - [ ] `rss_fetcher.py` — aggregate 10+ RSS news feeds
- [ ] Set up ChromaDB/Qdrant vector database locally
- [ ] Create embedding pipeline (ingest sample 10-K filings using `nomic-embed-text`)
- [ ] Implement basic LangGraph `AgentState` and state machine (Fetch → Summarize → Analyze)
- [ ] Build a **minimum viable periodic workflow** for a single sector (e.g., semiconductor)
- [ ] Demonstrate basic second-order reasoning on one example news event

---

### Internal Review 1 (Mar 8 – Mar 15) 🟪
*Corresponds to: Task 4 — "Internal Review"*

- [ ] Prepare demo of small-scope prototype
- [ ] Document what works and what needs improvement
- [ ] Collect supervisor feedback on architecture decisions
- [ ] Identify gaps in data coverage and reasoning quality

---

### Phase 3 — Refinement 1: Core Functionality (Mar 15 – Apr 12) 🟧
*Corresponds to: Task 5 — "Refinement 1: Focusing on core functionality"*

- [ ] Build Reflector agent (information sufficiency check with re-query loop)
- [ ] Build full Analyst agent (second-order CoT reasoning with all 9 data categories)
- [ ] Build Validator/Critic agent:
  - [ ] RAG cross-reference against vector DB (cosine similarity > 0.75)
  - [ ] Numerical cross-check against structured data (SEC XBRL, Yahoo Finance)
  - [ ] Self-correction loop (max 3 iterations)
- [ ] Implement Z-score and volume spike anomaly detector
- [ ] Build anomaly workflow (trigger → fetch → analyze → validate → simulate → advise)
- [ ] Connect real-time price feeds (Yahoo Finance polling or Finnhub WebSocket free tier)
- [ ] Build Simulator agent (Buy/Sell/Hold scenario modeling over 12 months)
- [ ] Implement confidence scoring system (1–10 scale)
- [ ] Expand data source coverage:
  - [ ] `reddit_sentiment.py` — Reddit API for retail sentiment
  - [ ] `google_trends.py` — demand signal proxy
- [ ] Refine all agent prompts for reasoning quality and source citation

---

### Internal Review 2 (Apr 12 – Apr 19) 🟪
*Corresponds to: Task 6 — "Second Internal Review"*

- [ ] Demo both periodic and anomaly workflows end-to-end
- [ ] Present hallucination rate measurement methodology
- [ ] Collect feedback on reasoning quality and output format
- [ ] Identify remaining core functionality gaps

---

### ◆ Milestone: Progress Report (Apr 19) 💎
*Corresponds to: Task 12 — "Milestone: Progress Report"*

- [ ] Submit progress report documenting:
  - Architecture decisions and rationale
  - Data categories and source mapping
  - Prototype demo results
  - Anti-hallucination strategy and early metrics
  - Remaining work plan

---

### Phase 4 — Refinement 2: UI/UX & Bug Fixes (Apr 19 – May 10) 🟧
*Corresponds to: Task 7 — "Refinement 2: UI/UX improvements and fixing bugs"*

- [ ] Create Streamlit/Gradio dashboard:
  - [ ] User sector preference configuration page
  - [ ] Real-time analysis feed view
  - [ ] Anomaly alert panel with "Explainable Alpha"
  - [ ] Historical analysis archive & search
  - [ ] Confidence score visualization
- [ ] Connect periodic workflow to APScheduler (daily/weekly runs)
- [ ] Build Advisor agent (final output with risk scores and actionable advice)
- [ ] Fix bugs identified in Internal Review 2
- [ ] Improve error handling and graceful API failure fallbacks
- [ ] Optimize prompt templates based on observed output quality

---

### Phase 5 — Add Extra Features & Tools (May 10 – Jun 7) 🔵
*Corresponds to: Task 8 — "Add extra features and tools"*

- [ ] Add advanced data sources:
  - [ ] Patent analysis (USPTO) for innovation pipeline
  - [ ] Google Trends integration for demand proxies
  - [ ] Academic paper ingestion (SSRN, arXiv q-fin) into vector DB
  - [ ] Central bank speeches & FOMC minutes parser
- [ ] Implement sector rotation detection (relative strength across sector ETFs)
- [ ] Add cross-company peer comparison module
- [ ] Build a backtesting engine to evaluate past recommendations vs. actual returns
- [ ] Implement notification system (email/webhook alerts for anomaly triggers)
- [ ] Add multi-sector parallel analysis (run analysis for N sectors concurrently)
- [ ] Build report export functionality (PDF/Markdown generation)

---

### Phase 6 — Testing & Evaluation (Jun 7 – Jun 21) 🔵
*Corresponds to: Task 9 — "Testing and evaluate the final product"*

- [ ] **Hallucination Benchmark:** Manual audit of 100+ outputs vs. source data
  - Measure: % of claims with valid source citations
  - Measure: % of numerical claims within 5% of ground truth
- [ ] **Performance Benchmark:** 
  - Latency per analysis cycle on RTX 5070 Ti
  - Throughput: how many sectors per hour
  - Memory usage with 32b model
- [ ] **Investment Benchmark:** 
  - Backtest recommendations against S&P 500 returns (6-month window)
  - Compare Buy/Sell/Hold accuracy with actual price movement
- [ ] **Anomaly Detection Benchmark:**
  - Precision/Recall of Z-score triggers vs. actual significant events
- [ ] Write test suites for all agents and data source wrappers
- [ ] Stress-test with edge cases (missing data, API downtime, contradictory sources)

---

### Phase 7 — Last Refinement: Final Polish & Stability (Jun 21 – Jul 19) 🟧
*Corresponds to: Task 10 — "Last Refinement: Final polish and stability"*

- [ ] Fix all bugs discovered during testing
- [ ] Optimize LLM inference speed (batching, caching, prompt compression)
- [ ] Harden error handling for all external API calls
- [ ] Add logging and monitoring for production-like stability
- [ ] Polish UI/UX based on testing feedback
- [ ] Finalize anti-hallucination pipeline thresholds
- [ ] Ensure all workflows run reliably on a 24-hour continuous schedule
- [ ] Code cleanup, documentation, and type hints

---

### Phase 8 — Thesis Documentation & Final Delivery (Jul 19 – Aug 9) 🔵
*Corresponds to: Tasks 11 & 13 — "Thesis Documentation" + "Project Demonstration & Final Report"*

- [ ] Write thesis/FYP report:
  - Introduction & motivation (Reasoning Gap, Information Overload, Hallucination)
  - Literature review (multi-agent systems, RAG, financial AI)
  - System architecture & design decisions
  - Implementation details (9 data categories, 7 agents, 2 workflows)
  - Evaluation results (hallucination rate, investment benchmark, performance)
  - Discussion, limitations & future work
- [ ] Prepare project demonstration (live demo with real market data)
- [ ] Create presentation slides

### ◆ Milestone: Project Demonstration & Final Report (Aug 9) 💎
- [ ] Submit final report
- [ ] Deliver live demonstration

---

## PART 6: Key Python Dependencies

```
# requirements.txt
langgraph>=0.2.0
langchain>=0.3.0
langchain-ollama>=0.2.0
langchain-community>=0.3.0

# Vector DB
chromadb>=0.5.0
# sentence-transformers>=3.0.0  # if not using Ollama embeddings

# Data Sources
yfinance>=0.2.40
finnhub-python>=2.4.0
fredapi>=0.5.0
feedparser>=6.0.0
praw>=7.7.0          # Reddit
pytrends>=4.9.0      # Google Trends
sec-edgar-downloader>=5.0.0

# Analysis
pandas>=2.2.0
numpy>=1.26.0
ta>=0.11.0           # Technical Analysis
scipy>=1.12.0        # Z-score calculations

# Scheduling
apscheduler>=3.10.0

# Frontend (optional)
streamlit>=1.38.0

# Utilities
requests>=2.31.0
beautifulsoup4>=4.12.0
python-dotenv>=1.0.0
```

---

## Summary: What You're Building

```
                    ┌─────────────────────────────────────────┐
                    │         USER SECTORS CONFIG              │
                    └──────────────┬──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────┐
                    │     PERIODIC SCHEDULER (Weekly/Daily)    │
                    └──────────────┬──────────────────────────┘
                                   │
  ┌────────────────────────────────▼────────────────────────────────┐
  │                        FETCHER AGENT                            │
  │  SEC EDGAR │ FRED │ Finnhub │ Yahoo │ RSS Feeds │ Reddit │ etc │
  └────────────────────────────────┬────────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │      SUMMARIZER AGENT        │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │      REFLECTOR AGENT         │◄──── Loop if data
                    │  (Information Sufficiency)   │      insufficient
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │       ANALYST AGENT          │
                    │  (Second-Order CoT Reasoning)│
                    │  9 Data Categories Input      │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │      VALIDATOR AGENT         │◄──── Loop if flaws
                    │  (RAG + Numerical Check)     │      (max 3x)
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
     ┌────────▼────────┐  ┌───────▼───────┐  ┌────────▼────────┐
     │   STORE IN DB   │  │   SIMULATOR   │  │  USER REPORT    │
     │  (Vector + SQL) │  │  (Scenarios)  │  │  (Advice + Risk)│
     └─────────────────┘  └───────────────┘  └─────────────────┘
```

> **Total estimated API cost: $0/month** (all free tiers + local LLM)
> **Hardware requirement: RTX 5070 Ti (16GB VRAM)** — sufficient for GLM-4.7-Flash via Ollama (production), with OpenRouter API fallback for development
