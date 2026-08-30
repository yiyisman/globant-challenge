"""
Tests for app/backup.py -- AVRO backup and restore.

Uses pytest's tmp_path fixture as the backup directory (via monkeypatch),
so these tests never touch the project's real backups/ folder.
"""
from __future__ import annotations

import pytest

from app.backup import backup_table, restore_table
from app.db import departments, engine


def _seed_departments():
    with engine.begin() as conn:
        conn.execute(departments.insert(), [
            {"id": 1, "department": "Engineering"},
            {"id": 2, "department": "Sales"},
        ])


def test_backup_then_restore_recovers_deleted_rows(tmp_path, monkeypatch):
    monkeypatch.setattr("app.backup.BACKUP_DIR", tmp_path)
    _seed_departments()

    backup_table("departments")
    assert (tmp_path / "departments.avro").exists()

    with engine.begin() as conn:
        conn.execute(departments.delete())
    with engine.connect() as conn:
        assert conn.execute(departments.select()).fetchall() == []

    restored_count = restore_table("departments")
    assert restored_count == 2

    with engine.connect() as conn:
        rows = {row.id: row.department for row in conn.execute(departments.select())}
    assert rows == {1: "Engineering", 2: "Sales"}


def test_restore_without_a_backup_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("app.backup.BACKUP_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        restore_table("jobs")
