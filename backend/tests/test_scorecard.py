"""The golden scorecard (evals/scorecard.py) must pass: every scenario as designed, and every Medium/High alert
either asserted by a scenario or reviewed with a reason in evals/reviewed_unexpected.yaml (issue #5)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evals"))

from scorecard import scorecard  # noqa: E402


def test_golden_scorecard_passes_and_has_no_unreviewed_alerts():
    card = scorecard()
    assert [r["id"] for r in card["rows"] if not r["passed"]] == []
    assert card["unexpected_alerts"]["unreviewed"] == []
    assert card["by_kind"]["must flag"]["total"] >= 7
