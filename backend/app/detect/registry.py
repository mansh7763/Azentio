"""Which indicators exist, which tables and columns each needs, and which can run on a given dataset."""

from dataclasses import dataclass

from app.detect.config import RulesConfig
from app.detect.dataset import Dataset


@dataclass(frozen=True)
class Indicator:
    id: str
    requires: tuple[str, ...]
    kind: str  # transfer | login | device | application | mitigation | network
    # "table.column" needed with at least one value; "a.x|b.y" means either is enough (issue #6).
    columns: tuple[str, ...] = ()


_DEVICE = ("logins.device_id",)
REGISTRY: list[Indicator] = [
    *(Indicator(i, ("transactions",), "transfer") for i in ("TX-01", "TX-02", "TX-03", "TX-04", "TX-05", "HV-01",
                                                          "TX-06", "TX-07", "TX-08")),
    Indicator("NW-01", ("transactions",), "network"),
    Indicator("NW-02", ("transactions",), "network"),
    *(Indicator(i, ("logins",), "login", ("logins.outcome",)) for i in ("LG-01", "LG-02", "LG-03")),
    Indicator("DV-03", ("logins",), "login", _DEVICE),
    *(Indicator(i, ("logins",), "device", _DEVICE) for i in ("DV-01", "DV-02", "MT-HOUSE")),
    Indicator("AP-01", ("applications",), "application", ("applications.device_id",)),
    Indicator("AP-02", ("applications",), "application"),
    Indicator("ID-01", ("applications", "customers"), "application", ("applications.phone|applications.email",)),
    Indicator("ID-02", ("applications", "customers"), "application", ("customers.phone|customers.email",)),
    Indicator("AP-03", ("applications", "transactions"), "application",
              ("applications.disbursement_account|transactions.application_id",)),
    *(Indicator(i, ("transactions",), "mitigation") for i in ("MT-PAYEE", "MT-RECUR", "MT-TENURE")),
    Indicator("MT-KNOWN", ("transactions", "logins"), "mitigation", _DEVICE),
]


def _has_column(ds: Dataset, ref: str) -> bool:
    table, column = ref.split(".", 1)
    df = ds.get(table)
    return column in df and df[column].notna().any()


def available(ds: Dataset, cfg: RulesConfig) -> tuple[list[str], dict[str, str]]:
    run, skipped = [], {}
    for ind in REGISTRY:
        missing = [t for t in ind.requires if not ds.has(t)]
        no_column = [ref.replace("|", " or ") for ref in ind.columns
                     if not any(_has_column(ds, option) for option in ref.split("|"))]
        if not cfg.enabled(ind.id):
            skipped[ind.id] = "disabled in rules"
        elif missing:
            skipped[ind.id] = f"missing table: {', '.join(missing)}"
        elif no_column:
            skipped[ind.id] = f"missing column: {', '.join(no_column)}"
        else:
            run.append(ind.id)
    return run, skipped
