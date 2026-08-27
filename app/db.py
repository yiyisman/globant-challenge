"""
Acceso a base de datos compartido (migración histórica + API).

Se usa SQLAlchemy Core (no ORM declarativo) porque las tablas ya están
definidas en sql/01_ddl.sql y no necesitamos mapeo objeto-relacional
completo: solo inserts/selects simples y las 2 queries de agregación
del Challenge #2, que se escriben mejor como SQL/Core directo.
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

# Fuera de Docker (venv local) la DB se ve en localhost:5432 porque el
# puerto está publicado en docker-compose.yml. Dentro del contenedor
# `api`, docker-compose.yml sobreescribe esta variable con host `db`.
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
