"""Run the whole pipeline from a clean checkout: load raw, dbt seed/run/test,
anomaly check, findings. Exits non-zero if any step fails."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def step(args: list[str]) -> None:
    print("\n$ " + " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def dbt(*args: str) -> list[str]:
    return [PY, "-m", "dbt.cli.main", *args, "--profiles-dir", "."]


if __name__ == "__main__":
    step([PY, "scripts/load_raw.py"])
    step(dbt("seed"))
    step(dbt("run"))
    step(dbt("test"))
    step([PY, "scripts/detect_anomalies.py"])
    step([PY, "scripts/findings.py"])
