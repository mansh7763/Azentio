# Suggestions for the Stage 01 Plan

Date: 2026-10-31 · Reviews: `Docs/STAGE1_PLAN.md` Revision 2 against the Digital Fraud Investigation System brief (challenge 1 in `Docs/All problem Statements.pdf`, same text as `Docs/ProblemStatement-Stage-1.pdf`)

**Bottom line:** All 19 suggestions from the first review are applied, so this file now lists only what is still open. Fix items 1–5 before coding. Items 1 and 5 change `schemas.py`, so lock those first. Items 16–24 cover deployment.

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
| 10 | Section 5, workstream A and integration rules; `Docs/OWNERSHIP.md`; `.github/workstreams.json` | The dashboard endpoint moved to C, but A's modules still list it, and `backend/app/api/` belongs to A in the ownership map, so C's edit raises an overlap warning | Remove it from A's list and give C an explicitly owned file for the endpoint, in all three places |
| 11 | Workstream A, section 6 | Generator v1 is due at 12:15 in one place and 12:00 in the other | Use one time |
| 12 | Section 4 P0 | HV-01 is missing from the P0 indicator list, though the ATO chain depends on it | Add it |

## Before starting

| # | Item | Action |
| --- | --- | --- |
| 13 | `Docs/OWNERSHIP.md` names an owner for B only. A and C are blank, and all three stay blank in the plan | Fill in the names, and add each member's git email to `.github/workstreams.json` |
| 14 | `requirements.txt` has only PDF-reading libraries | Replace it with the app stack from section 5, in `backend/requirements.txt` with the Python version pinned |
| 15 | Deleting `GAME_PLAN.md` removed the 6:00 PM HackCulture submission deadline from the repo | Add one line about it to the plan |

## Deployment

**Decision:** frontend on Vercel, backend on Render, database on Aiven Postgres when deployed. Local development stays on SQLite, so each person keeps their own data and work continues if the venue network fails. Do not put the backend on Vercel: its serverless functions do not suit a local database file, file uploads or a long detection run.

The Level 1 scope and timeline do not change. Do items 16–18 during the scaffold. The rest can wait until after Level 1.

| # | Plan ref | Change |
| --- | --- | --- |
| 16 | Section 3 diagram, 3.1 | Replace "SQLite" with: SQLite locally, Aiven Postgres when deployed, selected by `DATABASE_URL`. The Aiven connection needs `sslmode=require` |
| 17 | Section 5 integration rules | Read all config from the environment: `DATABASE_URL`, `GROQ_API_KEY` and the CORS origins. List these names in `.env.example`, with no real values. Run Uvicorn on `$PORT` |
| 18 | 3.3 | Keep `rules.yaml` as defaults only and save UI rule edits in the database, or a restart loses them |
| 19 | 3.5 | Write the immutability triggers for both databases (`BEFORE UPDATE` and `BEFORE DELETE`), selected by `engine.dialect.name`. Postgres needs a trigger function |
| 20 | Section 5, workstream A | Add `psycopg` to the backend dependencies. Insert rows in batches, since row-by-row inserts over the network are slow. Load the demo data on startup when the database is empty |
| 21 | Section 5, workstream C | Read the API base URL from `VITE_API_URL`. Add a `vercel.json` SPA rewrite so a page refresh does not return 404 |
| 22 | Section 6 | Add "deploy to Vercel, Render and Aiven" to the After L1 row, for whoever owns it |
| 23 | Section 7 | Add a risk: Aiven or the venue network goes down. Fallback: SQLite with the demo data |
| 24 | New section | Add a short deployment section covering the three services, the environment variables and the submission deadline from item 15 |

Check the current Vercel, Render and Aiven free-tier limits before deploying, including memory on Render, because pandas and scikit-learn are memory-heavy. These were not verified for this review.
