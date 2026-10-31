"""Rule configuration: defaults from rules.yaml with overrides merged on top."""

import copy
import hashlib
import json
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

RULES_FILE = Path(__file__).resolve().parent / "rules.yaml"

# Parameters each indicator reads. A missing key is a config error, never a silent fallback to a code default
# that may differ from rules.yaml (issue #6).
REQUIRED_PARAMS: dict[str, set[str]] = {
    "TX-01": {"z_min"}, "TX-02": {"median_multiple"}, "TX-04": {"count", "minutes"}, "TX-05": {"new_payees", "hours"},
    "TX-06": {"windows_hours", "quantile", "min_windows", "min_ratio"}, "TX-07": {"count", "hours", "low", "high", "min_z"},
    "TX-08": {"dormant_days", "observed_days", "follow_days"},
    "TX-09": {"share", "hours", "min_payees"},
    "HV-01": {"quantile", "min_samples"}, "DV-01": {"min_customers", "days"}, "LG-01": {"failures"},
    "AP-01": {"min_applicants", "window_hours"}, "AP-02": {"count", "days"}, "AP-03": {"share", "hours"}, "AP-04": {"min_applicants", "days"},
    "NW-01": {"min_payers", "hours", "established_payers"}, "NW-02": {"max_hops", "hours", "tolerance"},
    "MT-PAYEE": {"min_prior", "tolerance"}, "MT-RECUR": {"min_prior", "cadence_days", "slack_days"},
    "MT-TENURE": {"days"},
}
MAX_WEIGHT = 0.70  # no single indicator may reach High on its own


class IndicatorConfig(BaseModel):
    weight: float
    enabled: bool = True
    params: dict = Field(default_factory=dict)


class Bands(BaseModel):
    medium: int = 40
    high: int = 70


class Floors(BaseModel):
    ato_full: int = 85
    ato_movement: int = 70
    ato_partial: int = 55
    loan_mule: int = 80


class Windows(BaseModel):
    # Defaults equal rules.yaml, so a missing key cannot silently change a rule (issue #6).
    chain_hours: float = 0.5
    link_minutes: float = 30
    burst_minutes: float = 10
    success_after_burst_minutes: float = 30


class RulesConfig(BaseModel):
    indicators: dict[str, IndicatorConfig]
    mitigations: dict[str, IndicatorConfig]
    bands: Bands = Bands()
    floors: Floors = Floors()
    windows: Windows = Windows()
    min_history: int = 5
    floor_amount: float = 100

    @model_validator(mode="after")
    def _check(self) -> "RulesConfig":
        problems = []
        for indicator_id, item in {**self.indicators, **self.mitigations}.items():
            missing = REQUIRED_PARAMS.get(indicator_id, set()) - set(item.params)
            if missing:
                problems.append(f"{indicator_id} is missing params: {', '.join(sorted(missing))}")
            if indicator_id in self.indicators and item.weight >= MAX_WEIGHT:
                problems.append(f"{indicator_id} weight {item.weight} must stay below {MAX_WEIGHT}")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def version(self) -> str:
        blob = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:12]

    def weight(self, indicator_id: str) -> float:
        item = self.indicators.get(indicator_id) or self.mitigations.get(indicator_id)
        return item.weight if item and item.enabled else 0.0

    def params(self, indicator_id: str) -> dict:
        item = self.indicators.get(indicator_id) or self.mitigations.get(indicator_id)
        return item.params if item else {}

    def enabled(self, indicator_id: str) -> bool:
        item = self.indicators.get(indicator_id) or self.mitigations.get(indicator_id)
        return bool(item and item.enabled)


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_rules(overrides: dict | None = None) -> RulesConfig:
    defaults = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    return RulesConfig.model_validate(_deep_merge(defaults, overrides or {}))
