"""
The 2 analysis queries from Challenge #2 (SQL + API).

Both only consider 2021 and only valid records. That second filter comes
for free: hired_employees only ever contains rows that already passed
validate_record (Challenge #1) -- invalid ones are never inserted, so
there's no need to filter "valid" separately in this SQL.
"""
from __future__ import annotations

from sqlalchemy import text

from app.db import engine

_HIRES_BY_QUARTER_SQL = text(
    """
    SELECT
        d.department AS department,
        j.job AS job,
        COUNT(*) FILTER (WHERE EXTRACT(QUARTER FROM he.datetime) = 1) AS "Q1",
        COUNT(*) FILTER (WHERE EXTRACT(QUARTER FROM he.datetime) = 2) AS "Q2",
        COUNT(*) FILTER (WHERE EXTRACT(QUARTER FROM he.datetime) = 3) AS "Q3",
        COUNT(*) FILTER (WHERE EXTRACT(QUARTER FROM he.datetime) = 4) AS "Q4"
    FROM hired_employees he
    JOIN departments d ON d.id = he.department_id
    JOIN jobs j ON j.id = he.job_id
    WHERE EXTRACT(YEAR FROM he.datetime) = 2021
    GROUP BY d.department, j.job
    ORDER BY d.department ASC, j.job ASC
    """
)

# LEFT JOIN on purpose (not INNER), and the year filter lives inside the
# ON clause instead of a separate WHERE: this way a department with zero
# hires in 2021 still counts as "hired = 0" for the average, instead of
# disappearing from the count -- which would skew the average upward and
# be technically wrong against "the average of ALL departments".
_DEPARTMENTS_ABOVE_AVERAGE_SQL = text(
    """
    WITH hires_2021 AS (
        SELECT d.id AS id, d.department AS department, COUNT(he.id) AS hired
        FROM departments d
        LEFT JOIN hired_employees he
            ON he.department_id = d.id
            AND EXTRACT(YEAR FROM he.datetime) = 2021
        GROUP BY d.id, d.department
    )
    SELECT id, department, hired
    FROM hires_2021
    WHERE hired > (SELECT AVG(hired) FROM hires_2021)
    ORDER BY hired DESC
    """
)


def get_hires_by_quarter() -> list[dict]:
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(_HIRES_BY_QUARTER_SQL).mappings()]


def get_departments_above_average() -> list[dict]:
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(_DEPARTMENTS_ABOVE_AVERAGE_SQL).mappings()]
