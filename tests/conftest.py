"""
Shared pytest fixtures.

Tests that touch the database point at a dedicated `globant_challenge_test`
database inside the same Postgres server -- never the real
`globant_challenge` database migration.py loads. This has to happen before
any app module is imported, since app/db.py reads DATABASE_URL once, at
import time, to build its engine.

Requires Postgres to be running (`docker compose up -d db`). Tests that
don't need a database (e.g. test_validators_against_dataset.py) work fine
without it.
"""
from __future__ import annotations

import os

_BASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://globant:globant_pw@localhost:5432/globant_challenge"
)
_TEST_DB_NAME = "globant_challenge_test"
_TEST_URL = _BASE_URL.rsplit("/", 1)[0] + "/" + _TEST_DB_NAME
os.environ["DATABASE_URL"] = _TEST_URL

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402


def _admin_url() -> str:
    # Connect to the default `postgres` maintenance database to be able to
    # DROP/CREATE the test database itself (can't drop/create a database
    # you're currently connected to).
    return _BASE_URL.rsplit("/", 1)[0] + "/postgres"


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Creates a fresh globant_challenge_test database for the whole test
    session, applies the schema, and drops it again at the end."""
    admin = create_engine(_admin_url(), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {_TEST_DB_NAME}"))
        conn.execute(text(f"CREATE DATABASE {_TEST_DB_NAME}"))
    admin.dispose()

    from app.db import engine, metadata

    metadata.create_all(engine)

    yield

    engine.dispose()
    admin = create_engine(_admin_url(), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {_TEST_DB_NAME}"))
    admin.dispose()


@pytest.fixture(autouse=True)
def clean_tables():
    """Empties all 3 tables after every test, so tests don't leak state
    into each other. Order matters because of the FK from hired_employees."""
    yield
    from app.db import departments, engine, hired_employees, jobs

    with engine.begin() as conn:
        conn.execute(hired_employees.delete())
        conn.execute(departments.delete())
        conn.execute(jobs.delete())
