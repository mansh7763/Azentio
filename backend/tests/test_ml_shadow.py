"""The ML shadow score (app/detect/ml.py) is comparison-only: it must never change a rule score, band or category,
and it must be explainable from its own coefficients."""

import json
import math

from app.detect import ml
from app.detect.engine import run_detection


def _official(result):
    return [(a.alert_id, a.score, a.band, a.category) for a in result.alerts]


def test_shadow_model_never_changes_rule_scores(raw_golden, monkeypatch, tmp_path):
    with_model = run_detection(raw_golden)
    assert all(a.ml_score is not None and a.ml_band in {"Low", "Medium", "High"} for a in with_model.alerts)

    monkeypatch.setattr(ml, "MODEL_FILE", tmp_path / "missing.json")
    ml.load_model.cache_clear()
    try:
        without = run_detection(raw_golden)
    finally:
        ml.load_model.cache_clear()
    assert _official(without) == _official(with_model)
    assert all(a.ml_score is None for a in without.alerts)


def test_shadow_score_is_the_logistic_of_its_own_factors():
    model = json.loads(ml.MODEL_FILE.read_text(encoding="utf-8"))
    from app.schemas import Signal
    from datetime import datetime, timezone
    when = datetime(2026, 1, 1, tzinfo=timezone.utc)
    signals = [Signal(indicator_id="TX-01", entity_id="T", event_time=when, weight=0.45, strength=1.0, reason="r"),
               Signal(indicator_id="TX-03", entity_id="T", event_time=when, weight=0.25, strength=1.0, reason="r")]
    out = ml.shadow_score(signals, has_floor=False)
    z = model["intercept"] + model["coefficients"]["TX-01"] * 0.45 + model["coefficients"]["TX-03"] * 0.25
    assert out["ml_score"] == round(100 / (1 + math.exp(-z)))
    assert {f["rule"] for f in out["ml_factors"]} == {"TX-01", "TX-03"}
