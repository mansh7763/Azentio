# Azentio Hackathon Game Plan

Date: 2026-10-31

Theme: Digital Fraud Investigation System — AI-assisted detection, investigation and case intelligence. Build clock 11:00 AM–6:00 PM (7 hours, 3 people); briefs unlock one milestone at a time.

## Strategy

Win by clearing milestones fast with a working demo at every gate, not by building the most features. The next brief unlocks only after the current one clears, so speed to "cleared" compounds.

- **Pre-build the shell, not the answer.** Have the app skeleton, synthetic fraud data and the AI call working before 11:00. Each milestone then becomes "add a module", not "start a project".
- **Read the brief together, 10 minutes max.** List its acceptance criteria as checkboxes, split them, build. Re-read the criteria before asking for review.
- **Thin vertical slices.** Every milestone ends with something clickable end to end (data → detection → screen), even if rough. Polish only after the gate clears.
- **Use mentors as reviewers.** Ask a mentor to check against the brief before submitting a milestone; rework costs less than a failed gate.
- **AI must be visible and useful.** Judges are Azentio tech leaders (banking/insurance software). Show the AI explaining *why* a case is suspicious and drafting the investigator's report, with evidence cited — not a chatbot bolted on.
- **Freeze features at 5:00 PM.** The last hour is for the milestone lock, deck and a recorded backup demo.

## Roles

Three owners, one per layer, so nobody blocks on anyone else. Fill in names; swap if someone is stronger elsewhere.

| Role | Owns | Also does |
| --- | --- | --- |
| A — Backend + detection | API, database, data ingestion, rules engine, anomaly scoring | Repo, merges, deployment |
| B — Frontend + investigation UX | Alert queue, case view, entity link graph, dashboard | Demo flow and screen recording |
| C — AI + data + pitch | LLM case summary, risk explanation, report drafting, synthetic data | Reads each brief first, tracks acceptance criteria, owns the deck |

C is the milestone captain: they keep the checklist for the current brief and call when to submit it.

## Before 11:00

**Pre-built boilerplate is NOT allowed**, so no project code is written before 11:00. Before then we only prepare the environment and non-code material; the scaffold and the synthetic data script are the first tasks after 11:00.

Status:

- [x] All three have push access to `mansh7763/Azentio`
- [x] Wi-Fi, laptops, chargers
- [x] HackCulture platform account; submission location known
- [x] Branch rule: short feature branches, merge to `main` every hour
- [x] External APIs allowed
- [x] Hosted URL not required, but nice to have: deploy only if time allows after the 5:00 PM freeze
- [x] LLM provider: no Claude key needed. Default to **Groq** (keys available); final choice when the brief is out
- [ ] Format, judging criteria and what counts as clearing a milestone: not yet known; capture them at the briefing
- [x] Dependencies pre-downloaded (Python venv + npm cache) so 11:00 installs are fast
- [x] Deck outline drafted: `Docs/DECK_OUTLINE.md`

First 30 minutes after 11:00 (moved here because boilerplate is not allowed earlier):

- [ ] A: FastAPI + SQLite scaffold, `/health` endpoint, run command in README
- [ ] B: React (Vite) + Tailwind scaffold, one page calling `/health`
- [ ] C: Groq test call from the backend; synthetic transaction generator with planted fraud patterns

## Product shape

The detailed brief is not out yet, so this is our best guess at the pipeline. Milestones will most likely walk down it in order. Build each stage as its own module so a brief can reshape one without breaking the rest.

1. **Ingest** — load transactions, accounts, devices and customers (CSV upload or API).
2. **Detect** — rules (velocity, amount spikes, new device plus large transfer, round amounts, structuring under limits) plus an anomaly score (Isolation Forest). Output a 0–100 risk score with the reasons that fired.
3. **Alert queue** — ranked alerts with filters, assign to an investigator, mark true or false positive.
4. **Investigate** — case view with a timeline of events and an entity link graph (shared device, IP, phone or beneficiary links accounts into rings).
5. **AI case intelligence** — the LLM gets the case evidence and returns a plain-language summary, the likely fraud type, evidence cited by transaction ID, suggested next steps, and a drafted case report (STR/SAR style).
6. **Case management and dashboard** — statuses, audit trail of who did what, KPIs (alerts, cases open, amount at risk, false-positive rate).

Synthetic data to plant, so detection has something real to find: a mule ring (many accounts paying one beneficiary), account takeover (new device, then a password change, then a big transfer), structuring (many payments just under a limit), and card testing (many tiny charges).

## Stack

Pick tools all three already know; switch any row if the team is faster in something else. Decide tonight, not at 11:00.

| Layer | Choice | Why |
| --- | --- | --- |
| Backend | Python, FastAPI | Fast to write; same language as the ML and LLM code |
| Database | SQLite (Postgres only if the brief asks) | No setup, one file |
| Detection | pandas, scikit-learn (Isolation Forest) | Rules plus anomaly score in about 100 lines |
| AI | Groq API (`groq` Python SDK, JSON mode); provider decided once the brief is out | Keys already available; very fast responses for the live demo |
| Frontend | React + Vite, Tailwind, shadcn/ui | Good-looking screens quickly |
| Link graph | react-force-graph or Cytoscape.js | Shows fraud rings at a glance on the demo |
| Charts | Recharts | Dashboard KPIs |
| Hosting (optional, nice to have) | Render or Railway (backend), Vercel (frontend) | Deploys from GitHub in minutes |

## Day schedule

Target: Milestone 1 cleared by 12:30, so we start 2:00 PM already on Milestone 2 or 3. Milestone numbers are guesses; follow the briefs as they unlock.

| Time | A — Backend + detection | B — Frontend | C — AI + pitch |
| --- | --- | --- | --- |
| 11:00–11:15 | Read brief 1 together, write acceptance checklist, split work | Same | Same; owns the checklist |
| 11:15–11:45 | FastAPI + SQLite scaffold | React + Vite + Tailwind scaffold | Groq test call; synthetic data generator |
| 11:45–12:30 | Data model, ingestion, rules and scores via API | Alert queue and case screens on real API data | Data tuned to the brief; first LLM case summary |
| 12:30–13:00 | Integrate, run end to end, mentor check, submit Milestone 1 | Same | Same; leads submission |
| 13:00–14:00 (lunch) | Eat at desk; read brief 2, plan it | Fix rough UI from Milestone 1 | Draft deck: problem, solution, architecture |
| 14:00–15:30 | Next module (e.g. anomaly model, ring detection) | Link graph and case timeline | AI explanations with cited evidence, report draft |
| 15:30–16:00 | Integrate, mentor check, submit milestone | Same | Same |
| 16:00–17:00 | Next brief or rework; audit trail, KPIs | Dashboard, empty and loading states | Prompt tuning, guardrails (no made-up facts) |
| 17:00–18:00 | Feature freeze. Lock final milestone, push code, deploy if needed | Record a 2-minute backup demo video | Finish deck, upload all three before 18:00 |
| 18:00–18:45 | Rehearse the 5-minute pitch twice | Same | Same |
| 18:45–20:15 | Final jury if in top 10 | Drives the live demo | Presents |

Every integration slot: pull `main`, run the full demo path, fix only what breaks it.

## Submission and jury

Code, prototype and deck must be on HackCulture by 6:00 PM; aim for 5:45. The top 10 present to Azentio's technology leaders from 6:45.

Deck, 7 slides:

1. Problem: fraud losses and how slow manual investigation is
2. Solution in one line plus a screenshot
3. Architecture: ingest → detect → investigate → AI intelligence → case
4. Detection: rules plus anomaly score, with an example
5. AI case intelligence: summary, cited evidence, drafted report
6. Milestones cleared and impact (time per case, rings found)
7. What's next: real-time streaming, feedback loop for the model, deploying on Azentio's platforms

Demo script (3 minutes): upload data → alerts appear ranked → open the top alert → the graph shows a mule ring → the AI explains why and drafts the report → the investigator closes the case and the dashboard updates.

Have answers ready on: false positives, explainability for regulators, data privacy when sending data to an LLM, and how it scales.

## Risks and fallbacks

| Risk | Fallback |
| --- | --- |
| Brief differs from our guessed pipeline | Modules are separate; drop or reshape one, keep the shell |
| Stuck on one milestone past 45 minutes | Ask a mentor right away; ship the smallest version that meets the criteria |
| Venue Wi-Fi or LLM API fails | Cache AI responses for the demo cases; phone hotspot |
| Merge conflicts late in the day | Merge hourly; nobody touches another owner's folder |
| Live demo breaks at the jury | Backup video recorded by 5:30 PM; seeded demo database |
| Team fatigue (8 AM–9 PM) | Sleep tonight; eat lunch; one person stays off the keyboard during each integration |
