# Globant Data Engineer Challenge

A PoC that migrates 3 CSV files into PostgreSQL, exposes a REST API for batch
ingestion with validation, backs up/restores tables to AVRO, and answers two
hiring-analysis queries over SQL.

## Stack

Python 3.11 · FastAPI · SQLAlchemy Core · PostgreSQL 16 · Docker Compose · pytest

## Quick start

```bash
docker compose up -d --build
```

This starts Postgres (applies `sql/01_ddl.sql` on first boot) and the API at
`http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

Load the historical CSVs:

```bash
python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements.txt
python -m app.migration
```

Expected output: `departments: 12 valid out of 12 processed`,
`jobs: 51 valid out of 51 processed`,
`hired_employees: 1920 valid, 200 invalid, out of 2120 processed`.

## Project structure

```
app/
  db.py           SQLAlchemy table definitions + engine
  validators.py   validation rules, shared by migration and API
  invalid_logger.py  JSON-lines logger for rejected records
  migration.py    loads data/*.csv into Postgres
  main.py         FastAPI app (ingestion + analytics endpoints)
  analytics.py    the 2 Challenge #2 SQL queries
  backup.py       AVRO export/import per table
sql/01_ddl.sql    table definitions, applied automatically by Postgres
tests/            pytest suite (needs Postgres running)
data/             the 3 source CSVs
backups/          AVRO backups land here (gitignored)
logs/             invalid_records.log (gitignored)
```

## API

Ingestion endpoints take 1-1000 rows per request. Valid rows are inserted;
invalid rows are rejected individually (they don't fail the whole batch) and
logged to `logs/invalid_records.log`.

```
POST /departments
POST /jobs
POST /hired_employees
GET  /analytics/hires_by_quarter
GET  /analytics/departments_above_average
GET  /health
```

Example request:

```bash
curl -X POST http://localhost:8000/hired_employees \
  -H "Content-Type: application/json" \
  -d '{"records": [
    {"id": 1, "name": "Ada Lovelace", "datetime": "2021-05-01T10:00:00Z", "department_id": 1, "job_id": 1},
    {"id": 2, "name": "Bad Row", "datetime": "not-a-date", "department_id": 1, "job_id": 1}
  ]}'
```

Response:

```json
{
  "inserted": 1,
  "rejected": 1,
  "errors": [
    {"record": {"id": 2, "name": "Bad Row", ...}, "errors": ["invalid_datetime_format"]}
  ]
}
```

## Validation rules

`hired_employees`: `id`, `name`, `datetime`, `department_id`, `job_id` are all
required. `datetime` must be ISO 8601 with a `Z` suffix
(`2021-07-27T16:02:08Z`). `department_id`/`job_id` must reference existing
rows. `departments`/`jobs`: `id` and their name field are required.

Same rules apply whether the data comes from the historical CSV migration or
the API — both call `app/validators.py`.

## Backup and restore

```bash
python -m app.backup backup  <departments|jobs|hired_employees|all>
python -m app.backup restore <departments|jobs|hired_employees|all>
```

Restore is a full replace, not a merge: it deletes the table's current rows
and reinserts what's in the AVRO file, in one transaction. If another table
has a foreign key into the one you're restoring (e.g. `hired_employees` ->
`departments`), Postgres blocks the delete — restore/clear the dependent
table first.

## Tests

```bash
docker compose up -d db
pytest tests/ -v
```

12 tests: API ingestion (mixed batches, duplicates, batch size limits),
analytics queries against a hand-seeded dataset, and a full backup/restore
cycle. `tests/conftest.py` creates its own `globant_challenge_test` database
inside the same Postgres instance and drops it afterward — it never touches
`globant_challenge`.

CI runs the same suite on every push (`.github/workflows/tests.yml`), against
a native Postgres service.

## Assumptions and design decisions

- Ids are not auto-generated; they come from the CSVs and are preserved as-is.
  A duplicate id fails on the primary key on purpose.
- `department_id`/`job_id` are `NOT NULL` — the PDF states all 5
  `hired_employees` fields are required, unlike some public versions of this
  challenge that allow nulls there.
- Foreign keys use `ON DELETE RESTRICT`: you can't delete a department or job
  that still has employees attached to it.
- Ingestion is split into 3 endpoints (one per table) instead of one generic
  endpoint, for clearer per-table error messages and response typing.
- Rejected records are appended to a log file, not a separate database table
  — the requirement is "must be logged," and a full audit table would be
  more machinery than this needs.
- Row-level validation is done by hand in `validators.py`, not via strict
  Pydantic models. If Pydantic rejected a row by type, FastAPI would fail the
  *entire batch* with a 422 — but only the bad row should be rejected.

## Known limitations

No authentication on the API — anything with network access to it can read
or write data. No HTTPS. Postgres credentials are plaintext in
`docker-compose.yml`. Single Postgres instance, no replicas or automated
backups. None of this is hidden or accidental; it's out of scope for a PoC,
but would need to be addressed before this ran anywhere but a laptop.
