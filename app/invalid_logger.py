"""
Logging estructurado de registros inválidos.

Decisión (ver CLAUDE.md): archivo de log, no tabla de auditoría aparte.
Un logger dedicado en JSON Lines (un objeto JSON por línea) para que
tanto la migración histórica como los endpoints de la API lo reusen y
el archivo se pueda parsear fácilmente si hace falta revisarlo.
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
    """Loguea un registro rechazado como una línea JSON.

    source: origen del rechazo, ej. "historical_migration" o "api_ingestion".
    table: tabla destino, ej. "hired_employees".
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source,
        "table": table,
        "record": record,
        "errors": errors,
    }
    _logger.info(json.dumps(entry, ensure_ascii=False))
