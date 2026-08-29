"""
Central validation module for the Globant Data Engineer Challenge.

Used both by the historical migration (Challenge #1.1) and by the API
ingestion endpoints (Challenge #1.2), to guarantee that both paths apply
exactly the same rules. This directly follows the documented assumption:
validation also applies to the historical load, not only to what comes
in through the API.

Rules implemented (per the PDF's data dictionary):
1. All fields are required: id, name, datetime, department_id, job_id
2. datetime must be in ISO 8601 format (e.g. 2021-07-27T16:02:08Z)
3. department_id must exist in the departments table
4. job_id must exist in the jobs table
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
    """Strictly accepts ISO 8601 format with a 'Z' suffix (UTC), just like
    the PDF's example: 2021-07-27T16:02:08Z.
    Any other format (with or without a space, without 'T', without 'Z',
    with '/', etc.) is considered invalid.
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
    """Validates a single hired_employees record.

    record: dict with keys id, name, datetime, department_id, job_id
            (as they come from a csv.DictReader or from an API JSON body).
    valid_department_ids / valid_job_ids: sets of the ids that exist in
            the departments and jobs tables, to check the FKs without
            hitting the database on every row.
    """
    errors: list[str] = []

    for field_name in REQUIRED_FIELDS:
        if field_name not in record or _is_blank(record.get(field_name)):
            errors.append(f"missing_required_field:{field_name}")

    # id: if present, must be a valid integer.
    id_raw = record.get("id")
    if not _is_blank(id_raw):
        try:
            int(id_raw)
        except (ValueError, TypeError):
            errors.append("id_not_integer")

    # datetime: strict ISO 8601 format with 'Z'.
    dt_raw = record.get("datetime")
    if not _is_blank(dt_raw) and parse_iso_datetime(dt_raw) is None:
        errors.append("invalid_datetime_format")

    # department_id: must be an integer and exist in departments.
    dept_raw = record.get("department_id")
    if not _is_blank(dept_raw):
        try:
            dept_id = int(dept_raw)
            if dept_id not in valid_department_ids:
                errors.append("department_id_not_found")
        except (ValueError, TypeError):
            errors.append("department_id_not_integer")

    # job_id: must be an integer and exist in jobs.
    job_raw = record.get("job_id")
    if not _is_blank(job_raw):
        try:
            job_id = int(job_raw)
            if job_id not in valid_job_ids:
                errors.append("job_id_not_found")
        except (ValueError, TypeError):
            errors.append("job_id_not_integer")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)


def validate_lookup_record(record: dict, name_field: str) -> ValidationResult:
    """Validates a departments or jobs record: integer id + non-empty name.

    These 2 tables don't have hired_employees' date/FK rules (their data
    dictionary only defines id + one name field), but they're still
    validated to avoid inserting broken rows.
    """
    errors: list[str] = []

    id_raw = record.get("id")
    if _is_blank(id_raw):
        errors.append("missing_required_field:id")
    else:
        try:
            int(id_raw)
        except (ValueError, TypeError):
            errors.append("id_not_integer")

    name_raw = record.get(name_field)
    if _is_blank(name_raw):
        errors.append(f"missing_required_field:{name_field}")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)
