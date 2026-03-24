"""
Logging Configuration — centralized setup for the entire application.

Usage:
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Something happened: %s", detail)

All modules should use `logging.getLogger(__name__)` — NEVER `print()`.
This gives us:
- Log levels (DEBUG, INFO, WARNING, ERROR) instead of print soup
- File output alongside console for debugging production runs
- Timestamps on every message
- Module names so you know WHERE the message came from
"""

import logging
import os
import sys

LOG_DIR = os.path.dirname(os.path.dirname(__file__))
LOG_FILE = os.path.join(LOG_DIR, "pipeline.log")


def setup_logging(level: str = "INFO") -> None:
    """
    Configure logging for the application.

    Call this ONCE at startup (in main.py or app.py).
    After this, any module using `logging.getLogger(__name__)` will
    automatically write to both console and the log file.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Root logger — all child loggers inherit this
    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Don't add handlers twice (Streamlit re-runs the script)
    if root.handlers:
        return

    # ── Console handler (human-friendly, with emoji-safe encoding) ─
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(numeric_level)
    console_fmt = logging.Formatter(
        "  %(levelname)-8s %(name)-30s │ %(message)s"
    )
    console.setFormatter(console_fmt)
    root.addHandler(console)

    # ── File handler (machine-parseable, with timestamps) ──────────
    try:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # Capture everything to file
        file_fmt = logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)-30s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_fmt)
        root.addHandler(file_handler)
    except (OSError, PermissionError):
        # If we can't write the log file (e.g., read-only filesystem), continue
        root.warning("Cannot write to log file: %s", LOG_FILE)

    # Quiet down noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("yfinance").setLevel(logging.WARNING)
