-- ============================================================
-- DDL for the Globant Data Engineer Challenge
--
-- Design decisions (also documented in the README):
-- 1. Ids are NOT auto-incremented: they come from the source CSV files
--    (this is migrated data, not system-generated). Inserting a
--    duplicate id must fail on the PK, and that's intentional.
-- 2. department_id and job_id are NOT NULL: the PDF explicitly states
--    that all 5 hired_employees fields are required.
-- 3. FK with ON DELETE RESTRICT: we don't want to accidentally delete a
--    department or job that still has employees attached to it.
-- ============================================================

CREATE TABLE IF NOT EXISTS departments (
    id          INTEGER PRIMARY KEY,
    department  VARCHAR(150) NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id   INTEGER PRIMARY KEY,
    job  VARCHAR(150) NOT NULL
);

CREATE TABLE IF NOT EXISTS hired_employees (
    id             INTEGER PRIMARY KEY,
    name           VARCHAR(250) NOT NULL,
    "datetime"     TIMESTAMPTZ NOT NULL,
    department_id  INTEGER NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    job_id         INTEGER NOT NULL REFERENCES jobs(id) ON DELETE RESTRICT
);

-- Note: "datetime" keeps the same name as the field in the PDF's data
-- dictionary (it's not a reserved word in Postgres, but it's quoted for
-- clarity). Keeping the same name across CSV -> API -> DB reduces
-- mapping friction and confusion when reviewing the code.

-- Indexes designed for the 2 Challenge #2 queries: both filter by year
-- and group by department/job.
CREATE INDEX IF NOT EXISTS idx_hired_employees_datetime
    ON hired_employees ("datetime");

CREATE INDEX IF NOT EXISTS idx_hired_employees_department_id
    ON hired_employees (department_id);

CREATE INDEX IF NOT EXISTS idx_hired_employees_job_id
    ON hired_employees (job_id);
