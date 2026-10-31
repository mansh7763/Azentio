"""Rule configuration: defaults from rules.yaml with overrides merged on top."""

import copy
import hashlib
import json
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

RULES_FILE = Path(__file__).resolve().parent / "rules.yaml"


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
    chain_hours: float = 24
    link_minutes: float = 30
    burst_minutes: float = 15
    success_after_burst_minutes: float = 30


class RulesConfig(BaseModel):
    indicators: dict[str, IndicatorConfig]
    mitigations: dict[str, IndicatorConfig]
    bands: Bands = Bands()
    floors: Floors = Floors()
    windows: Windows = Windows()
    min_history: int = 5
    floor_amount: float = 100

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
