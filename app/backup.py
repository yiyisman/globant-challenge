"""
Backup y restore por tabla en formato AVRO (Challenge #1, puntos 4 y 5).

Cada tabla se exporta a su propio archivo backups/<tabla>.avro con todas
sus filas actuales. El schema AVRO se genera a partir de las columnas ya
definidas en app/db.py (que a su vez reflejan sql/01_ddl.sql), así que si
el DDL cambia, el backup lo sigue automáticamente.

Restore es un reemplazo completo: borra las filas actuales de la tabla y
reinserta lo que hay en el AVRO, todo en una sola transacción (si algo
falla, no se pierde nada de lo que ya estaba). Si otra tabla depende de
esta por FK (ej. hired_employees depende de departments), Postgres va a
rechazar el borrado -- es el mismo ON DELETE RESTRICT ya documentado en
sql/01_ddl.sql, y es intencional: hay que restaurar/vaciar primero la
tabla dependiente (hired_employees) antes de restaurar departments o jobs.

Uso:
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
    """Exporta la tabla completa a backups/<table_name>.avro."""
    table = TABLES[table_name]
    schema = _avro_schema(table)

    with engine.connect() as conn:
        records = [dict(row) for row in conn.execute(select(table)).mappings()]

    backup_path = BACKUP_DIR / f"{table_name}.avro"
    with open(backup_path, "wb") as f:
        fastavro.writer(f, schema, records)

    return backup_path


def restore_table(table_name: str) -> int:
    """Reemplaza el contenido de la tabla con lo que hay en su backup AVRO."""
    table = TABLES[table_name]
    backup_path = BACKUP_DIR / f"{table_name}.avro"
    if not backup_path.exists():
        raise FileNotFoundError(f"No existe backup para '{table_name}': {backup_path}")

    with open(backup_path, "rb") as f:
        records = list(fastavro.reader(f))

    with engine.begin() as conn:
        conn.execute(table.delete())
        if records:
            conn.execute(table.insert(), records)

    return len(records)


def _main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in ("backup", "restore"):
        print("Uso: python -m app.backup backup|restore <departments|jobs|hired_employees|all>")
        sys.exit(1)

    action, target = sys.argv[1], sys.argv[2]
    if target != "all" and target not in TABLES:
        print(f"Tabla desconocida: {target}. Opciones: {list(TABLES)} o 'all'")
        sys.exit(1)

    targets = list(TABLES.keys()) if target == "all" else [target]

    for name in targets:
        if action == "backup":
            path = backup_table(name)
            print(f"{name}: backup escrito en {path}")
        else:
            count = restore_table(name)
            print(f"{name}: {count} filas restauradas")


if __name__ == "__main__":
    _main()
