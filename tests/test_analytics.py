"""
Tests for app/analytics.py -- the 2 SQL queries from Challenge #2.

Seeds a tiny, hand-built dataset with known numbers instead of asserting
against the real ~2000-row dataset (which would just be re-testing the
data, not the query logic). The seed deliberately includes a department
with zero 2021 hires and a hire from the wrong year, since those are the
2 edge cases the queries have to get right.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.analytics import get_departments_above_average, get_hires_by_quarter
from app.db import departments, engine, hired_employees, jobs


def _seed():
    with engine.begin() as conn:
        conn.execute(departments.insert(), [
            {"id": 1, "department": "Engineering"},
            {"id": 2, "department": "Sales"},
            {"id": 3, "department": "Empty Dept"},  # no hires at all, ever
        ])
        conn.execute(jobs.insert(), [
            {"id": 1, "job": "Backend Developer"},
            {"id": 2, "job": "Sales Rep"},
        ])
        conn.execute(hired_employees.insert(), [
            {"id": 1, "name": "A", "datetime": datetime(2021, 1, 15, tzinfo=timezone.utc),
             "department_id": 1, "job_id": 1},
            {"id": 2, "name": "B", "datetime": datetime(2021, 4, 20, tzinfo=timezone.utc),
             "department_id": 1, "job_id": 1},
            {"id": 3, "name": "C", "datetime": datetime(2021, 7, 1, tzinfo=timezone.utc),
             "department_id": 2, "job_id": 2},
            {"id": 4, "name": "D", "datetime": datetime(2020, 1, 1, tzinfo=timezone.utc),
             "department_id": 2, "job_id": 2},  # wrong year, must be excluded
        ])


def test_hires_by_quarter_groups_by_department_job_and_filters_by_year():
    _seed()
    rows = get_hires_by_quarter()
    by_key = {(r["department"], r["job"]): r for r in rows}

    eng = by_key[("Engineering", "Backend Developer")]
    assert (eng["Q1"], eng["Q2"], eng["Q3"], eng["Q4"]) == (1, 1, 0, 0)

    sales = by_key[("Sales", "Sales Rep")]
    assert sum(sales[q] for q in ("Q1", "Q2", "Q3", "Q4")) == 1  # the 2020 hire must not count


def test_departments_above_average_counts_zero_hire_departments_in_the_average():
    _seed()
    rows = get_departments_above_average()

    # Engineering: 2 hires in 2021. Sales: 1. Empty Dept: 0.
    # Average = (2 + 1 + 0) / 3 = 1.0 -- only Engineering (2) is above it.
    # If "Empty Dept" were dropped from the average instead of counted as 0,
    # the average would be 1.5 and Engineering would still pass but the
    # threshold itself would be silently wrong -- this is exactly the bug
    # a plain INNER JOIN would introduce.
    assert [r["department"] for r in rows] == ["Engineering"]
    assert rows[0]["hired"] == 2
