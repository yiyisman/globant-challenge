"""
Shared database access (historical migration + API).

SQLAlchemy Core is used (not the declarative ORM) because the tables are
already defined in sql/01_ddl.sql and we don't need full object-relational
mapping: just simple inserts/selects and the 2 aggregation queries from
Challenge #2, which read better as direct SQL/Core.
"""
from __future__ import annotations

import os

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    TIMESTAMP,
    create_engine,
)

# Outside Docker (local venv) the DB is reachable at localhost:5432
# because the port is published in docker-compose.yml. Inside the `api`
# container, docker-compose.yml overrides this variable with host `db`.
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://globant:globant_pw@localhost:5432/globant_challenge",
)

engine = create_engine(DATABASE_URL, future=True)
metadata = MetaData()

departments = Table(
    "departments",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=False),
    Column("department", String(150), nullable=False),
)

jobs = Table(
    "jobs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=False),
    Column("job", String(150), nullable=False),
)

hired_employees = Table(
    "hired_employees",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=False),
    Column("name", String(250), nullable=False),
    Column("datetime", TIMESTAMP(timezone=True), nullable=False),
    Column(
        "department_id",
        Integer,
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "job_id",
        Integer,
        ForeignKey("jobs.id", ondelete="RESTRICT"),
        nullable=False,
    ),
)
