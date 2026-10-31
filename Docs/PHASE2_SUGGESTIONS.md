# Phase 2 Suggestions

Date: 2026-10-31 · Reviews: `Docs/PHASE2_PLAN.md` against `Docs/Phase-2.pdf` pages 4–5 and `main` at `04b1189` (graph, priority and Pattern Scout merged).

**Bottom line:** The plan covers the requirements, and the agent guardrails are good. The scope is large for the time left, so agree on items 1–3 first. Nothing here is implemented yet. This review read the plan and the merged code; no tests were run for it.

## Fix first

| # | Owner | Problem | Fix |
| --- | --- | --- | --- |
| 1 | A + B | "Same customer within the chain window" is 30 minutes, but `APP-C011` is on 9 Oct and `T-C011-OUT2` on 10 Oct, so the main loan → payout → transfer story stays as separate cases | Group by linked group from `GET /api/graph/groups`, or by customer within a longer window such as 72 hours. Store `grouping_reason` |
| 2 | A | In the current engine a burst and new-device login are context on `T-C002-ATO`, not separate alerts, so the ATO example does not prove consolidation | Show consolidation with the `C011` loan chain and `C006` transfers. Keep the ATO story for the workspace |
| 3 | A | `fraud_case.incident_key` is unique, so one case holds one incident, and a re-run could undo an analyst's split | Let a case hold several incidents. Save a split as an override that every consolidation respects |
| 4 | A + C | Level 2 expects analysts to change a risk classification, but the 7 actions have no such action | Add `reclassify`, keeping the original band, new band, reason, user and time. Show it in the workspace |
| 5 | A | The plan does not say which actions change case status | Define it in one table. `request_info`, `recommend_hold` and `recommend_verification` are recorded without touching any account or payment |
| 6 | B | The demo files have no claims or policies, so L2-1's insurance side cannot be shown, though `builder.py` already links them | Add 2–3 synthetic claims whose payout account matches the loan chain, then rebuild the demo files. If this is cut, say in the demo that insurance is not shown |
| 7 | B + C | `POST /api/agents/pattern-scout` saves nothing, and suggestions have no case to store Approve or Dismiss on | Add a small suggestion table. Approving must not change the rules |

## Agents and prioritisation

| # | Owner | Suggestion |
| --- | --- | --- |
| 8 | C | The Assistant should receive the route and IDs, and the backend should load the data from the store. Check citations against that data, and treat text inside records as data, not instructions |
| 9 | A + C | Save an `ai_assessment` event only for output tied to a case, marked AI-generated, so analysts can reject it |
| 10 | B | `prioritise()` works per alert, but the queue sorts cases. Aggregate per case: highest risk, combined evidence, and exposure |
| 11 | B | Exposure compares raw amounts across currencies. Compare within one currency, or show exposure by currency |
| 12 | B + C | Show `confidence` as evidence strength, not a probability |

## Cut order

The plan's "never cut" list includes the Assistant, while Split can be cut. The PDF requires Split; it does not require an Assistant.

1. **Never cut:** consolidation with the reason, Split, the analyst actions, audit trail, report download, prioritisation, and a relationship view (a table is an acceptable fallback).
2. **Then:** Assistant with its LLM-off fallback.
3. **Cut first:** Pattern Scout's LLM text, then Reviewer memory, then graph animation.

## Before building

- One person edits `schemas.py`. Case statuses and event types will change, so everyone should pull after that commit.
- Case tables will change, and the app does not migrate them. Everyone must delete `backend/fraud.db` after pulling.
- Until login exists, "user identity" is a typed reviewer name. Say so in the demo.
- Close the demo files in Excel. An open file blocks uploads and tests on Windows.
