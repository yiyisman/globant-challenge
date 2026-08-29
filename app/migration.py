"""
Historical migration: loads the 3 original CSV files (data/) into Postgres.

Reuses the exact same validators.validate_record that the API ingestion
endpoints use, so the historical load and the API apply the same rules
(see CLAUDE.md).

Load order: departments and jobs first (they're hired_employees' FKs),
then hired_employees. Ids are preserved exactly as they come from the
CSV (they're not auto-incremented). The script is safe to re-run: it
uses ON CONFLICT (id) DO NOTHING, so running it twice neither fails nor
duplicates rows.

Usage:
    python -m app.migration
"""
from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import departments, engine, hired_employees, jobs, metadata
from app.invalid_logger import log_invalid_record
from app.validators import validate_lookup_record, validate_record

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SOURCE = "historical_migration"


def _read_csv(filename: str) -> list[dict]:
    with open(DATA_DIR / filename, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_lookup_table(table, csv_filename: str, name_field: str) -> None:
    """Loads departments.csv or jobs.csv: validates with validators.py
    (same rule the API uses), inserts valid rows, logs invalid ones."""
    rows = _read_csv(csv_filename)
    to_insert = []

    for row in rows:
        result = validate_lookup_record(row, name_field)
        if not result.is_valid:
            log_invalid_record(SOURCE, table.name, row, result.errors)
            continue

        to_insert.append({"id": int(row["id"]), name_field: row[name_field].strip()})

    if to_insert:
        stmt = pg_insert(table).values(to_insert)
        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
        with engine.begin() as conn:
            conn.execute(stmt)

    print(f"{table.name}: {len(to_insert)} valid out of {len(rows)} processed")


def _load_hired_employees() -> None:
    rows = _read_csv("hired_employees.csv")

    with engine.begin() as conn:
        valid_department_ids = {r[0] for r in conn.execute(select(departments.c.id))}
        valid_job_ids = {r[0] for r in conn.execute(select(jobs.c.id))}

    to_insert = []
    invalid_count = 0

    for row in rows:
        result = validate_record(row, valid_department_ids, valid_job_ids)
        if not result.is_valid:
            invalid_count += 1
            log_invalid_record(SOURCE, "hired_employees", row, result.errors)
            continue

        to_insert.append(
            {
                "id": int(row["id"]),
                "name": row["name"],
                "datetime": row["datetime"],
                "department_id": int(row["department_id"]),
                "job_id": int(row["job_id"]),
            }
        )

    if to_insert:
        stmt = pg_insert(hired_employees).values(to_insert)
        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
        with engine.begin() as conn:
            conn.execute(stmt)

    print(
        f"hired_employees: {len(to_insert)} valid, "
        f"{invalid_count} invalid, out of {len(rows)} processed"
    )


def main() -> None:
    metadata.create_all(engine, checkfirst=True)

    _load_lookup_table(departments, "departments.csv", "department")
    _load_lookup_table(jobs, "jobs.csv", "job")
    _load_hired_employees()

    print("\nInvalid records logged to: logs/invalid_records.log")


if __name__ == "__main__":
    main()
