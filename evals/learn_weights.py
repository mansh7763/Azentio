"""Learned rule weights (ML step 1): two classifiers on top of the frozen rules, compared with the hand weights.

Model A, logistic: a sign-constrained logistic model (one learned multiplier per rule).
Model B, gradient-boosted trees (HistGradientBoostingClassifier): learns combinations of rules, with monotonic
constraints (risk rules can only raise the score, mitigations only lower it), shallow trees and balanced classes;
explained by permutation importance on D2.

Each scoring unit's features are its rule evidence as the hand weights see it (weight x strength, strongest per
rule), plus the attack-chain floor. The model learns one multiplier per rule: 1.0 means the hand weight was right,
1.5 means the rule deserves more, 0 means it adds nothing. Risk rules may only add risk (>= 0); mitigations may only
reduce it (<= 0). So the model stays explainable: contribution = multiplier x hand evidence.

Trained on D2 (seed 2). Compared with the hand-weighted engine on a FRESH held-out seed (4): D3 was reported once
at the Stage 1 freeze and is not reused. Rules are not changed; this only measures whether learned weights would
help, at the same Medium/High alert volume as the hand weights on D2.

    python evals/learn_weights.py      -> evals/reports/learned_weights.{md,json}
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
from scipy.optimize import minimize  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.inspection import permutation_importance  # noqa: E402
from sklearn.metrics import average_precision_score  # noqa: E402

import evaluate as ev  # noqa: E402
from app.detect.units import build_units  # noqa: E402
from app.schemas import Band  # noqa: E402
from app.score.scoring import effect  # noqa: E402

REPORTS = Path(__file__).resolve().parent / "reports"
TRAIN_SEED, TEST_SEED = 2, 4
L2 = 0.002  # light pull toward the hand weights: the data decides, the hand weights break ties
NOTE = ("Synthetic labelled data (evals/generate.py). The model learns how much each existing rule should count on "
        "simulated scenarios; it is a calibration of the rules, not a fraud probability and not real-world accuracy.")


def dataset(seed: int) -> dict:
    """Units with rule evidence, the engine's own alert for each, and a fraud label from the planted incidents."""
    bank, parts, cfg, events = ev.run(seed)
    result = ev.score_signals(parts, cfg)
    alerts = {(a.unit_type.value, a.primary_entity_id): a for a in result.alerts}
    owner = {e: i.id for i in bank.incidents for e in i.planted}
    setup = set().union(*(i.setup for i in bank.incidents))
    rows = []
    for unit in build_units(parts.ds, parts.signals, parts.bursts, cfg):
        everything = unit.signals + unit.context
        risk = [s for s in everything if s.direction.value == "risk" and effect(s) > 0]
        alert = alerts.get((unit.unit_type.value, unit.primary_entity_id))
        if not risk or alert is None or unit.primary_entity_id in setup:
            continue
        features: dict[str, float] = {}
        for s in everything:
            key = s.indicator_id if s.direction.value == "risk" else f"{s.indicator_id}"
            features[key] = max(features.get(key, 0.0), effect(s))
        floor = max((c.points for c in alert.contributions if c.kind == "floor"), default=0)
        features["CHAIN_FLOOR"] = 1.0 if floor > 0 else 0.0
        incidents = {owner[e] for e in [unit.primary_entity_id, *unit.event_ids] if e in owner}
        kinds = {i.kind for i in bank.incidents if i.id in incidents}
        rows.append({"features": features, "label": int("fraud" in kinds), "alert": alert,
                     "risk": {s.indicator_id for s in risk}})
    return {"rows": rows, "bank": bank, "events": events, "alerts": result.alerts}


def matrix(rows, columns):
    return np.array([[r["features"].get(c, 0.0) for c in columns] for r in rows])


def fit(X, y, columns, mitigations):
    """Weighted logistic loss + L2, with sign bounds. Starts at 'every rule counts as its hand weight'."""
    pos = max(1, y.sum())
    sample_w = np.where(y == 1, len(y) / (2 * pos), len(y) / (2 * max(1, len(y) - pos)))

    def loss(theta):
        b, w = theta[0], theta[1:]
        z = b + X @ w
        p = 1 / (1 + np.exp(-z))
        eps = 1e-9
        nll = -np.sum(sample_w * (y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps))) / len(y)
        grad_z = sample_w * (p - y) / len(y)
        return nll + L2 * np.sum((w - start[1:]) ** 2), np.concatenate([[grad_z.sum()], X.T @ grad_z + 2 * L2 * (w - start[1:])])

    start = np.concatenate([[-2.0], [(-1.0 if c in mitigations else 1.0) * 4.0 for c in columns]])
    bounds = [(None, None)] + [((None, 0.0) if c in mitigations else (0.0, None)) for c in columns]
    res = minimize(loss, start, jac=True, method="L-BFGS-B", bounds=bounds)
    return res.x


def predict(theta, X):
    return 1 / (1 + np.exp(-(theta[0] + X @ theta[1:])))


def rebanded(rows, scores, t_medium, t_high):
    """The engine's alerts with bands set by the model's score instead of the hand score."""
    out = []
    for r, p in zip(rows, scores):
        band = Band.high if p >= t_high else Band.medium if p >= t_medium else Band.low
        out.append(r["alert"].model_copy(update={"band": band}))
    return out


def matched_threshold(scores, n_flagged):
    """The score threshold that flags the same number of units as the hand weights did."""
    if n_flagged <= 0:
        return float("inf")
    return float(np.sort(scores)[::-1][min(n_flagged, len(scores)) - 1])


def main() -> int:
    train, test = dataset(TRAIN_SEED), dataset(TEST_SEED)
    mitigations = {c for r in train["rows"] for c in r["features"] if c.startswith("MT-")}
    columns = sorted({c for r in train["rows"] for c in r["features"]})
    Xtr, ytr = matrix(train["rows"], columns), np.array([r["label"] for r in train["rows"]])
    Xte, yte = matrix(test["rows"], columns), np.array([r["label"] for r in test["rows"]])
    theta = fit(Xtr, ytr, columns, mitigations)
    trees = HistGradientBoostingClassifier(
        max_depth=3, learning_rate=0.08, max_iter=300, l2_regularization=1.0, class_weight="balanced",
        monotonic_cst=[-1 if c in mitigations else 1 for c in columns], random_state=0).fit(Xtr, ytr)

    # Thresholds chosen on D2 only: the same number of Medium+ and High units as the hand weights flag on D2.
    ptr = predict(theta, Xtr)
    hand_tr = np.array([r["alert"].score for r in train["rows"]])
    t_medium = matched_threshold(ptr, int((hand_tr >= 40).sum()))
    t_high = matched_threshold(ptr, int((hand_tr >= 70).sum()))

    gtr = trees.predict_proba(Xtr)[:, 1]
    g_medium = matched_threshold(gtr, int((hand_tr >= 40).sum()))
    g_high = matched_threshold(gtr, int((hand_tr >= 70).sum()))

    pte = predict(theta, Xte)
    gte = trees.predict_proba(Xte)[:, 1]
    hand_te = np.array([r["alert"].score for r in test["rows"]])
    hand_alerts = [r["alert"] for r in test["rows"]]
    model_alerts = rebanded(test["rows"], pte, t_medium, t_high)
    hand_m = ev.measure(hand_alerts, test["bank"].incidents, test["events"])
    model_m = ev.measure(model_alerts, test["bank"].incidents, test["events"])
    trees_m = ev.measure(rebanded(test["rows"], gte, g_medium, g_high), test["bank"].incidents, test["events"])
    imp = permutation_importance(trees, Xtr, ytr, scoring="average_precision", n_repeats=5, random_state=0)
    importance = sorted(({"rule": c, "importance": round(float(v), 4)} for c, v in zip(columns, imp.importances_mean)),
                        key=lambda r: -r["importance"])

    weights = []
    for c, w in zip(columns, theta[1:]):
        weights.append({"rule": c, "learned_multiplier": round(abs(w) / 4.0, 2),
                        "direction": "mitigation" if c in mitigations else ("floor" if c == "CHAIN_FLOOR" else "risk"),
                        "units_in_D2": int((Xtr[:, columns.index(c)] > 0).sum())})
    weights.sort(key=lambda r: -r["learned_multiplier"])
    keys = ("recall_medium_plus", "recall_high", "lookalike_fp_medium_plus", "lookalike_fp_high",
            "precision_medium_plus", "background_flags_medium_plus", "alerts_medium_plus_per_1k_events")
    report = {
        "note": NOTE, "train": f"D2 (seed {TRAIN_SEED})", "test": f"fresh held-out seed {TEST_SEED}",
        "units": {"train": len(ytr), "train_fraud": int(ytr.sum()), "test": len(yte), "test_fraud": int(yte.sum())},
        "average_precision_test": {"hand_weights": round(float(average_precision_score(yte, hand_te)), 3),
                                   "learned_weights": round(float(average_precision_score(yte, pte)), 3),
                                   "boosted_trees": round(float(average_precision_score(yte, gte)), 3)},
        "incident_metrics_test": {"hand_weights": {k: hand_m[k] for k in keys}, "learned_weights": {k: model_m[k] for k in keys},
                                  "boosted_trees": {k: trees_m[k] for k in keys}},
        "thresholds_from_D2": {"logistic": {"medium": round(t_medium, 4), "high": round(t_high, 4)},
                               "boosted_trees": {"medium": round(g_medium, 4), "high": round(g_high, 4)}},
        "weights": weights, "boosted_tree_importance_D2": importance,
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "learned_weights.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    pct = lambda x: f"{100 * x:.0f}%"  # noqa: E731
    h, m = report["incident_metrics_test"]["hand_weights"], report["incident_metrics_test"]["learned_weights"]
    g = report["incident_metrics_test"]["boosted_trees"]
    ap = report["average_precision_test"]
    md = ["# Learned rule weights (ML step 1)", "", f"> {NOTE}", "",
          f"Trained on {report['train']} ({report['units']['train']} scored units, {report['units']['train_fraud']} fraud); "
          f"tested on {report['test']} ({report['units']['test']} units, {report['units']['test_fraud']} fraud). "
          "Alert volume is matched to the hand weights on D2, so the comparison is like for like.", "",
          "## Held-out comparison", "", "| Measure | Hand weights | Learned weights (logistic) | Boosted trees |", "| --- | --- | --- | --- |",
          f"| Ranking quality (average precision, units) | {ap['hand_weights']} | {ap['learned_weights']} | {ap['boosted_trees']} |",
          f"| Fraud incidents caught at Medium+ | {pct(h['recall_medium_plus'])} | {pct(m['recall_medium_plus'])} | {pct(g['recall_medium_plus'])} |",
          f"| Fraud incidents caught at High | {pct(h['recall_high'])} | {pct(m['recall_high'])} | {pct(g['recall_high'])} |",
          f"| Lookalikes wrongly at Medium+ | {pct(h['lookalike_fp_medium_plus'])} | {pct(m['lookalike_fp_medium_plus'])} | {pct(g['lookalike_fp_medium_plus'])} |",
          f"| Lookalikes wrongly at High | {pct(h['lookalike_fp_high'])} | {pct(m['lookalike_fp_high'])} | {pct(g['lookalike_fp_high'])} |",
          f"| Precision of Medium+ alerts | {pct(h['precision_medium_plus'])} | {pct(m['precision_medium_plus'])} | {pct(g['precision_medium_plus'])} |",
          f"| Background false alarms (Medium+) | {h['background_flags_medium_plus']} | {m['background_flags_medium_plus']} | {g['background_flags_medium_plus']} |",
          f"| Medium+ alerts per 1,000 events | {h['alerts_medium_plus_per_1k_events']} | {m['alerts_medium_plus_per_1k_events']} | {g['alerts_medium_plus_per_1k_events']} |",
          "", "## What the model learned", "",
          "Multiplier on the hand weight: 1.0 = hand weight confirmed, above 1 = rule deserves more, 0 = adds nothing on D2.", "",
          "| Rule | Direction | Learned multiplier | Units with this rule (D2) |", "| --- | --- | --- | --- |"]
    md += [f"| {w['rule']} | {w['direction']} | {w['learned_multiplier']} | {w['units_in_D2']} |" for w in weights]
    md += ["", "## What the boosted trees rely on (permutation importance on D2)", "",
           "Drop in average precision when a rule's evidence is shuffled; larger = the model relies on it more.", "",
           "| Rule | Importance |", "| --- | --- |"]
    md += [f"| {r['rule']} | {r['importance']} |" for r in importance if r["importance"] > 0]
    md += ["", "Rules are frozen for Stage 1: these multipliers are evidence for a future rules change, reviewed by a "
               "person and re-checked on new held-out data before adoption."]
    (REPORTS / "learned_weights.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[6:18]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
