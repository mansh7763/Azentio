"""Labelled evaluation (issue #5 Part 2). D2 (seed 2) is for tuning analysis; D3 (seed 3) is held out and only
reported. Nothing here changes rules: it measures them.

    python evals/evaluate.py heldout     # D3 metrics  -> evals/reports/d3_heldout.{md,json}
    python evals/evaluate.py tuning      # D2 metrics + ablation, sensitivity, correlation, threshold curve
                                         #            -> evals/reports/d2_tuning.{md,json}

Attribution: an alert belongs to an incident when its primary entity or any of its events was planted by that
incident. Medium/High alerts attributed to no incident are background false alarms.
"""

import json
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.detect.config import load_rules  # noqa: E402
from app.detect.dataset import Dataset  # noqa: E402
from app.detect.engine import Collected, collect_signals, score_signals  # noqa: E402
from app.schemas import Band  # noqa: E402
from generate import generate  # noqa: E402

REPORTS = Path(__file__).resolve().parent / "reports"
RANK = {None: -1, Band.low: 0, Band.medium: 1, Band.high: 2}
NOTE = ("Synthetic data from evals/generate.py with planted, labelled incidents. These numbers measure the rules "
        "against the scenarios we know how to simulate; they are not real-world fraud detection rates.")


def attribute(alerts, incidents):
    owner, setup = {}, set()
    for inc in incidents:
        for entity in inc.planted:
            owner[entity] = inc.id
        setup |= inc.setup
    by_incident, background = defaultdict(list), []
    for a in alerts:
        hits = {owner[e] for e in [a.primary_entity_id, *a.event_ids] if e in owner}
        if hits:
            for inc_id in hits:
                by_incident[inc_id].append(a)
        elif a.primary_entity_id not in setup:  # an incident's own history is neither its result nor background
            background.append(a)
    return by_incident, background


def measure(alerts, incidents, events: int) -> dict:
    by_incident, background = attribute(alerts, incidents)
    best = {i.id: max((RANK[a.band] for a in by_incident.get(i.id, [])), default=-1) for i in incidents}
    per = defaultdict(lambda: {"kind": None, "total": 0, "medium_plus": 0, "high": 0})
    for inc in incidents:
        row = per[inc.scenario]
        row["kind"] = inc.kind
        row["total"] += 1
        row["medium_plus"] += best[inc.id] >= 1
        row["high"] += best[inc.id] >= 2
    fraud = [i for i in incidents if i.kind == "fraud"]
    look = [i for i in incidents if i.kind == "lookalike"]
    flagged = [a for a in alerts if RANK[a.band] >= 1]
    kinds = {i.id: i.kind for i in incidents}
    true_flags = [a for a in flagged
                  if any(kinds.get(x) == "fraud" for x in attribute([a], incidents)[0])]

    def rate(items, level):
        return round(sum(best[i.id] >= level for i in items) / max(1, len(items)), 3)

    cold, warm = [i for i in fraud if i.new_customer], [i for i in fraud if not i.new_customer]
    return {
        "fraud_incidents": len(fraud), "lookalike_incidents": len(look),
        "recall_medium_plus": rate(fraud, 1), "recall_high": rate(fraud, 2),
        "lookalike_fp_medium_plus": rate(look, 1), "lookalike_fp_high": rate(look, 2),
        "precision_medium_plus": round(len(true_flags) / max(1, len(flagged)), 3),
        "background_flags_medium_plus": sum(RANK[a.band] >= 1 for a in background),
        "alerts_medium_plus_per_1k_events": round(1000 * len(flagged) / max(1, events), 2),
        "recall_medium_plus_new_customers": rate(cold, 1), "recall_medium_plus_established": rate(warm, 1),
        "new_customer_incidents": len(cold),
        "by_scenario": dict(sorted(per.items(), key=lambda kv: (kv[1]["kind"], kv[0]))),
    }


def run(seed: int):
    bank = generate(seed)
    frames = bank.frames()
    events = len(frames["transactions"]) + len(frames["logins"]) + len(frames["applications"])
    cfg = load_rules()
    parts = collect_signals(Dataset.from_frames(**frames), cfg)
    return bank, parts, cfg, events


def rescore(parts: Collected, cfg, keep=lambda s: True, weight=None):
    signals = [s if weight is None or s.indicator_id not in weight else s.model_copy(update={"weight": weight[s.indicator_id]})
               for s in parts.signals if keep(s)]
    return score_signals(Collected(parts.ds, parts.profiles, parts.bursts, signals, parts.run_ids, parts.skipped), cfg)


def heldout(seed: int = 3) -> dict:
    bank, parts, cfg, events = run(seed)
    result = score_signals(parts, cfg)
    return {"note": NOTE, "dataset": f"D3 (seed {seed}, held out)", "rules_version": result.run.rules_version,
            "rows": {k: len(v) for k, v in bank.frames().items()}, "metrics": measure(result.alerts, bank.incidents, events)}


def tuning(seed: int = 2) -> dict:
    bank, parts, cfg, events = run(seed)
    base_result = score_signals(parts, cfg)
    base = measure(base_result.alerts, bank.incidents, events)
    fired = sorted({s.indicator_id for s in parts.signals})
    risk_ids = sorted({s.indicator_id for s in parts.signals if s.direction.value == "risk"})

    def summary(m):
        return {k: m[k] for k in ("recall_medium_plus", "recall_high", "lookalike_fp_medium_plus",
                                  "precision_medium_plus", "background_flags_medium_plus")}

    def bands(result):
        return {(a.unit_type.value, a.primary_entity_id): a.band for a in result.alerts}

    base_bands = bands(base_result)

    ablation = {}
    for ind in fired:
        m = measure(rescore(parts, cfg, keep=lambda s, i=ind: s.indicator_id != i).alerts, bank.incidents, events)
        ablation[ind] = {k: round(v - base[k], 3) for k, v in summary(m).items()}

    sensitivity = {}
    for ind in fired:
        w = cfg.weight(ind)
        changed = {}
        for factor in (0.8, 1.2):
            new_w = min(round(w * factor, 4), 0.99)
            result = rescore(parts, cfg, weight={ind: new_w})
            now = bands(result)
            changed[f"x{factor}"] = sum(now.get(k) != v for k, v in base_bands.items()) + len(set(now) - set(base_bands))
        sensitivity[ind] = changed
    band_shift = {}
    for label, bands_cfg in {"medium-5": {"medium": cfg.bands.medium - 5}, "medium+5": {"medium": cfg.bands.medium + 5},
                             "high-5": {"high": cfg.bands.high - 5}, "high+5": {"high": cfg.bands.high + 5}}.items():
        shifted = load_rules({"bands": bands_cfg})
        band_shift[label] = summary(measure(score_signals(parts, shifted).alerts, bank.incidents, events))

    sets = [set(d for d in a.detection_types if not d.startswith("CHAIN:")) & set(risk_ids) for a in base_result.alerts]
    single = Counter(i for s in sets for i in s)
    pair = Counter(p for s in sets for p in combinations(sorted(s), 2))
    from app.score.scoring import family_of
    correlation = sorted(({"pair": f"{a} + {b}", "co_fire": n, "jaccard": round(n / (single[a] + single[b] - n), 3),
                           "same_family": family_of(a) == family_of(b)}
                          for (a, b), n in pair.items() if n / (single[a] + single[b] - n) >= 0.3),
                         key=lambda r: -r["jaccard"])

    curve = []
    for medium in range(30, 65, 5):
        shifted = load_rules({"bands": {"medium": medium}})
        m = measure(score_signals(parts, shifted).alerts, bank.incidents, events)
        curve.append({"medium_threshold": medium, **{k: m[k] for k in ("recall_medium_plus", "precision_medium_plus",
                                                                         "lookalike_fp_medium_plus",
                                                                         "alerts_medium_plus_per_1k_events")}})
    return {"note": NOTE, "dataset": f"D2 (seed {seed}, tuning)", "rules_version": base_result.run.rules_version,
            "metrics": base, "ablation_delta": ablation, "weight_sensitivity_band_changes": sensitivity,
            "band_threshold_shift": band_shift, "correlated_pairs": correlation, "medium_threshold_curve": curve}


def pct(x):
    return f"{100 * x:.0f}%"


def metrics_md(m: dict) -> list[str]:
    lines = ["| Measure | Value |", "| --- | --- |",
             f"| Fraud incidents caught at Medium or High | {pct(m['recall_medium_plus'])} of {m['fraud_incidents']} |",
             f"| Fraud incidents caught at High | {pct(m['recall_high'])} |",
             f"| Lookalikes wrongly raised to Medium or High | {pct(m['lookalike_fp_medium_plus'])} of {m['lookalike_incidents']} |",
             f"| Lookalikes wrongly raised to High | {pct(m['lookalike_fp_high'])} |",
             f"| Precision of Medium/High alerts | {pct(m['precision_medium_plus'])} |",
             f"| Background false alarms (Medium/High, no planted incident) | {m['background_flags_medium_plus']} |",
             f"| Medium/High alerts per 1,000 events (analyst workload) | {m['alerts_medium_plus_per_1k_events']} |",
             f"| Recall, new customers (cold start) | {pct(m['recall_medium_plus_new_customers'])} of {m['new_customer_incidents']} |",
             f"| Recall, established customers | {pct(m['recall_medium_plus_established'])} |",
             "", "| Scenario | Kind | Incidents | At Medium+ | At High |", "| --- | --- | --- | --- | --- |"]
    lines += [f"| {name} | {r['kind']} | {r['total']} | {r['medium_plus']} | {r['high']} |" for name, r in m["by_scenario"].items()]
    return lines


def write(name: str, report: dict, body: list[str]):
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / f"{name}.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (REPORTS / f"{name}.md").write_text("\n".join(body) + "\n", encoding="utf-8")


def main(mode: str) -> int:
    if mode == "heldout":
        r = heldout()
        write("d3_heldout", r, [f"# Held-out evaluation ({r['dataset']})", "", f"> {r['note']}", "",
                                f"Rules version `{r['rules_version']}` · rows {r['rows']}", "", *metrics_md(r["metrics"])])
        print(json.dumps({k: v for k, v in r["metrics"].items() if k != "by_scenario"}, indent=1))
    else:
        r = tuning()
        body = [f"# Tuning analysis ({r['dataset']})", "", f"> {r['note']} D2 is for analysis; D3 is reported separately.", "",
                f"Rules version `{r['rules_version']}`", "", *metrics_md(r["metrics"]), "",
                "## Ablation: change when one indicator is removed", "",
                "| Indicator | Recall M+ | Recall High | Lookalike FP M+ | Precision M+ | Background M+ |", "| --- | --- | --- | --- | --- | --- |"]
        body += [f"| {k} | {v['recall_medium_plus']:+.3f} | {v['recall_high']:+.3f} | {v['lookalike_fp_medium_plus']:+.3f} | "
                 f"{v['precision_medium_plus']:+.3f} | {v['background_flags_medium_plus']:+d} |" for k, v in r["ablation_delta"].items()]
        body += ["", "## Weight sensitivity: alerts whose band changes at ±20% weight", "", "| Indicator | x0.8 | x1.2 |", "| --- | --- | --- |"]
        body += [f"| {k} | {v['x0.8']} | {v['x1.2']} |" for k, v in r["weight_sensitivity_band_changes"].items()]
        body += ["", "## Band threshold shifts", "", "| Shift | Recall M+ | Recall High | Lookalike FP M+ | Precision M+ | Background M+ |", "| --- | --- | --- | --- | --- | --- |"]
        body += [f"| {k} | {pct(v['recall_medium_plus'])} | {pct(v['recall_high'])} | {pct(v['lookalike_fp_medium_plus'])} | "
                 f"{pct(v['precision_medium_plus'])} | {v['background_flags_medium_plus']} |" for k, v in r["band_threshold_shift"].items()]
        body += ["", "## Indicators that fire together (Jaccard >= 0.3)", "", "| Pair | Alerts with both | Jaccard | Same family |", "| --- | --- | --- | --- |"]
        body += [f"| {c['pair']} | {c['co_fire']} | {c['jaccard']} | {'yes' if c['same_family'] else 'no'} |" for c in r["correlated_pairs"]]
        body += ["", "## Medium threshold trade-off", "", "| Medium at | Recall M+ | Precision M+ | Lookalike FP M+ | Alerts per 1k |", "| --- | --- | --- | --- | --- |"]
        body += [f"| {c['medium_threshold']} | {pct(c['recall_medium_plus'])} | {pct(c['precision_medium_plus'])} | "
                 f"{pct(c['lookalike_fp_medium_plus'])} | {c['alerts_medium_plus_per_1k_events']} |" for c in r["medium_threshold_curve"]]
        write("d2_tuning", r, body)
        print(json.dumps(r["metrics"] | {"by_scenario": None}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "tuning"))
