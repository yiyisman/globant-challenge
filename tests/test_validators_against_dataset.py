"""
Smoke test: runs the validator against the synthetic dataset in /data
and confirms the invalid count matches dataset_summary.md (200 out of
2120 rows). Doesn't require Postgres -- it's a pure test of the
validation module in isolation.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.validators import validate_record  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def load_ids(filename: str) -> set[int]:
    with open(DATA_DIR / filename, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {int(row["id"]) for row in reader}


def main() -> None:
    dept_ids = load_ids("departments.csv")
    job_ids = load_ids("jobs.csv")

    valid_count = 0
    invalid_count = 0
    error_breakdown: dict[str, int] = {}

    with open(DATA_DIR / "hired_employees.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            result = validate_record(row, dept_ids, job_ids)
            if result.is_valid:
                valid_count += 1
            else:
                invalid_count += 1
                for err in result.errors:
                    error_breakdown[err] = error_breakdown.get(err, 0) + 1

    print(f"Valid:   {valid_count}")
    print(f"Invalid: {invalid_count}")
    print("\nError breakdown:")
    for err, count in sorted(error_breakdown.items()):
        print(f"  {err}: {count}")


if __name__ == "__main__":
    main()
