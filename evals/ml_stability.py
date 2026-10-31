"""ML step 1b: error bars for the learned weights (issue #7).

- Pools training data from several seeds (more incidents, less dependence on one simulated bank).
- Tests on several unseen seeds and reports every metric as mean and range, hand weights vs learned weights.
- Bootstraps by INCIDENT (units of one incident are near-copies, so the incident is the independent sample) to
  give a 90% interval for every rule multiplier: which re-weightings are reliable and which are noise.
- Exports the pooled model as the engine's shadow model (backend/app/detect/ml_model.json).

    python evals/ml_stability.py      -> evals/reports/ml_stability.{md,json}
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
from sklearn.metrics import average_precision_score  # noqa: E402

import evaluate as ev  # noqa: E402
import learn_weights as lw  # noqa: E402
from app.detect.units import build_units  # noqa: E402
from app.score.scoring import effect  # noqa: E402

TRAIN_SEEDS, TEST_SEEDS = (2, 6, 7), (4, 5, 8)
BOOTSTRAPS = 50
REPORTS = Path(__file__).resolve().parent / "reports"
KEYS = ("recall_medium_plus", "recall_high", "lookalike_fp_medium_plus", "precision_medium_plus",
        "background_flags_medium_plus", "alerts_medium_plus_per_1k_events")


def dataset(seed: int) -> dict:
    """Like learn_weights.dataset, plus the incident each unit belongs to (the bootstrap group)."""
    bank, parts, cfg, events = ev.run(seed)
    result = ev.score_signals(parts, cfg)
    alerts = {(a.unit_type.value, a.primary_entity_id): a for a in result.alerts}
    owner = {e: i.id for i in bank.incidents for e in i.planted}
    kind = {i.id: i.kind for i in bank.incidents}
    setup = set().union(*(i.setup for i in bank.incidents))
    rows = []
    for n, unit in enumerate(build_units(parts.ds, parts.signals, parts.bursts, cfg)):
        everything = unit.signals + unit.context
        risk = [s for s in everything if s.direction.value == "risk" and effect(s) > 0]
        alert = alerts.get((unit.unit_type.value, unit.primary_entity_id))
        if not risk or alert is None or unit.primary_entity_id in setup:
            continue
        features: dict[str, float] = {}
        for s in everything:
            features[s.indicator_id] = max(features.get(s.indicator_id, 0.0), effect(s))
        features["CHAIN_FLOOR"] = 1.0 if any(c.kind == "floor" and c.points > 0 for c in alert.contributions) else 0.0
        incidents = sorted({owner[e] for e in [unit.primary_entity_id, *unit.event_ids] if e in owner})
        rows.append({"features": features, "label": int(any(kind[i] == "fraud" for i in incidents)), "alert": alert,
                     "group": f"{seed}:{incidents[0]}" if incidents else f"{seed}:bg{n}"})
    return {"rows": rows, "bank": bank, "events": events}


def stats(values):
    v = np.array(values, dtype=float)
    return {"mean": round(float(v.mean()), 3), "min": round(float(v.min()), 3), "max": round(float(v.max()), 3)}


def main() -> int:
    train = [dataset(s) for s in TRAIN_SEEDS]
    rows = [r for d in train for r in d["rows"]]
    columns = sorted({c for r in rows for c in r["features"]})
    mitigations = {c for c in columns if c.startswith("MT-")}
    X, y = lw.matrix(rows, columns), np.array([r["label"] for r in rows])
    groups = np.array([r["group"] for r in rows])
    theta = lw.fit(X, y, columns, mitigations)

    hand_train = np.array([r["alert"].score for r in rows])
    p_train = lw.predict(theta, X)
    t_medium = lw.matched_threshold(p_train, int((hand_train >= 40).sum()))
    t_high = lw.matched_threshold(p_train, int((hand_train >= 70).sum()))

    # Held-out seeds: hand vs learned, at the alert volume matched on the pooled training data.
    per_seed = []
    for seed in TEST_SEEDS:
        d = dataset(seed)
        Xt, yt = lw.matrix(d["rows"], columns), np.array([r["label"] for r in d["rows"]])
        pt, ht = lw.predict(theta, Xt), np.array([r["alert"].score for r in d["rows"]])
        hand = ev.measure([r["alert"] for r in d["rows"]], d["bank"].incidents, d["events"])
        learned = ev.measure(lw.rebanded(d["rows"], pt, t_medium, t_high), d["bank"].incidents, d["events"])
        per_seed.append({"seed": seed, "units": len(yt), "fraud_units": int(yt.sum()),
                         "ap_hand": float(average_precision_score(yt, ht)), "ap_learned": float(average_precision_score(yt, pt)),
                         "hand": {k: hand[k] for k in KEYS}, "learned": {k: learned[k] for k in KEYS}})
        del d

    # Bootstrap by incident: resample groups with replacement, refit, collect multipliers.
    rng = np.random.default_rng(0)
    unique = np.unique(groups)
    index = {g: np.flatnonzero(groups == g) for g in unique}
    draws = []
    for _ in range(BOOTSTRAPS):
        pick = np.concatenate([index[g] for g in rng.choice(unique, len(unique), replace=True)])
        if y[pick].sum() == 0:
            continue
        draws.append(np.abs(lw.fit(X[pick], y[pick], columns, mitigations)[1:]) / 4.0)
    draws = np.array(draws)
    multipliers = []
    for j, c in enumerate(columns):
        lo, hi = np.percentile(draws[:, j], [5, 95])
        point = abs(theta[1 + j]) / 4.0
        verdict = "stronger than hand weight" if lo > 1.05 else "weaker than hand weight" if hi < 0.95 else "not distinguishable from hand weight"
        multipliers.append({"rule": c, "multiplier": round(point, 2), "p5": round(float(lo), 2), "p95": round(float(hi), 2),
                            "units": int((X[:, j] > 0).sum()), "incidents_or_units": int(len({g for g, v in zip(groups, X[:, j]) if v > 0})),
                            "verdict": verdict})
    multipliers.sort(key=lambda m: -m["multiplier"])

    model = {
        "model": "logistic regression on rule evidence (weight x strength), sign-constrained",
        "trained_on": f"pooled seeds {list(TRAIN_SEEDS)} ({len(y)} units, {int(y.sum())} fraud, "
                      f"{len({g for g in unique if not g.split(':')[1].startswith('bg')})} incidents)",
        "tested_on": f"held-out seeds {list(TEST_SEEDS)}", "rules_version": rows[0]["alert"].rules_version,
        "intercept": float(theta[0]), "coefficients": {c: float(w) for c, w in zip(columns, theta[1:])},
        "thresholds": {"medium": t_medium, "high": t_high},
        "held_out": {"average_precision_mean": round(float(np.mean([s["ap_learned"] for s in per_seed])), 3)},
        "note": lw.NOTE,
    }
    (ROOT / "backend" / "app" / "detect" / "ml_model.json").write_text(json.dumps(model, indent=2), encoding="utf-8")

    summary = {"ap_hand": stats([s["ap_hand"] for s in per_seed]), "ap_learned": stats([s["ap_learned"] for s in per_seed])}
    for k in KEYS:
        summary[f"hand_{k}"] = stats([s["hand"][k] for s in per_seed])
        summary[f"learned_{k}"] = stats([s["learned"][k] for s in per_seed])
    report = {"note": lw.NOTE, "train_seeds": TRAIN_SEEDS, "test_seeds": TEST_SEEDS, "training": model["trained_on"],
              "bootstraps": len(draws), "summary": summary, "per_seed": per_seed, "multipliers": multipliers}
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "ml_stability.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    def rng_txt(key, pct=True):
        s = summary[key]
        f = (lambda v: f"{100 * v:.0f}%") if pct else (lambda v: f"{v:g}")
        return f"{f(s['mean'])} ({f(s['min'])}–{f(s['max'])})"

    md = ["# Learned weights: stability across datasets", "", f"> {lw.NOTE}", "",
          f"Trained on {model['trained_on']}. Tested on unseen seeds {list(TEST_SEEDS)}; each cell is the mean "
          "(lowest–highest) over the three test datasets, at the alert volume matched on the training data.", "",
          "| Measure | Hand weights | Learned weights |", "| --- | --- | --- |",
          f"| Ranking quality (average precision) | {rng_txt('ap_hand', False)} | {rng_txt('ap_learned', False)} |",
          f"| Fraud incidents caught at Medium+ | {rng_txt('hand_recall_medium_plus')} | {rng_txt('learned_recall_medium_plus')} |",
          f"| Fraud incidents caught at High | {rng_txt('hand_recall_high')} | {rng_txt('learned_recall_high')} |",
          f"| Lookalikes wrongly at Medium+ | {rng_txt('hand_lookalike_fp_medium_plus')} | {rng_txt('learned_lookalike_fp_medium_plus')} |",
          f"| Precision of Medium+ alerts | {rng_txt('hand_precision_medium_plus')} | {rng_txt('learned_precision_medium_plus')} |",
          f"| Background false alarms | {rng_txt('hand_background_flags_medium_plus', False)} | {rng_txt('learned_background_flags_medium_plus', False)} |",
          f"| Medium+ alerts per 1,000 events | {rng_txt('hand_alerts_medium_plus_per_1k_events', False)} | {rng_txt('learned_alerts_medium_plus_per_1k_events', False)} |",
          "", f"## Rule multipliers with 90% intervals ({len(draws)} bootstrap resamples by incident)", "",
          "| Rule | Multiplier | 90% interval | Units | Verdict |", "| --- | --- | --- | --- | --- |"]
    md += [f"| {m['rule']} | {m['multiplier']} | {m['p5']}–{m['p95']} | {m['units']} | {m['verdict']} |" for m in multipliers]
    md += ["", "The pooled model is the engine's shadow model (backend/app/detect/ml_model.json); rule scores are unchanged."]
    (REPORTS / "ml_stability.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[6:16]))
    print("\n".join(f"{m['rule']:<12} {m['multiplier']:>5} [{m['p5']}-{m['p95']}] {m['verdict']}" for m in multipliers))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
