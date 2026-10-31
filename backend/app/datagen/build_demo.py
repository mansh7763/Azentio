"""Build the demo files from the labelled golden scenarios: one source system per format, plus a dirty upload.

Run from backend/ after golden data changes: python -m app.datagen.build_demo
"""

import csv
import io
from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).resolve().parents[2]
GOLDEN = BACKEND / "tests" / "golden"
OUT = Path(__file__).resolve().parent / "demo"

# Different column names from our schema, as another system would export them.
DIRTY_HEADER = ["Transaction ID", "From Account", "To Account", "Txn Date", "Amount", "Currency", "Status", "Branch"]
DIRTY_ROWS = [
    ["00917", "A-C001", "SUP-1", "2026-10-20T09:00:00Z", "₹2,00,000", "INR", "success", "MUM"],  # valid, leading zeros kept
    ["D-02", "A-C002", "B-77", "2026-10-20T09:05:00Z", "1500", "INR", "success", "MUM"],         # valid
    ["D-03", "A-UNKNOWN", "B-77", "2026-10-20T09:10:00Z", "1500", "INR", "success", "DEL"],      # valid, unknown account warns
    ["D-04", "A-C001", "B-77", "20/10/2026", "1500", "INR", "success", "DEL"],                   # ambiguous date
    ["D-05", "A-C001", "B-77", "2026-10-20T09:20:00Z", "", "INR", "success", "DEL"],             # missing amount
    ["D-06", "A-C001", "B-77", "2026-10-20T09:25:00Z", "-250", "INR", "success", "DEL"],         # negative amount
    ["D-07", "A-C001", "B-77", "2026-10-20T09:30:00Z", "twelve", "INR", "success", "DEL"],       # not a number
    ["", "A-C001", "B-77", "2026-10-20T09:35:00Z", "1500", "INR", "success", "DEL"],             # missing ID
    ["D-02", "A-C002", "B-77", "2026-10-20T09:05:00Z", "1500", "INR", "success", "MUM"],         # exact duplicate of D-02
    ["D-02", "A-C002", "B-77", "2026-10-20T09:05:00Z", "9900", "INR", "success", "MUM"],         # same ID, different data
]


def _rows(name: str) -> pd.DataFrame:
    return pd.read_csv(GOLDEN / f"{name}.csv", dtype=str, keep_default_na=False)


def excel_bytes(frame: pd.DataFrame, sheet: str) -> bytes:
    buffer = io.BytesIO()
    frame.to_excel(buffer, index=False, sheet_name=sheet)
    return buffer.getvalue()


def json_bytes(frame: pd.DataFrame) -> bytes:
    return frame.replace({"": None}).to_json(orient="records", indent=1).encode()


def build() -> None:
    (OUT / "dirty").mkdir(parents=True, exist_ok=True)
    for name in ("customers", "accounts", "applications", "claims"):
        (OUT / f"{name}.csv").write_bytes((GOLDEN / f"{name}.csv").read_bytes())
    (OUT / "transactions.xlsx").write_bytes(excel_bytes(_rows("transactions"), "transactions"))
    (OUT / "logins.json").write_bytes(json_bytes(_rows("logins")))
    with open(OUT / "dirty" / "transactions_dirty.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(DIRTY_HEADER)
        writer.writerows(DIRTY_ROWS)


if __name__ == "__main__":
    build()
