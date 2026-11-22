"""Load the FOCUS 1.0 sample billing file into the local warehouse as raw.focus_charges.

The file is loaded as-is (all columns as the CSV types them). Typing and cleaning
happen in dbt staging, so the raw table is the reconciliation baseline.
"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = ROOT / "data" / "raw" / "focus_sample_100000.csv.gz"
DB = ROOT / "warehouse.duckdb"


def main() -> None:
    con = duckdb.connect(str(DB))
    con.execute("create schema if not exists raw")
    con.execute(
        "create or replace table raw.focus_charges as "
        f"select * from read_csv_auto('{RAW_FILE.as_posix()}', sample_size=-1)"
    )
    n = con.execute("select count(*) from raw.focus_charges").fetchone()[0]
    print(f"loaded {n:,} rows into raw.focus_charges")


if __name__ == "__main__":
    main()
