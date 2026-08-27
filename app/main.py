"""
API REST de ingesta de datos (Challenge #1.2).

Endpoints separados por tabla (departments, jobs, hired_employees) en vez
de uno genérico: mejor tipado de la respuesta y mensajes de error más
claros por tabla (decisión ya documentada en CLAUDE.md).

Reusa app/validators.py -- las mismas reglas que la migración histórica.
Los campos de cada fila se reciben como dict[str, Any], NO tipados a
int/datetime en Pydantic a propósito: si Pydantic rechazara una fila por
tipo antes de tiempo, tumbaría el batch completo con un 422, violando el
requisito de que solo la fila inválida se rechace (no el request entero).
validate_record/validate_lookup_record ya se encargan de esa validación
"a mano" y son la única fuente de verdad sobre qué es un dato válido.

Duplicados: un id que ya existe en la tabla se rechaza fila por fila (no
tumba el batch) usando SAVEPOINTs de Postgres, para no perder el resto del
batch por una sola fila repetida.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field
from sqlalchemy import Table, select
from sqlalchemy.exc import IntegrityError

from app.db import departments, engine, hired_employees, jobs
from app.invalid_logger import log_invalid_record
from app.validators import validate_lookup_record, validate_record

app = FastAPI(
    title="Globant Data Engineer Challenge API",
    description="Ingesta batch para hired_employees, departments y jobs.",
)

Row = dict[str, Any]


class BatchIn(BaseModel):
    records: list[Row] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Entre 1 y 1000 filas por request.",
    )


class RejectedRecord(BaseModel):
    record: Row
    errors: list[str]


class IngestResult(BaseModel):
    inserted: int
    rejected: int
    errors: list[RejectedRecord]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _insert_one_by_one(
    table: Table, clean_rows: list[tuple[Row, dict]]
) -> tuple[int, list[RejectedRecord]]:
    """Inserta cada fila ya validada en su propio SAVEPOINT: si una choca
    por id duplicado, se descarta solo esa fila y el resto del batch sigue."""
    inserted = 0
    rejected: list[RejectedRecord] = []

    with engine.begin() as conn:
        for original, values in clean_rows:
            savepoint = conn.begin_nested()
            try:
                conn.execute(table.insert().values(**values))
                savepoint.commit()
                inserted += 1
            except IntegrityError:
                savepoint.rollback()
                rejected.append(RejectedRecord(record=original, errors=["duplicate_id"]))
                log_invalid_record("api_ingestion", table.name, original, ["duplicate_id"])

    return inserted, rejected


@app.post("/departments", response_model=IngestResult)
def ingest_departments(batch: BatchIn) -> IngestResult:
    return _ingest_lookup(departments, "department", batch.records)


@app.post("/jobs", response_model=IngestResult)
def ingest_jobs(batch: BatchIn) -> IngestResult:
    return _ingest_lookup(jobs, "job", batch.records)


def _ingest_lookup(table: Table, name_field: str, records: list[Row]) -> IngestResult:
    rejected: list[RejectedRecord] = []
    clean_rows: list[tuple[Row, dict]] = []

    for record in records:
        result = validate_lookup_record(record, name_field)
        if not result.is_valid:
            rejected.append(RejectedRecord(record=record, errors=result.errors))
            log_invalid_record("api_ingestion", table.name, record, result.errors)
            continue
        clean_rows.append(
            (record, {"id": int(record["id"]), name_field: str(record[name_field]).strip()})
        )

    inserted, dup_rejected = _insert_one_by_one(table, clean_rows)
    rejected.extend(dup_rejected)
    return IngestResult(inserted=inserted, rejected=len(rejected), errors=rejected)


@app.post("/hired_employees", response_model=IngestResult)
def ingest_hired_employees(batch: BatchIn) -> IngestResult:
    with engine.begin() as conn:
        valid_department_ids = {r[0] for r in conn.execute(select(departments.c.id))}
        valid_job_ids = {r[0] for r in conn.execute(select(jobs.c.id))}

    rejected: list[RejectedRecord] = []
    clean_rows: list[tuple[Row, dict]] = []

    for record in batch.records:
        result = validate_record(record, valid_department_ids, valid_job_ids)
        if not result.is_valid:
            rejected.append(RejectedRecord(record=record, errors=result.errors))
            log_invalid_record("api_ingestion", "hired_employees", record, result.errors)
            continue
        clean_rows.append(
            (
                record,
                {
                    "id": int(record["id"]),
                    "name": record["name"],
                    "datetime": record["datetime"],
                    "department_id": int(record["department_id"]),
                    "job_id": int(record["job_id"]),
                },
            )
        )

    inserted, dup_rejected = _insert_one_by_one(hired_employees, clean_rows)
    rejected.extend(dup_rejected)
    return IngestResult(inserted=inserted, rejected=len(rejected), errors=rejected)
