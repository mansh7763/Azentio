# Phase 2 (Level 2) Plan — FinShield

Source: `Docs/Phase-2.pdf` pages 4–5. **Hard deadline 17:00.** Build 16:20–16:45 · integrate 16:45–16:55 · submit by 16:58. Anything not working at 16:45 is cut, not demoed.

## What Level 2 asks (proof the judges must see)

| # | Requirement | Observable proof | Owner |
| --- | --- | --- | --- |
| L2-1 | Cross-system correlation (lending + insurance + banking) | Loan app on a shared device → payout → unfamiliar beneficiary shown as **one** investigation | B (links) + A (case) |
| L2-2 | Relationship visualisation; click entity → its records; links only from matching IDs | Network view; every edge shows the shared identifier and record IDs | B (API) + C (UI) |
| L2-3 | Consolidate alerts into one investigation, explain grouping, allow split, keep originals | ATO case holds burst + new-device login + transfer; "why grouped"; Split button | A |
| L2-4 | Workspace: timeline, entities, indicators, evidence, risk, notes; 6 analyst actions (recommendations only) | Confirm / FP with reason / request info / escalate / recommend hold or verification / conclusion | A (API) + C (UI) |
| L2-5 | Evidence + audit trail incl. **AI-generated assessments**, corrections, user, time; downloadable report | Case history lists AI outputs and decisions; Download report | A |
| L2-6 | Prioritise by risk, exposure, related events, confidence; weak evidence → "needs review" | Queue sorted by priority with the factors shown | B (function) + A (sort) |

## Agents (agentic layer) — what we build and the guardrails

All agents **suggest, never decide**: they never change a score, never invent a relationship (only IDs that exist in the data), cite record IDs (backend drops claims whose IDs don't exist), are saved as `ai_assessment` events in the case audit trail (L2-5), and the app works with the LLM off. Model: Groq (our keys), JSON output.

| Agent | What it does | Owner |
| --- | --- | --- |
| **Pattern Scout** (your idea 1) | Scans the latest run for linked groups and behaviour **no rule alerted on** (shared device/phone/payout/beneficiary clusters, convergence). Deterministic mining finds the candidates with evidence; the LLM writes a short hypothesis and a suggested rule. Shown as "Suggested patterns — needs analyst approval". | B |
| **AI Assistant** (idea 2), top-right button on every screen | Answers evaluator questions about **what is on screen**: the frontend sends the current route and its visible data (dashboard summary, alert, case, graph); the backend adds the latest run summary. Answers cite IDs; "not on this screen" when unsure. | C |
| **Reviewer memory** (idea 3) | Previous evaluators' decisions, notes and AI assessments on a case (and on cases sharing its entities) are fed to the Assistant and shown as "What earlier reviewers found". Uses the existing append-only case events. | C (assistant context) + A (query) |

## Split

### A — Harsh: cases, consolidation, workspace actions, audit, report
- Consolidate alerts into incidents: same customer within the chain window, or same linked group from B's `GET /api/graph/groups`. Store `grouping_reason`. `POST /api/cases/{id}/split {alert_ids, reason}` → new case, originals kept.
- `POST /api/cases/{id}/actions {action, note, actor}`: `confirm`, `false_positive` (reason required), `request_info`, `escalate`, `recommend_hold`, `recommend_verification`, `conclude`. Account-affecting ones are stored as **recommendations**.
- Case events gain `type: decision | action | ai_assessment | note`; `POST /api/cases/{id}/events` for agents. Changing a classification keeps the original + reason.
- `GET /api/cases/{id}/report` → JSON (and Markdown) download: records, indicators, AI assessments, decisions, users, timestamps.
- Sort the queue with B's `prioritise()`; `GET /api/cases/history?entity_id=` for reviewer memory.

### B — mansh7763: links, correlation, prioritisation, Pattern Scout
- `backend/app/graph/`: NetworkX graph from stored records, nodes customer · account · device · IP · phone · email · application · beneficiary account (+ policy/claim if loaded); every edge carries the shared identifier and record IDs. Hub nodes (very common IPs/merchants) excluded above a degree cap.
- `GET /api/graph?entity_id=&depth=2` → `{nodes, edges}`; `GET /api/graph/entity/{id}` → its records; `GET /api/graph/groups` → connected groups with members, their alerts and the linking IDs (feeds A's consolidation, L2-1).
- `prioritise(alerts) -> {priority, risk, exposure, related_events, confidence, needs_review, factors}`; insufficient evidence (coverage gaps, only context signals) → `needs_review`.
- `POST /api/agents/pattern-scout` → suggestions with evidence; saved for the audit trail.

### C — Bhuvan: investigation UI + AI Assistant
- Network view (react-force-graph or a simple SVG); click node → records drawer; edge tooltip shows the shared ID.
- Case workspace: timeline, entities, indicators, evidence, risk/priority factors, notes, the 7 actions, Split, Download report, "What earlier reviewers found".
- Top-right **Ask FinShield** button → panel; `POST /api/assistant {question, screen: {route, data}}` in `backend/app/ai/` → `{answer, citations}`; context = screen data + latest run + case events.
- Suggested patterns panel (from Pattern Scout) with Approve / Dismiss (stored as case events).

## Contracts (fix now, build against them)

```
GET  /api/graph?entity_id=C011&depth=2   -> {nodes:[{id,type,label,risk}], edges:[{source,target,type,via,evidence_ids}]}
GET  /api/graph/groups                   -> {groups:[{group_id, members:[ids], alert_ids, links:[{via, value, evidence_ids}]}]}
POST /api/agents/pattern-scout           -> {suggestions:[{id,title,hypothesis,entities,evidence_ids,suggested_rule,source:"ai"|"rules"}]}
POST /api/assistant {question, screen}   -> {answer, citations:[ids], used_llm:bool}
POST /api/cases/{id}/actions {action,note,actor}; POST /api/cases/{id}/split {alert_ids,reason}; GET /api/cases/{id}/report
```

## Cut order if late (16:40 check)
1. Pattern Scout LLM text (keep deterministic suggestions) · 2. Split · 3. Markdown report (keep JSON) · 4. Graph animation (keep a table of links). Never cut: consolidation, actions, audit trail, priority, Assistant with LLM-off fallback.
