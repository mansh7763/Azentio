"""Golden scorecard (issue #5, Part 1): every hand-built scenario in tests/golden/expected.yaml, expected vs actual.

These are calibration scenarios written by hand alongside the rules, NOT an accuracy measurement. Accuracy comes
from the labelled held-out evaluation (evals/evaluate.py).

    python evals/scorecard.py            # prints the summary, writes evals/reports/golden_scorecard.{md,json}
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import yaml  # noqa: E402

from app.detect.dataset import Dataset  # noqa: E402
from app.detect.engine import run_detection  # noqa: E402
from app.schemas import Band  # noqa: E402

GOLDEN = ROOT / "backend" / "tests" / "golden"
REPORTS = Path(__file__).resolve().parent / "reports"
REVIEWED = Path(__file__).resolve().parent / "reviewed_unexpected.yaml"
ORDER = {Band.low: 0, Band.medium: 1, Band.high: 2}
NOTE = ("Hand-built calibration scenarios, written alongside the rules. They show the rules behave as designed; "
        "they are not an accuracy measurement.")


def kind(case: dict) -> str:
    if "band" in case or "min_band" in case:
        return "must flag"
    if case.get("no_alert"):
        return "must stay silent"
    if case.get("max_band") == "Low":
        return "lookalike, must stay Low"
    return "capped"  # fraud that must not over-escalate, e.g. a ring application judged before the ring exists


def _matches(alerts, case):
    """Same matching as tests/test_engine.py::_matches."""
    return [a for a in alerts if a.unit_type.value == case["unit_type"]
            and ("entity" not in case or a.primary_entity_id == case["entity"])
            and ("customer" not in case or a.customer_id == case["customer"])]


def judge(alerts, case) -> tuple[bool, str]:
    found = _matches(alerts, case)
    problems = []
    if case.get("no_alert") and found:
        problems.append("expected no alert")
    if "band" in case and not any(a.band == Band(case["band"]) for a in found):
        problems.append(f"expected {case['band']}")
    if "min_band" in case and not (found and all(ORDER[a.band] >= ORDER[Band(case["min_band"])] for a in found)):
        problems.append(f"expected at least {case['min_band']}")
    if "max_band" in case and not all(ORDER[a.band] <= ORDER[Band(case["max_band"])] for a in found):
        problems.append(f"expected at most {case['max_band']}")
    if "category" in case and not (found and all(a.category.value == case["category"] for a in found)):
        problems.append(f"expected category {case['category']}")
    if case.get("one_alert_for") and len(found) != 1:
        problems.append("expected exactly one alert")
    if case.get("no_chain") and any(c.indicator_id and c.indicator_id.startswith("CHAIN:")
                                    for a in found for c in a.contributions):
        problems.append("expected no attack chain")
    return not problems, "; ".join(problems)


def scorecard(dataset: Dataset | None = None, cases: list[dict] | None = None) -> dict:
    cases = cases if cases is not None else yaml.safe_load((GOLDEN / "expected.yaml").read_text(encoding="utf-8"))
    result = run_detection(dataset or Dataset.from_csv_dir(GOLDEN))
    rows, matched = [], set()
    for case in cases:
        found = _matches(result.alerts, case)
        matched |= {a.alert_id for a in found}
        ok, why = judge(result.alerts, case)
        best = max(found, key=lambda a: a.score, default=None)
        expected = (case.get("band") or (f">= {case['min_band']}" if "min_band" in case else None)
                    or (f"<= {case['max_band']}" if "max_band" in case else "no alert"))
        rows.append({
            "id": case["id"], "kind": kind(case), "unit": case["unit_type"], "entity": case.get("entity", ""),
            "expected": expected, "score": best.score if best else None, "band": best.band.value if best else "none",
            "passed": ok, "problem": why,
            "top": [f"{c.indicator_id} {c.points:+d}" for c in sorted(best.contributions, key=lambda c: -abs(c.points))[:3]]
                   if best else [],
        })
    extra = [a for a in result.alerts if a.alert_id not in matched]
    reviewed = yaml.safe_load(REVIEWED.read_text(encoding="utf-8")) or {}
    flagged = [a for a in extra if a.band != Band.low]
    summary = {}
    for k in ("must flag", "capped", "lookalike, must stay Low", "must stay silent"):
        group = [r for r in rows if r["kind"] == k]
        summary[k] = {"passed": sum(r["passed"] for r in group), "total": len(group)}
    return {
        "note": NOTE, "run_id": result.run.run_id, "rules_version": result.run.rules_version,
        "passed": sum(r["passed"] for r in rows), "total": len(rows), "by_kind": summary, "rows": rows,
        "unexpected_alerts": {"total": len(extra),
                              "medium_or_high": sorted(f"{a.primary_entity_id} ({a.band.value} {a.score})" for a in flagged),
                              "unreviewed": sorted(a.primary_entity_id for a in flagged if a.primary_entity_id not in reviewed),
                              "reviewed": {a.primary_entity_id: reviewed[a.primary_entity_id]
                                           for a in flagged if a.primary_entity_id in reviewed}},
    }


def to_markdown(card: dict) -> str:
    lines = [f"# Golden scorecard", "", f"> {card['note']}", "",
             f"Rules version `{card['rules_version']}` · run `{card['run_id']}` · "
             f"**{card['passed']} / {card['total']} scenarios behave as designed**", "",
             "| Group | Passed |", "| --- | --- |"]
    lines += [f"| {k} | {v['passed']} / {v['total']} |" for k, v in card["by_kind"].items()]
    extra = card["unexpected_alerts"]
    lines += ["", f"Alerts on entities no scenario mentions: {extra['total']} "
                  f"({len(extra['medium_or_high'])} at Medium or High"
                  + (f": {', '.join(extra['medium_or_high'])}" if extra["medium_or_high"] else "") + "). "
              f"Unreviewed: **{len(extra['unreviewed'])}** (reasons for the reviewed ones: `evals/reviewed_unexpected.yaml`).", "",
              "| Scenario | Group | Unit · entity | Expected | Actual | Top contributions | Result |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in card["rows"]:
        actual = f"{r['band']} {r['score']}" if r["score"] is not None else "no alert"
        result = "✅" if r["passed"] else f"❌ {r['problem']}"
        lines.append(f"| {r['id']} | {r['kind']} | {r['unit']} · {r['entity']} | {r['expected']} | {actual} | "
                     f"{', '.join(r['top']) or '—'} | {result} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    card = scorecard()
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "golden_scorecard.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    (REPORTS / "golden_scorecard.md").write_text(to_markdown(card), encoding="utf-8")
    print(f"{card['passed']} / {card['total']} golden scenarios behave as designed")
    for k, v in card["by_kind"].items():
        print(f"  {k:<26} {v['passed']} / {v['total']}")
    extra = card["unexpected_alerts"]
    print(f"  unasserted Medium/High alerts: {len(extra['medium_or_high'])} ({len(extra['unreviewed'])} unreviewed"
          + (f": {', '.join(extra['unreviewed'])}" if extra["unreviewed"] else "") + ")")
    return 0 if card["passed"] == card["total"] and not extra["unreviewed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
