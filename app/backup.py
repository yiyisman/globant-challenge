"""
Per-table AVRO backup and restore (Challenge #1, points 4 and 5).

Each table is exported to its own backups/<table>.avro file with all of
its current rows. The AVRO schema is generated from the columns already
defined in app/db.py (which in turn reflect sql/01_ddl.sql), so if the
DDL changes, the backup follows automatically.

Restore is a full replace: it deletes the table's current rows and
reinserts what's in the AVRO file, all in a single transaction (if
anything fails, nothing that was already there is lost). If another
table depends on this one via FK (e.g. hired_employees depends on
departments), Postgres will reject the delete -- that's the same
ON DELETE RESTRICT already documented in sql/01_ddl.sql, and it's
intentional: the dependent table (hired_employees) needs to be
restored/cleared first before restoring departments or jobs.

Usage:
    python -m app.backup backup  departments|jobs|hired_employees|all
    python -m app.backup restore departments|jobs|hired_employees|all
"""
from __future__ import annotations

import sys
from pathlib import Path

import fastavro
from sqlalchemy import Table, select

from app.db import departments, engine, hired_employees, jobs

BACKUP_DIR = Path(__file__).resolve().parents[1] / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

TABLES: dict[str, Table] = {
    "departments": departments,
    "jobs": jobs,
    "hired_employees": hired_employees,
}


def _avro_schema(table: Table) -> dict:
    fields = []
    for column in table.columns:
        if column.name == "datetime":
            field_type = {"type": "long", "logicalType": "timestamp-micros"}
        elif column.type.python_type is int:
            field_type = "long"
        else:
            field_type = "string"
        fields.append({"name": column.name, "type": field_type})
    return {"type": "record", "name": table.name, "fields": fields}


def backup_table(table_name: str) -> Path:
    """Exports the full table to backups/<table_name>.avro."""
    table = TABLES[table_name]
    schema = _avro_schema(table)

    with engine.connect() as conn:
        records = [dict(row) for row in conn.execute(select(table)).mappings()]

    backup_path = BACKUP_DIR / f"{table_name}.avro"
    with open(backup_path, "wb") as f:
        fastavro.writer(f, schema, records)

    return backup_path


def restore_table(table_name: str) -> int:
    """Replaces the table's content with what's in its AVRO backup."""
    table = TABLES[table_name]
    backup_path = BACKUP_DIR / f"{table_name}.avro"
    if not backup_path.exists():
        raise FileNotFoundError(f"No backup found for '{table_name}': {backup_path}")

    with open(backup_path, "rb") as f:
        records = list(fastavro.reader(f))

    with engine.begin() as conn:
        conn.execute(table.delete())
        if records:
            conn.execute(table.insert(), records)

    return len(records)


def _main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in ("backup", "restore"):
        print("Usage: python -m app.backup backup|restore <departments|jobs|hired_employees|all>")
        sys.exit(1)

    action, target = sys.argv[1], sys.argv[2]
    if target != "all" and target not in TABLES:
        print(f"Unknown table: {target}. Options: {list(TABLES)} or 'all'")
        sys.exit(1)

    targets = list(TABLES.keys()) if target == "all" else [target]

    for name in targets:
        if action == "backup":
            path = backup_table(name)
            print(f"{name}: backup written to {path}")
        else:
            count = restore_table(name)
            print(f"{name}: {count} rows restored")


if __name__ == "__main__":
    _main()
