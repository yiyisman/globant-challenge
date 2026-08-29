"""
Structured logging for invalid records.

Decision (see CLAUDE.md): a log file, not a separate audit table. A
dedicated JSON Lines logger (one JSON object per line) so both the
historical migration and the API endpoints can reuse it, and the file
can be easily parsed if it ever needs to be reviewed.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_FILE = LOG_DIR / "invalid_records.log"

LOG_DIR.mkdir(parents=True, exist_ok=True)

_logger = logging.getLogger("globant.invalid_records")
_logger.setLevel(logging.INFO)
if not _logger.handlers:
    _handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.propagate = False


def log_invalid_record(
    source: str,
    table: str,
    record: dict[str, Any],
    errors: list[str],
) -> None:
    """Logs a rejected record as a single JSON line.

    source: origin of the rejection, e.g. "historical_migration" or
            "api_ingestion".
    table: destination table, e.g. "hired_employees".
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source,
        "table": table,
        "record": record,
        "errors": errors,
    }
    _logger.info(json.dumps(entry, ensure_ascii=False))
