"""The engine's input: canonical tables as pandas DataFrames, and their preparation."""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from app.detect.config import RulesConfig

TABLES = ("customers", "accounts", "transactions", "logins", "applications", "claims")
ID_COLUMN = {
    "customers": "customer_id", "accounts": "account_id", "transactions": "txn_id",
    "logins": "event_id", "applications": "application_id", "claims": "claim_id",
}
TIME_COLUMNS = {
    "customers": ["onboarding_date"], "accounts": ["open_date"], "transactions": ["timestamp"],
    "logins": ["timestamp"], "applications": ["timestamp"], "claims": ["incident_date", "timestamp"],
}
AMOUNT_COLUMNS = {"transactions": ["amount"], "accounts": ["balance"], "applications": ["amount"], "claims": ["amount"]}
EVENT_TABLES = ("transactions", "logins", "applications", "claims")
_NOT_NUMBER = re.compile(r"[^\d.\-]")
INBOUND_TYPES = {"credit", "inbound", "deposit", "incoming", "refund", "salary_credit", "loan_disbursement", "disbursement"}


def is_inbound(kind) -> bool:
    return isinstance(kind, str) and kind.lower() in INBOUND_TYPES


@dataclass
class Dataset:
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)

    def has(self, name: str) -> bool:
        df = self.frames.get(name)
        return df is not None and not df.empty

    def get(self, name: str) -> pd.DataFrame:
        df = self.frames.get(name)
        return df if df is not None else pd.DataFrame()

    @classmethod
    def from_frames(cls, **frames: pd.DataFrame) -> "Dataset":
        return cls({k: v for k, v in frames.items() if v is not None})

    @classmethod
    def from_csv_dir(cls, path: str | Path) -> "Dataset":
        path = Path(path)
        frames = {}
        for name in TABLES:
            file = path / f"{name}.csv"
            if file.exists():
                frames[name] = pd.read_csv(file, dtype=str, keep_default_na=False).replace({"": None})
        return cls(frames)


def _parse_amount(series: pd.Series, label: str) -> pd.Series:
    def one(value, row):
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = _NOT_NUMBER.sub("", str(value))
        try:
            return float(cleaned)
        except ValueError:
            raise ValueError(f"{label}: cannot parse '{value}' in row {row + 1}") from None

    return pd.Series([one(v, i) for i, v in enumerate(series)], index=series.index, dtype="float64")


def _login_id(row) -> str:
    key = f"{row.get('customer_id')}|{row.get('timestamp')}|{row.get('device_id')}|{row.get('outcome')}"
    return "L-" + hashlib.sha256(key.encode()).hexdigest()[:12]


def _link_devices(txns: pd.DataFrame, logins: pd.DataFrame, minutes: float) -> pd.DataFrame:
    """Give each transaction the device of the customer's last successful login within `minutes` before it."""
    if "device_id" not in txns:
        txns["device_id"] = None
    txns["device_link"] = txns["device_id"].map(lambda d: "given" if pd.notna(d) and d else None)
    if logins.empty or "device_id" not in logins:
        return txns
    ok = logins[(logins["outcome"].str.lower() == "success") & logins["device_id"].notna()]
    ok = ok[["customer_id", "timestamp", "device_id"]].rename(columns={"device_id": "_dev", "timestamp": "_lt"})
    need = txns["device_link"].isna() & txns["customer_id"].notna()
    if ok.empty or not need.any():
        return txns
    left = txns.loc[need, ["customer_id", "timestamp"]].reset_index().sort_values("timestamp")
    left["customer_id"] = left["customer_id"].astype(object)
    ok = ok.assign(customer_id=ok["customer_id"].astype(object))
    merged = pd.merge_asof(left, ok.sort_values("_lt"), left_on="timestamp", right_on="_lt", by="customer_id",
                           direction="backward", tolerance=pd.Timedelta(minutes=minutes))
    merged = merged.set_index("index")
    found = merged["_dev"].notna()
    txns.loc[merged.index[found], "device_id"] = merged.loc[found, "_dev"]
    txns.loc[merged.index[found], "device_link"] = "derived"
    return txns


def prepare(ds: Dataset, cfg: RulesConfig) -> Dataset:
    """Types, UTC timestamps, (timestamp, id) order, derived links. Returns a new Dataset."""
    frames = {name: df.copy() for name, df in ds.frames.items() if df is not None}

    if "logins" in frames and not frames["logins"].empty:
        lg = frames["logins"]
        if "event_id" not in lg:
            lg["event_id"] = None
        missing = lg["event_id"].isna() | (lg["event_id"].astype(str) == "")
        lg.loc[missing, "event_id"] = lg[missing].apply(_login_id, axis=1)

    for name, df in frames.items():
        if df.empty:
            continue
        for col in TIME_COLUMNS.get(name, []):
            if col in df:
                df[col] = pd.to_datetime(df[col], utc=True, format="mixed")
        for col in AMOUNT_COLUMNS.get(name, []):
            if col in df:
                df[col] = _parse_amount(df[col], f"{name}.{col}")
        for col in df.columns:
            if col.endswith("_id") or col in ("sender_account", "beneficiary_account", "disbursement_account"):
                df[col] = df[col].map(lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))

    for name in EVENT_TABLES:
        df = frames.get(name)
        if df is None or df.empty:
            continue
        time_col = "timestamp" if "timestamp" in df else "incident_date"
        df = df.sort_values([time_col, ID_COLUMN[name]], kind="mergesort").reset_index(drop=True)
        df["seq"] = range(len(df))
        frames[name] = df

    txns = frames.get("transactions")
    if txns is not None and not txns.empty:
        if "customer_id" not in txns:
            txns["customer_id"] = None
        accounts = frames.get("accounts")
        if accounts is not None and not accounts.empty:
            owner = dict(zip(accounts["account_id"], accounts["customer_id"]))
            kinds = txns["type"] if "type" in txns else pd.Series([None] * len(txns), index=txns.index)
            # Exact account links only: an outgoing transfer belongs to the sender's owner, an incoming credit
            # (salary, refund) to the receiver's owner. Unknown accounts stay unresolved (None), never guessed.
            txns["customer_id"] = [
                c if isinstance(c, str) and c else owner.get(b if is_inbound(k) else s)
                for c, s, b, k in zip(txns["customer_id"], txns["sender_account"], txns["beneficiary_account"], kinds)
            ]
            txns["customer_id"] = txns["customer_id"].astype(object).where(txns["customer_id"].map(lambda v: isinstance(v, str)), None)
        frames["transactions"] = _link_devices(txns, frames.get("logins", pd.DataFrame()), cfg.windows.link_minutes)

    return Dataset(frames)
