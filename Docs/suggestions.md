# Suggestions for the Stage 01 Plan

Date: 2026-10-31 · Reviews: `Docs/STAGE1_PLAN.md` Revision 2 against the Digital Fraud Investigation System brief (challenge 1 in `Docs/All problem Statements.pdf`, same text as `Docs/ProblemStatement-Stage-1.pdf`)

**Bottom line:** All 19 suggestions from the first review are applied, so this file now lists only what is still open. Fix items 1–5 before coding. Items 1 and 5 change `schemas.py`, so lock those first.

**Scope:** The team is working on challenge 1 only. The other six challenges in the pack are out of scope. The pack's fraud section covers Level 1 only, so section 1.4's view of later levels remains a guess.

## Fix before coding

| # | Plan ref | Problem | Fix |
| --- | --- | --- | --- |
| 1 | 3.5, 3.4 step 3 | The scoring unit is undefined. "Every event" gives five alerts for one failed-login burst and an alert for each login on a shared device. Login signals and transfers are separate events, so an ATO chain never lands in one score | Define the scoring units: transaction, login burst, device cluster and application. Attach login and device signals from the window to the transaction as context |
| 2 | 3.4 step 5 | Contribution lines do not sum to the final score, because risk lines already total it before mitigation and floor lines are added. Final 20 with −30 damping gives −10; final 85 with a +45 floor gives 130. This came from the wording of the earlier suggestion #6 | Risk line = `undamped × cᵢ/Σc`; mitigation = `damped − undamped`; floor = `final − damped`. Clamp `wᵢsᵢ` below 1 to avoid `ln(0)` |
| 3 | 3.3 point-in-time rule, TX-03, DV-03 | With point-in-time features, each customer's first device and first beneficiary count as "new", which floods a short dataset with false positives | Skip TX-03 and DV-03 when history is short (e.g. fewer than 5 prior events). Do not treat the onboarding device as new |
| 4 | 3.4 step 3 | The partial ATO floor of 70 makes a legitimate user High: forgot password, failed attempts, reset, login from a new phone, with no money moved | Set the partial chain floor to Medium (e.g. 55). Require a beneficiary change or transfer for High. Add this case to the golden dataset, expecting Medium or lower |
| 5 | 3.5 | A rule change makes a re-run write a new alert for every event, so the dashboard double-counts and duplicate cases open. The trigger also blocks only `UPDATE` | The dashboard reads the latest run only. A new alert for the same event attaches to the existing case. Add a `BEFORE DELETE` trigger and a separate demo reset path |

## Smaller fixes

| # | Plan ref | Problem | Fix |
| --- | --- | --- | --- |
| 6 | 3.4 step 3 | Chains only say "within 24 h", so a transfer before the login would also match | Enforce the order: failed logins → new device → transfer |
| 7 | 3.3 HV-01 | A fixed absolute threshold breaks on unknown currencies and scales | Default to a value derived from loaded data, e.g. p90 of outbound amounts |
| 8 | 3.3 DV-02 | Anonymised data may have no name or address, so the household check cannot run | Return a neutral result and show "assessment unavailable" |
| 9 | 3.3 mitigation suspension | DV-03 alone suspends mitigation, which penalises a regular payer with a new phone | Suspend only when an LG signal is active |
| 10 | Section 5, workstream A and integration rules | The dashboard endpoint moved to C, but A's modules still list it, and C's folders do not include `backend/app/api` | Remove it from A's list and give C an explicitly owned file for the endpoint |
| 11 | Workstream A, section 6 | Generator v1 is due at 12:15 in one place and 12:00 in the other | Use one time |
| 12 | Section 4 P0 | HV-01 is missing from the P0 indicator list, though the ATO chain depends on it | Add it |

## Before starting

| # | Item | Action |
| --- | --- | --- |
| 13 | Owners for workstreams A, B and C are blank | Fill in the names |
| 14 | `requirements.txt` has only PDF-reading libraries | Replace it with the app stack from section 5 |
| 15 | Deleting `GAME_PLAN.md` removed the 6:00 PM HackCulture submission deadline from the repo | Add one line about it to the plan |
