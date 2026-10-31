"""Pattern Scout agent: looks for linked behaviour that no rule alerted on and proposes it to the analyst.

Deterministic mining finds every candidate and its evidence (real record IDs only). The LLM (Groq), when available,
only writes the hypothesis and a suggested rule for each candidate; it cannot add entities or change any score.
Every suggestion needs analyst approval. Works with the LLM off."""

import hashlib
import json
import os
from collections import defaultdict

from app.config import settings
from app.detect.dataset import Dataset
from app.graph.builder import build_graph, linked_groups
from app.schemas import Alert, Band

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _candidates(ds: Dataset, alerts: list[Alert]) -> list[dict]:
    flagged = {a.primary_entity_id for a in alerts if a.band != Band.low} | \
              {a.customer_id for a in alerts if a.band != Band.low}
    out = []
    # 1. Linked customers where nobody has a Medium/High alert yet.
    for grp in linked_groups(build_graph(ds), alerts):
        if not set(grp["members"]) & flagged:
            out.append({
                "kind": "quiet_linked_group", "entities": grp["members"],
                "evidence_ids": sorted({e for lk in grp["links"] for e in lk["evidence_ids"]})[:20],
                "title": f"{len(grp['members'])} linked customers with no Medium/High alert",
                "facts": grp["reason"],
            })
    # 2. Beneficiaries that several customers started paying, none of those payments flagged.
    txns = ds.get("transactions")
    if not txns.empty:
        first: dict[str, dict[str, str]] = defaultdict(dict)
        for _, t in txns.sort_values("seq").iterrows():
            cid = t.get("customer_id")
            if isinstance(cid, str) and cid not in first[t["beneficiary_account"]]:
                first[t["beneficiary_account"]][cid] = t["txn_id"]
        for ben, payers in sorted(first.items()):
            if len(payers) >= 3 and not set(payers.values()) & flagged:
                out.append({
                    "kind": "unflagged_convergence", "entities": sorted(payers) + [ben],
                    "evidence_ids": sorted(payers.values()),
                    "title": f"{len(payers)} customers started paying {ben}",
                    "facts": f"first payments to {ben} from {', '.join(sorted(payers))}",
                })
    return out


def _template(c: dict) -> tuple[str, str]:
    if c["kind"] == "quiet_linked_group":
        return (f"These customers are linked ({c['facts']}) but no rule raised them. Could be a family or a quiet "
                "ring building history before acting.", "Watch-list the group; alert if any member applies for "
                "credit or pays a new beneficiary within 30 days.")
    return (f"Several customers began paying the same account ({c['facts']}). Could be a merchant, or a "
            "collection (mule) account.", "Flag a beneficiary when >= 3 unrelated customers make first payments "
            "to it within 72h and it has no established payers.")


def _llm(cands: list[dict]) -> list[tuple[str, str]] | None:
    if not settings.groq_api_key or not cands:
        return None
    try:
        from groq import Groq

        prompt = ("You are a fraud analyst assistant. For each candidate pattern below, write a one-sentence "
                  "hypothesis (including an innocent explanation) and one suggested detection rule. Use only the "
                  "facts given; do not mention any ID that is not in the facts. Reply as JSON: "
                  '{"items":[{"hypothesis":"...","suggested_rule":"..."}]} in the same order.\n'
                  + json.dumps([{"title": c["title"], "facts": c["facts"]} for c in cands]))
        resp = Groq(api_key=settings.groq_api_key, timeout=8).chat.completions.create(
            model=GROQ_MODEL, response_format={"type": "json_object"}, temperature=0.2,
            messages=[{"role": "user", "content": prompt}])
        items = json.loads(resp.choices[0].message.content)["items"]
        return [(str(i["hypothesis"]), str(i["suggested_rule"])) for i in items][:len(cands)]
    except Exception:  # any LLM failure falls back to the deterministic text
        return None


def pattern_scout(ds: Dataset, alerts: list[Alert], use_llm: bool = True) -> dict:
    cands = _candidates(ds, alerts)
    texts = _llm(cands) if use_llm else None
    used = texts is not None and len(texts) == len(cands)
    suggestions = []
    for i, c in enumerate(cands):
        hyp, rule = texts[i] if used else _template(c)
        key = c["kind"] + "|" + ",".join(sorted(c["entities"]))
        suggestions.append({"id": "SUG-" + hashlib.sha256(key.encode()).hexdigest()[:10], "kind": c["kind"], "title": c["title"], "hypothesis": hyp,
                            "suggested_rule": rule, "entities": c["entities"], "evidence_ids": c["evidence_ids"],
                            "source": "ai" if used else "rules", "status": "suggested"})
    return {"suggestions": suggestions, "used_llm": used,
            "note": "Suggestions only: they need analyst approval and never change a score."}
