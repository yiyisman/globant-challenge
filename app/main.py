"""
Data ingestion REST API (Challenge #1.2).

Endpoints are split per table (departments, jobs, hired_employees) instead
of a single generic one: better typed responses and clearer per-table
error messages (decision already documented in CLAUDE.md).

Reuses app/validators.py -- the same rules the historical migration uses.
Each row's fields arrive as dict[str, Any], deliberately NOT typed to
int/datetime in Pydantic: if Pydantic rejected a row by type ahead of
time, it would fail the whole batch with a 422, violating the requirement
that only the invalid row gets rejected (not the entire request).
validate_record/validate_lookup_record already handle that validation
"by hand" and are the single source of truth for what counts as valid.

Duplicates: an id that already exists in the table is rejected row by row
(it doesn't fail the batch) using Postgres SAVEPOINTs, so the rest of the
batch isn't lost because of one repeated row.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field
from sqlalchemy import Table, select
from sqlalchemy.exc import IntegrityError

from app.analytics import get_departments_above_average, get_hires_by_quarter
from app.db import departments, engine, hired_employees, jobs
from app.invalid_logger import log_invalid_record
from app.validators import validate_lookup_record, validate_record

app = FastAPI(
    title="Globant Data Engineer Challenge API",
    description="Batch ingestion for hired_employees, departments and jobs.",
)

Row = dict[str, Any]


class BatchIn(BaseModel):
    records: list[Row] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Between 1 and 1000 rows per request.",
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


class HiresByQuarterRow(BaseModel):
    department: str
    job: str
    Q1: int
    Q2: int
    Q3: int
    Q4: int


class DepartmentAboveAverageRow(BaseModel):
    id: int
    department: str
    hired: int


@app.get("/analytics/hires_by_quarter", response_model=list[HiresByQuarterRow])
def hires_by_quarter() -> list[dict]:
    """Challenge #2, query 1: 2021 hires by department/job and quarter."""
    return get_hires_by_quarter()


@app.get("/analytics/departments_above_average", response_model=list[DepartmentAboveAverageRow])
def departments_above_average() -> list[dict]:
    """Challenge #2, query 2: departments that hired above the average
    of all departments in 2021."""
    return get_departments_above_average()


def _insert_one_by_one(
    table: Table, clean_rows: list[tuple[Row, dict]]
) -> tuple[int, list[RejectedRecord]]:
    """Inserts each already-validated row in its own SAVEPOINT: if one
    collides on a duplicate id, only that row is dropped and the rest of
    the batch keeps going."""
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
