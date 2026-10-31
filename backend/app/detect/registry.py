"""Which indicators exist, which tables each needs, and which can run on a given dataset."""

from dataclasses import dataclass

from app.detect.config import RulesConfig
from app.detect.dataset import Dataset


@dataclass(frozen=True)
class Indicator:
    id: str
    requires: tuple[str, ...]
    kind: str  # transfer | login | device | application | mitigation


REGISTRY: list[Indicator] = [
    *(Indicator(i, ("transactions",), "transfer") for i in ("TX-01", "TX-02", "TX-03", "TX-04", "TX-05", "HV-01")),
    *(Indicator(i, ("logins",), "login") for i in ("LG-01", "LG-02", "LG-03", "DV-03")),
    *(Indicator(i, ("logins",), "device") for i in ("DV-01", "DV-02", "MT-HOUSE")),
    *(Indicator(i, ("applications",), "application") for i in ("AP-01", "AP-02")),
    Indicator("ID-01", ("applications", "customers"), "application"),
    *(Indicator(i, ("transactions",), "mitigation") for i in ("MT-PAYEE", "MT-RECUR", "MT-TENURE")),
    Indicator("MT-KNOWN", ("transactions", "logins"), "mitigation"),
]


def available(ds: Dataset, cfg: RulesConfig) -> tuple[list[str], dict[str, str]]:
    run, skipped = [], {}
    for ind in REGISTRY:
        missing = [t for t in ind.requires if not ds.has(t)]
        if not cfg.enabled(ind.id):
            skipped[ind.id] = "disabled in rules"
        elif missing:
            skipped[ind.id] = f"missing table: {', '.join(missing)}"
        else:
            run.append(ind.id)
    return run, skipped
