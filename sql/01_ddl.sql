-- ============================================================
-- DDL del Globant Data Engineer Challenge
--
-- Decisiones de diseño (documentar también en el README):
-- 1. Los ids NO son autoincrementales: vienen de los CSV de origen
--    (son datos migrados, no generados por el sistema). Insertar un
--    id duplicado debe fallar por PK, y eso es intencional.
-- 2. department_id y job_id son NOT NULL: el PDF dice explícitamente
--    que los 5 campos de hired_employees son requeridos.
-- 3. FK con ON DELETE RESTRICT: no queremos borrar un departamento o
--    job "por accidente" si todavía tiene empleados asociados.
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

-- Nota: "datetime" se mantiene igual al nombre del campo en el data
-- dictionary del PDF (no es palabra reservada en Postgres, pero se
-- entrecomilla por claridad). Mantener el mismo nombre en CSV -> API
-- -> DB reduce fricción de mapeo y confusión al revisar el código.

-- Índices pensados para las 2 queries del Challenge #2:
-- ambas filtran por año y agrupan por department/job.
CREATE INDEX IF NOT EXISTS idx_hired_employees_datetime
    ON hired_employees ("datetime");

CREATE INDEX IF NOT EXISTS idx_hired_employees_department_id
    ON hired_employees (department_id);

CREATE INDEX IF NOT EXISTS idx_hired_employees_job_id
    ON hired_employees (job_id);
