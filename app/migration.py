"""
Migración histórica: carga los 3 CSV originales (data/) a Postgres.

Reusa exactamente el mismo validators.validate_record que usarán los
endpoints de ingesta de la API, para que la carga histórica y la API
apliquen las mismas reglas (ver CLAUDE.md).

Orden de carga: departments y jobs primero (son la FK de
hired_employees), luego hired_employees. Los ids se preservan tal cual
vienen del CSV (no son autoincrementales). El script es re-ejecutable:
usa ON CONFLICT (id) DO NOTHING, así correrlo dos veces no falla ni
duplica filas.

Uso:
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
    """Carga departments.csv o jobs.csv: valida con validators.py (misma
    regla que usa la API), inserta válidos, loguea inválidos."""
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

    print(f"{table.name}: {len(to_insert)} válidos de {len(rows)} procesados")


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
        f"hired_employees: {len(to_insert)} válidos, "
        f"{invalid_count} inválidos, de {len(rows)} procesados"
    )


def main() -> None:
    metadata.create_all(engine, checkfirst=True)

    _load_lookup_table(departments, "departments.csv", "department")
    _load_lookup_table(jobs, "jobs.csv", "job")
    _load_hired_employees()

    print(f"\nRegistros inválidos logueados en: app/../logs/invalid_records.log")


if __name__ == "__main__":
    main()
