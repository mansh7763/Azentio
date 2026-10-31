"""ML shadow score: a classifier learned on labelled synthetic data (evals/learn_weights.py) that re-weighs the same
rule evidence. It runs on every alert of every dataset, next to the rule score, and NEVER sets the band, the case or
any decision: rule scores stay the official, evaluated result (Stage 1 freeze). Shadow first, promote on evidence.

Features are exactly what the model was trained on: per rule, the strongest weight x strength in the unit, plus
whether an attack-chain floor applied. Contribution of a rule = coefficient x feature, so the score is explainable.
"""

import json
import math
from functools import lru_cache
from pathlib import Path

from app.score.scoring import effect

MODEL_FILE = Path(__file__).resolve().parent / "ml_model.json"


@lru_cache(maxsize=1)
def load_model() -> dict | None:
    if not MODEL_FILE.exists():
        return None
    return json.loads(MODEL_FILE.read_text(encoding="utf-8"))


def features(signals, has_floor: bool) -> dict[str, float]:
    out: dict[str, float] = {}
    for s in signals:
        out[s.indicator_id] = max(out.get(s.indicator_id, 0.0), effect(s))
    out["CHAIN_FLOOR"] = 1.0 if has_floor else 0.0
    return out


def shadow_score(signals, has_floor: bool) -> dict | None:
    """{ml_score 0-100, ml_band, ml_factors} or None when no model is installed. Rules the model never saw add 0."""
    model = load_model()
    if model is None:
        return None
    x = features(signals, has_floor)
    coef = model["coefficients"]
    parts = {k: coef[k] * v for k, v in x.items() if k in coef and v}
    z = model["intercept"] + sum(parts.values())
    p = 1 / (1 + math.exp(-max(-60.0, min(60.0, z))))
    band = "High" if p >= model["thresholds"]["high"] else "Medium" if p >= model["thresholds"]["medium"] else "Low"
    factors = sorted(({"rule": k, "effect": round(v, 3)} for k, v in parts.items()), key=lambda f: -abs(f["effect"]))
    return {"ml_score": round(100 * p), "ml_band": band, "ml_factors": factors[:5]}
