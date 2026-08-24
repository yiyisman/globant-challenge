"""
Módulo central de validación para el Globant Data Engineer Challenge.

Se usa tanto en la migración histórica (Challenge #1.1) como en los
endpoints de ingesta de la API (Challenge #1.2), para garantizar que
ambos caminos apliquen exactamente las mismas reglas. Esto responde
directamente al assumption documentado: la validación aplica también
a la carga histórica, no solo a lo que llegue por la API.

Reglas implementadas (según el data dictionary del PDF):
1. Todos los campos son requeridos: id, name, datetime, department_id, job_id
2. datetime debe estar en formato ISO 8601 (ej. 2021-07-27T16:02:08Z)
3. department_id debe existir en la tabla departments
4. job_id debe existir en la tabla jobs
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

REQUIRED_FIELDS = ["id", "name", "datetime", "department_id", "job_id"]


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def parse_iso_datetime(value: Any) -> datetime | None:
    """Acepta estrictamente el formato ISO 8601 con sufijo 'Z' (UTC),
    tal como el ejemplo del PDF: 2021-07-27T16:02:08Z.
    Cualquier otro formato (con o sin espacio, sin 'T', sin 'Z',
    con '/', etc.) se considera inválido.
    """
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def validate_record(
    record: dict,
    valid_department_ids: set[int],
    valid_job_ids: set[int],
) -> ValidationResult:
    """Valida un único registro de hired_employees.

    record: dict con claves id, name, datetime, department_id, job_id
            (tal como vienen de un csv.DictReader o de un JSON de la API).
    valid_department_ids / valid_job_ids: sets con los ids existentes
            en las tablas departments y jobs, para chequear las FKs
            sin necesidad de golpear la base de datos por cada fila.
    """
    errors: list[str] = []

    for field_name in REQUIRED_FIELDS:
        if field_name not in record or _is_blank(record.get(field_name)):
            errors.append(f"missing_required_field:{field_name}")

    # id: si viene, debe ser un entero válido.
    id_raw = record.get("id")
    if not _is_blank(id_raw):
        try:
            int(id_raw)
        except (ValueError, TypeError):
            errors.append("id_not_integer")

    # datetime: formato ISO 8601 estricto con 'Z'.
    dt_raw = record.get("datetime")
    if not _is_blank(dt_raw) and parse_iso_datetime(dt_raw) is None:
        errors.append("invalid_datetime_format")

    # department_id: debe ser entero y existir en departments.
    dept_raw = record.get("department_id")
    if not _is_blank(dept_raw):
        try:
            dept_id = int(dept_raw)
            if dept_id not in valid_department_ids:
                errors.append("department_id_not_found")
        except (ValueError, TypeError):
            errors.append("department_id_not_integer")

    # job_id: debe ser entero y existir en jobs.
    job_raw = record.get("job_id")
    if not _is_blank(job_raw):
        try:
            job_id = int(job_raw)
            if job_id not in valid_job_ids:
                errors.append("job_id_not_found")
        except (ValueError, TypeError):
            errors.append("job_id_not_integer")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)
