"""
Integration tests for the ingestion API (app/main.py).

These hit a real database (see conftest.py) through FastAPI's TestClient,
not mocks -- so they exercise the exact same validation, insert, and
duplicate-handling logic the real API runs. As a side effect they append
entries to logs/invalid_records.log, same as a real rejected request would.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ingest_departments_mixed_batch_rejects_only_the_bad_row():
    response = client.post(
        "/departments",
        json={"records": [
            {"id": 1, "department": "Engineering"},
            {"id": 2, "department": ""},
        ]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["inserted"] == 1
    assert body["rejected"] == 1
    assert body["errors"][0]["errors"] == ["missing_required_field:department"]


def test_ingest_departments_duplicate_id_does_not_fail_the_batch():
    client.post("/departments", json={"records": [{"id": 1, "department": "Engineering"}]})

    response = client.post(
        "/departments",
        json={"records": [
            {"id": 1, "department": "Engineering (again)"},
            {"id": 2, "department": "Marketing"},
        ]},
    )
    body = response.json()
    assert body["inserted"] == 1
    assert body["rejected"] == 1
    assert body["errors"][0]["errors"] == ["duplicate_id"]


def test_ingest_hired_employees_requires_valid_department_and_job():
    client.post("/departments", json={"records": [{"id": 1, "department": "Engineering"}]})
    client.post("/jobs", json={"records": [{"id": 1, "job": "Backend Developer"}]})

    response = client.post(
        "/hired_employees",
        json={"records": [
            {"id": 1, "name": "Ada Lovelace", "datetime": "2021-05-01T10:00:00Z",
             "department_id": 1, "job_id": 1},
            {"id": 2, "name": "Bad Dept", "datetime": "2021-05-01T10:00:00Z",
             "department_id": 999, "job_id": 1},
        ]},
    )
    body = response.json()
    assert body["inserted"] == 1
    assert body["rejected"] == 1
    assert body["errors"][0]["errors"] == ["department_id_not_found"]


def test_ingest_hired_employees_rejects_bad_datetime_format():
    client.post("/departments", json={"records": [{"id": 1, "department": "Engineering"}]})
    client.post("/jobs", json={"records": [{"id": 1, "job": "Backend Developer"}]})

    response = client.post(
        "/hired_employees",
        json={"records": [
            {"id": 1, "name": "Ada Lovelace", "datetime": "2021-05-01 10:00:00",
             "department_id": 1, "job_id": 1},
        ]},
    )
    body = response.json()
    assert body["inserted"] == 0
    assert body["errors"][0]["errors"] == ["invalid_datetime_format"]


def test_batch_over_1000_rows_is_rejected():
    records = [{"id": i, "department": f"Dept {i}"} for i in range(1, 1002)]
    response = client.post("/departments", json={"records": records})
    assert response.status_code == 422


def test_empty_batch_is_rejected():
    response = client.post("/departments", json={"records": []})
    assert response.status_code == 422
