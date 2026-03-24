"""
SEC EDGAR Fetcher — pull recent filings AND their actual text content.

The SEC EDGAR API is completely free and open to anyone worldwide.
No account needed — just requires an email in the User-Agent header
(so they can contact you if your script misbehaves).

WHAT THIS MODULE DOES:
1. Looks up a company's CIK number from its ticker symbol
2. Fetches metadata for recent filings (10-K, 10-Q, 8-K)
3. Downloads the actual filing document (HTML)
4. Extracts key sections: MD&A, Risk Factors, Business Overview
5. Returns both metadata AND usable text content for the LLM

WHY THIS MATTERS:
Without filing text, the LLM only sees "NVDA filed a 10-K on 2025-02-21"
which is useless. With filing text, it sees actual management commentary
about revenue guidance, margin outlook, and risk disclosures — the kind
of information that moves stocks.
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from config.settings import SEC_EDGAR_EMAIL, SEC_EDGAR_BASE_URL

import logging
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# EDUCATIONAL CONTEXT
# ═══════════════════════════════════════════════════════════════════

FILING_EDUCATION = {
    "10-K": {
        "name": "Annual Report",
        "what_it_is": (
            "A comprehensive yearly report that public companies must file. "
            "Contains audited financial statements, management's discussion of "
            "business operations (MD&A), risk factors, and strategic outlook. "
            "Think of it as the company's full health checkup."
        ),
        "why_it_matters": (
            "The MD&A section is where management explains WHY numbers changed — "
            "not just that revenue grew 20%, but that it grew because of AI chip "
            "demand. Risk factors reveal what the company itself sees as threats."
        ),
        "key_sections": ["Management's Discussion & Analysis (MD&A)", "Risk Factors", "Business Overview"],
        "learn_more": "https://www.investor.gov/introduction-investing/investing-basics/glossary/form-10-k",
    },
    "10-Q": {
        "name": "Quarterly Report",
        "what_it_is": (
            "A quarterly update (filed 3x per year — Q1, Q2, Q3; the 4th quarter "
            "is covered by the 10-K). Contains unaudited financial statements and "
            "an MD&A update. More timely than the 10-K but less comprehensive."
        ),
        "why_it_matters": (
            "Quarterly reports catch trends between annual reports. A company's "
            "margins shrinking for two quarters in a row is a red flag that the "
            "10-K alone wouldn't catch until year-end."
        ),
        "key_sections": ["Management's Discussion & Analysis (MD&A)", "Risk Factors (if updated)"],
        "learn_more": "https://www.investor.gov/introduction-investing/investing-basics/glossary/form-10-q",
    },
    "8-K": {
        "name": "Current Report (Material Event)",
        "what_it_is": (
            "Filed within 4 business days of a 'material event' — something big "
            "enough to affect the stock price. Examples: CEO change, merger "
            "announcement, bankruptcy filing, major contract, earnings release."
        ),
        "why_it_matters": (
            "8-Ks are the fastest official information channel. When a company "
            "announces earnings, a big acquisition, or a CEO departure, the 8-K "
            "is the primary source document."
        ),
        "key_sections": ["Item descriptions", "Exhibits"],
        "learn_more": "https://www.investor.gov/introduction-investing/investing-basics/glossary/form-8-k",
    },
    "DEF 14A": {
        "name": "Proxy Statement",
        "what_it_is": (
            "Filed before the annual shareholder meeting. Shows executive "
            "compensation, board nominees, and shareholder vote items."
        ),
        "why_it_matters": (
            "Reveals how much executives are paid and whether their incentives "
            "align with shareholders. Large stock-based compensation can dilute shares."
        ),
        "key_sections": ["Executive Compensation", "Board of Directors"],
        "learn_more": "https://www.investor.gov/introduction-investing/investing-basics/glossary/proxy-statement",
    },
}

# General SEC educational resource
SEC_EDUCATION_LINK = "https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/how-read"


# ═══════════════════════════════════════════════════════════════════
# RATE LIMITING & HTTP
# ═══════════════════════════════════════════════════════════════════

HEADERS = {
    "User-Agent": f"FYP-Financial-Analyzer/1.0 ({SEC_EDGAR_EMAIL})",
    "Accept-Encoding": "gzip, deflate",
}

import threading

_last_request_time = 0
_rate_lock = threading.Lock()


def _rate_limit():
    """Ensure we don't exceed SEC's 10 req/sec limit (thread-safe)."""
    global _last_request_time
    with _rate_lock:
        elapsed = time.time() - _last_request_time
        if elapsed < 0.12:  # ~8 req/sec to be safe
            time.sleep(0.12 - elapsed)
        _last_request_time = time.time()


def _sec_get(url: str, timeout: int = 15) -> requests.Response:
    """Rate-limited GET request to SEC with automatic retry."""
    from utils.http_retry import resilient_get

    _rate_limit()
    return resilient_get(
        url,
        timeout=timeout,
        max_retries=2,
        backoff_base=1.0,
        headers=HEADERS,
        label="SEC EDGAR",
    )


# ═══════════════════════════════════════════════════════════════════
# CIK LOOKUP (cached in-memory for the session)
# ═══════════════════════════════════════════════════════════════════

_cik_cache: dict[str, tuple[str, str]] = {}  # ticker -> (cik, company_name)


def _lookup_cik(ticker: str) -> tuple[str, str] | None:
    """
    Look up SEC CIK number from ticker. Returns (cik_padded, company_name).
    Uses SEC's company_tickers.json — cached after first call.
    """
    ticker_upper = ticker.upper()
    if ticker_upper in _cik_cache:
        return _cik_cache[ticker_upper]

    try:
        resp = _sec_get("https://www.sec.gov/files/company_tickers.json")
        tickers_data = resp.json()

        # Cache ALL tickers from this response — saves future API calls
        for entry in tickers_data.values():
            t = entry.get("ticker", "").upper()
            cik = str(entry["cik_str"]).zfill(10)
            name = entry.get("title", t)
            _cik_cache[t] = (cik, name)

        return _cik_cache.get(ticker_upper)

    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
# FILING METADATA
# ═══════════════════════════════════════════════════════════════════

def get_company_filings_by_ticker(
    ticker: str,
    filing_type: str = "10-K",
    max_results: int = 3,
) -> list[dict]:
    """
    Get recent filings for a company by its ticker symbol.

    Returns list of filing dicts with metadata fields:
    - company, ticker, type, date, description, url, accession_number, cik
    """
    if not SEC_EDGAR_EMAIL:
        return [{"error": "SEC_EDGAR_EMAIL not set in .env — needed for SEC API access"}]

    lookup = _lookup_cik(ticker)
    if not lookup:
        return [{"error": f"Ticker {ticker} not found in SEC database"}]

    cik, company_name = lookup

    try:
        resp = _sec_get(f"https://data.sec.gov/submissions/CIK{cik}.json")
        data = resp.json()

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])
        descriptions = recent.get("primaryDocDescription", [])

        filings = []
        for i in range(len(forms)):
            if filing_type and forms[i] != filing_type:
                continue
            if len(filings) >= max_results:
                break

            cik_stripped = cik.lstrip("0")
            accession_clean = accessions[i].replace("-", "")
            doc_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{cik_stripped}/{accession_clean}/{primary_docs[i]}"
            )

            # Get educational info for this filing type
            edu = FILING_EDUCATION.get(forms[i], {})

            filings.append({
                "company": company_name,
                "ticker": ticker,
                "type": forms[i],
                "date": dates[i],
                "description": descriptions[i] if i < len(descriptions) else "",
                "url": doc_url,
                "accession_number": accessions[i],
                "cik": cik_stripped,
                # Educational metadata
                "type_name": edu.get("name", forms[i]),
                "type_explanation": edu.get("what_it_is", ""),
                "type_why_it_matters": edu.get("why_it_matters", ""),
                "learn_more_url": edu.get("learn_more", SEC_EDUCATION_LINK),
            })

        return filings

    except Exception as e:
        return [{"error": f"Failed to fetch filings for {ticker}: {e}"}]


# ═══════════════════════════════════════════════════════════════════
# FILING TEXT EXTRACTION
# ═══════════════════════════════════════════════════════════════════

# Section header patterns — these match the standard headings in SEC filings.
# SEC filings use "Item 7" for MD&A, "Item 1A" for Risk Factors, etc.
# We look for both the item number and the section name for robustness.
_SECTION_PATTERNS = [
    {
        "name": "Management Discussion & Analysis (MD&A)",
        "tag": "mda",
        "patterns": [
            r"(?i)item\s*7[\.\s]*[-—–]?\s*management.{0,5}s?\s*discussion",
            r"(?i)management.{0,5}s?\s*discussion\s*(?:and|&)\s*analysis",
        ],
        "priority": 1,  # Most valuable section
    },
    {
        "name": "Risk Factors",
        "tag": "risk_factors",
        "patterns": [
            r"(?i)item\s*1a[\.\s]*[-—–]?\s*risk\s*factors",
            r"(?i)risk\s*factors",
        ],
        "priority": 2,
    },
    {
        "name": "Business Overview",
        "tag": "business",
        "patterns": [
            r"(?i)item\s*1[\.\s]*[-—–]?\s*business\b",
            r"(?i)(?:business|company)\s*overview",
        ],
        "priority": 3,
    },
]

# For 8-Ks, look for item descriptions instead
_8K_ITEM_PATTERNS = [
    r"(?i)item\s*\d+\.\d+",         # "Item 2.02", "Item 5.02" etc.
    r"(?i)results\s*of\s*operations",
    r"(?i)departure\s*of\s*directors",
    r"(?i)financial\s*statements\s*and\s*exhibits",
]


def fetch_filing_text(
    filing: dict,
    max_chars_per_section: int = 3000,
    max_total_chars: int = 8000,
) -> dict:
    """
    Download a filing and extract key text sections.

    Args:
        filing: A filing dict from get_company_filings_by_ticker()
        max_chars_per_section: Max characters to extract per section
        max_total_chars: Hard cap on total extracted text

    Returns:
        Dict with:
        - sections: list of {name, tag, text} dicts
        - total_chars: int
        - extraction_note: str (any warnings)
    """
    url = filing.get("url", "")
    if not url:
        return {"sections": [], "total_chars": 0, "extraction_note": "No filing URL"}

    try:
        resp = _sec_get(url, timeout=30)
        content_type = resp.headers.get("Content-Type", "")

        # Parse HTML filing
        if "html" in content_type or url.endswith(".htm") or url.endswith(".html"):
            text = _extract_from_html(resp.text)
        else:
            # Plain text filing (rare but possible)
            text = resp.text

        if not text or len(text) < 200:
            return {
                "sections": [],
                "total_chars": 0,
                "extraction_note": "Filing document too short or empty",
            }

        filing_type = filing.get("type", "")
        if filing_type == "8-K":
            sections = _extract_8k_sections(text, max_chars_per_section)
        else:
            sections = _extract_annual_quarterly_sections(text, max_chars_per_section)

        # Enforce total char cap
        total = 0
        capped_sections = []
        for sec in sections:
            remaining = max_total_chars - total
            if remaining <= 0:
                break
            if len(sec["text"]) > remaining:
                sec["text"] = sec["text"][:remaining] + "... [truncated]"
            total += len(sec["text"])
            capped_sections.append(sec)

        note = ""
        if not capped_sections:
            note = (
                "Could not find standard section headers (MD&A, Risk Factors). "
                "This may be a non-standard filing format."
            )

        return {
            "sections": capped_sections,
            "total_chars": total,
            "extraction_note": note,
        }

    except requests.Timeout:
        return {
            "sections": [],
            "total_chars": 0,
            "extraction_note": "Filing download timed out (document may be very large)",
        }
    except Exception as e:
        return {
            "sections": [],
            "total_chars": 0,
            "extraction_note": f"Failed to extract filing text: {e}",
        }


def _extract_from_html(html: str) -> str:
    """Strip HTML tags, clean up whitespace, return plain text."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove script, style, and hidden elements
    for tag in soup.find_all(["script", "style", "meta", "link"]):
        tag.decompose()

    # Get text with reasonable spacing
    text = soup.get_text(separator="\n")

    # Clean up excessive whitespace while preserving paragraph breaks
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped:
            # Collapse internal whitespace
            stripped = re.sub(r"\s+", " ", stripped)
            lines.append(stripped)

    return "\n".join(lines)


def _is_toc_region(text: str, pos: int) -> bool:
    """
    Check if a match position is inside a Table of Contents.

    ToC regions have lines that are just page numbers (1-4 digit numbers
    on their own line) mixed with section headers. Real content has
    full sentences and paragraphs.
    """
    # Look at the next 600 chars after the match
    preview = text[pos:pos + 600]
    lines = preview.split("\n")

    # Count lines that are just page numbers (1-4 digits, optionally with spaces)
    page_number_lines = sum(
        1 for ln in lines[1:]  # Skip the header line itself
        if re.match(r"^\s*\d{1,4}\s*$", ln.strip())
    )

    # Count lines that look like "Item N." references (other ToC entries)
    item_ref_lines = sum(
        1 for ln in lines[1:]
        if re.match(r"(?i)^\s*item\s+\d", ln.strip())
    )

    # In a ToC, you'll see many page numbers and item references.
    # In real content, you'll see 0-1 at most.
    return (page_number_lines >= 3) or (item_ref_lines >= 2 and page_number_lines >= 1)


def _extract_annual_quarterly_sections(
    text: str,
    max_chars: int,
) -> list[dict]:
    """
    Extract MD&A, Risk Factors, and Business sections from 10-K/10-Q text.

    Strategy: Find section headers, but skip Table of Contents entries.
    ToC entries have page numbers and other Item references following them,
    while actual sections have paragraphs of real text.
    """
    results = []

    for section_def in _SECTION_PATTERNS:
        best_match = None

        for pattern in section_def["patterns"]:
            # Find ALL occurrences — ToC and actual content
            for m in re.finditer(pattern, text):
                pos = m.start()
                # Skip if this is inside the Table of Contents
                if _is_toc_region(text, pos):
                    continue
                # Take the first non-ToC match (closest to actual content)
                best_match = pos
                break
            if best_match is not None:
                break

        if best_match is None:
            continue

        # Extract text from this section header to the next likely header
        section_text = text[best_match:]

        # Find where the next major section starts (Item N or similar)
        # Skip at least 500 chars to avoid matching sub-items within this section
        next_section = re.search(
            r"(?i)\n\s*item\s*\d+[a-z]?[\.\s]*[-—–]",
            section_text[500:],
        )

        if next_section:
            end = 500 + next_section.start()
            section_text = section_text[:end]

        # Clean and truncate
        section_text = section_text.strip()
        if len(section_text) > max_chars:
            # Try to cut at a sentence boundary
            cut_point = section_text.rfind(". ", max_chars - 200, max_chars)
            if cut_point > 0:
                section_text = section_text[:cut_point + 1] + " [... continued in filing]"
            else:
                section_text = section_text[:max_chars] + "... [truncated]"

        if len(section_text) > 100:  # Only add if we got meaningful content
            results.append({
                "name": section_def["name"],
                "tag": section_def["tag"],
                "text": section_text,
            })

    # Sort by priority
    tag_priority = {s["tag"]: s["priority"] for s in _SECTION_PATTERNS}
    results.sort(key=lambda x: tag_priority.get(x["tag"], 99))

    return results


def _extract_8k_sections(text: str, max_chars: int) -> list[dict]:
    """
    Extract content from 8-K filings. 8-Ks are shorter and structured
    differently — they describe specific material events.
    """
    results = []

    # Try to find item descriptions
    for pattern in _8K_ITEM_PATTERNS:
        m = re.search(pattern, text)
        if m:
            chunk = text[m.start():m.start() + max_chars]
            # Find a clean end point
            cut = chunk.rfind(". ", max(0, len(chunk) - 300))
            if cut > 100:
                chunk = chunk[:cut + 1]

            if len(chunk) > 100:
                results.append({
                    "name": "Event Details",
                    "tag": "event",
                    "text": chunk.strip(),
                })
                break  # One good section is enough for 8-Ks

    # If no specific items found, grab the first substantial paragraph
    if not results and len(text) > 200:
        chunk = text[:max_chars]
        cut = chunk.rfind(". ", max(0, len(chunk) - 200))
        if cut > 100:
            chunk = chunk[:cut + 1]
        results.append({
            "name": "Filing Content",
            "tag": "content",
            "text": chunk.strip(),
        })

    return results


# ═══════════════════════════════════════════════════════════════════
# HIGH-LEVEL CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def get_filings_with_text(
    ticker: str,
    filing_types: list[str] | None = None,
    max_filings: int = 2,
    max_text_chars: int = 6000,
) -> list[dict]:
    """
    Fetch filings AND their actual text content for a ticker.

    This is the main entry point for the pipeline. Returns filings
    enriched with extracted text sections.

    Args:
        ticker: Stock ticker (e.g., "NVDA")
        filing_types: Which types to fetch. Default: ["10-K", "10-Q", "8-K"]
        max_filings: Max filings to return (across all types)
        max_text_chars: Max chars of text to extract per filing

    Returns:
        List of filing dicts (same as get_company_filings_by_ticker)
        plus additional keys:
        - text_sections: list of {name, tag, text}
        - text_total_chars: int
        - text_extraction_note: str
    """
    if filing_types is None:
        filing_types = ["10-K", "10-Q", "8-K"]

    all_filings = []

    for ftype in filing_types:
        filings = get_company_filings_by_ticker(ticker, ftype, max_results=1)
        for f in filings:
            if "error" not in f:
                all_filings.append(f)
        if len(all_filings) >= max_filings:
            break

    all_filings = all_filings[:max_filings]

    # Now fetch actual text for each filing
    for filing in all_filings:
        logger.info("Downloading %s %s (%s)...", filing['ticker'], filing['type'], filing['date'])
        text_result = fetch_filing_text(filing, max_total_chars=max_text_chars)
        filing["text_sections"] = text_result["sections"]
        filing["text_total_chars"] = text_result["total_chars"]
        filing["text_extraction_note"] = text_result["extraction_note"]

        section_names = [s["name"] for s in text_result["sections"]]
        if section_names:
            logger.info("Extracted: %s (%d chars)", ', '.join(section_names), text_result['total_chars'])
        elif text_result["extraction_note"]:
            logger.warning("%s", text_result['extraction_note'])

    return all_filings


def search_filings(company_name: str, filing_type: str = "", max_results: int = 5) -> list[dict]:
    """
    Search for recent SEC filings by company name using EFTS.

    Args:
        company_name: e.g., "NVIDIA" or "Rocket Lab"
        filing_type: e.g., "10-K", "10-Q", "8-K" (empty = all types)
        max_results: max filings to return

    Returns:
        List of filing dicts with:
        - company, type, date, description, url
    """
    if not SEC_EDGAR_EMAIL:
        return [{"error": "SEC_EDGAR_EMAIL not set in .env — needed for SEC API access"}]

    _rate_limit()

    # Dynamic date range: last 2 years → today (never expires)
    from datetime import datetime, timedelta
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
    params = {
        "q": company_name,
        "dateRange": "custom",
        "startdt": start_date,
        "enddt": end_date,
        "forms": filing_type,
    }

    try:
        from utils.http_retry import resilient_get
        response = resilient_get(
            f"{SEC_EDGAR_BASE_URL}/search-index",
            timeout=15,
            max_retries=2,
            backoff_base=1.0,
            headers=HEADERS,
            label=f"SEC search ({company_name})",
            params=params,
        )
        response.raise_for_status()
        data = response.json()

        filings = []
        for hit in data.get("hits", {}).get("hits", [])[:max_results]:
            source = hit.get("_source", {})
            filings.append({
                "company": (
                    source.get("display_names", [company_name])[0]
                    if source.get("display_names") else company_name
                ),
                "type": source.get("form_type", "Unknown"),
                "date": source.get("file_date", "Unknown"),
                "description": source.get("display_description", ""),
                "url": (
                    f"https://www.sec.gov/Archives/edgar/data/"
                    f"{source.get('entity_id', '')}/{source.get('file_num', '')}"
                ),
            })

        return filings

    except Exception as e:
        return [{"error": f"SEC EDGAR search failed: {e}"}]


def format_filings_for_prompt(filings: list[dict]) -> str:
    """
    Format filings (with text sections) into a string for the LLM prompt.

    This replaces the old one-liner format. Now the LLM gets actual
    management commentary to reason about.
    """
    if not filings:
        return ""

    lines = ["## RECENT SEC FILINGS\n"]

    for f in filings:
        if "error" in f:
            lines.append(f"- {f['error']}")
            continue

        ticker = f.get("ticker", f.get("company", ""))
        ftype = f.get("type", "?")
        date = f.get("date", "?")
        desc = f.get("description", "")

        lines.append(f"### {ticker}: {ftype} ({date})")
        if desc:
            lines.append(f"*{desc}*")
        lines.append("")

        # Add extracted text sections
        sections = f.get("text_sections", [])
        if sections:
            for sec in sections:
                lines.append(f"**{sec['name']}:**")
                lines.append(sec["text"])
                lines.append("")
        else:
            note = f.get("text_extraction_note", "")
            if note:
                lines.append(f"*Note: {note}*")
            else:
                lines.append(f"*No text content extracted. [View full filing]({f.get('url', '')})*")
            lines.append("")

    return "\n".join(lines)
