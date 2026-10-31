# Product

<!-- impeccable:product-schema 1 -->

## Name

FinShield (Digital Fraud Investigation System). Use "FinShield" in the app header, browser title and deck.

## Platform

web

## Stack

React + Vite + TypeScript + Tailwind, Recharts for charts, react-force-graph-2d for the link graph (P1), axios. Backend is FastAPI (`backend/`). Frontend lives in `frontend/`, deploys to Vercel; API base URL from `VITE_API_URL`. Decided in `Docs/STAGE1_PLAN.md` section 5, workstream C.

## Users

**Primary: a bank fraud analyst** triaging alerts and deciding cases across a working day. They need to see quickly what was flagged, why, on what evidence, and record a decision they can defend later. Design every screen for this person.

**Evaluators: hackathon judges** click through the app live on a laptop and score observable behaviour. They are treated as stand-ins for the analyst: if the analyst workflow is clear, the judge's walkthrough is clear. No separate "demo mode" UI.

## Product Purpose

A digital fraud investigation system for banking, lending and insurance data. It ingests records from several systems (CSV, Excel, JSON), links them into one entity model, detects suspicious behaviour, scores risk 0–100 with Low/Medium/High bands, raises alerts, and routes actionable ones into a case queue where the analyst records **Requires Investigation** or **False Positive**.

Success for Stage 01 (Level 1): a judge can (1) upload files and see a validation report with visible rejection reasons, (2) run detection, (3) use the dashboard with filters, (4) open an alert and see why it was flagged with supporting records, (5) open its case, record a decision, and see the original alert unchanged with a decision log.

## Positioning

Explainable, entity-centric risk: every score is a sum of visible contributions, including **why risk went down** (per-customer baselines recognise legitimate lookalikes such as a regular high-value payer or a family sharing a device). An identity graph links customers through shared devices, IPs, phones and beneficiary accounts to reveal coordinated fraud. Not a black box and not a flag-every-big-transfer rules list.

## Operating Context

- Analyst workflow: upload/load data → review data-quality report → run detection → scan dashboard → open alert → open case → decide.
- Primary viewing: laptop, live demo, roughly 1280–1440px wide. Desktop-first; phone is not a Stage 01 target.
- Every number on screen is computed from ingested data; nothing hard-coded. A "Load demo dataset" path always exists so the app is never empty.
- Must work fully with the LLM (Groq) switched off; AI text only rephrases evidence and cites record IDs.

## Capabilities and Constraints

- Entities: customer, account, transaction, login event, device, loan application, insurance claim, ingestion batch, alert (immutable), case + append-only case events.
- Detection families: suspicious transfers, shared devices, repeated login failures / account-takeover chains, legitimate lookalikes (mitigation), suspicious loan applications or duplicate claims.
- Scoring units: transaction, login burst, device cluster, application. Contribution lines sum exactly to the final score (risk lines, mitigation, floor).
- Alerts are never edited or deleted; dashboard reads the latest detection run only.
- Dashboard filters: customer, transaction, product, risk level, date, detection type.
- Terminology to use verbatim: **Requires Investigation**, **False Positive**, risk bands **Low / Medium / High**.
- Deadline-driven: Level 1 build window is roughly 30 minutes of frontend time; P1 (graph view, score waterfall, customer 360, AI summary) comes after.
- Synthetic / anonymised data only; no real PII.

## Brand Commitments

- **Working name: Kestrel** (recommended during init; the team may rename). Rationale: a small hawk that hovers, watches patiently, and strikes only on a confirmed target — matches "watch everything, flag only what's real."
- **Not branded as Azentio.** Azentio is the organiser, not the product owner; do not use their name or marks in the product UI.
- Voice: plain, factual, evidence-first. No "AI-powered" labels on rules; unsupported AI claims lose points.

## Evidence on Hand

- Brief: `Docs/ProblemStatement-Stage-1.pdf`, `Docs/All problem Statements.pdf`, `Docs/Stage-01.pdf`.
- Plan and evaluation: `Docs/STAGE1_PLAN.md`, `Docs/EVALUATION.md`, `Docs/specs/`, `Docs/plans/`.
- Data: seeded synthetic generator with labelled fraud and lookalikes (planned in backend). No organiser sample data yet.
- No testimonials, customers, benchmarks, logos or press exist. Do not fabricate any; metrics shown in the deck must come from the held-out dataset.

## Product Principles

1. **Show the why.** Every flag, score and band is traceable to named indicators and supporting record IDs, in both directions (risk up, risk down).
2. **Nothing silently lost.** Rejected rows, unmapped columns and skipped indicators are visible, with reasons.
3. **The record is sacred.** Alerts are immutable; decisions append, never overwrite. The UI makes that audit trail obvious.
4. **Analyst speed over spectacle.** The analyst workflow comes first; anything that doesn't help triage, explain or decide waits for P1.
5. **Live, never staged.** Every number reflects the ingested data.

## Accessibility & Inclusion

No product-specific standard set. Baseline: risk bands must not rely on colour alone (always label Low / Medium / High), and text stays readable at laptop demo distance.
