# Suggestions for the Stage 01 Plan - Review 3 / Revision 4

Reviewed: 2026-10-31. Controlling delivery constraint: **120 minutes from build start**.

**Recommendation:** implement the official upload-to-case journey first, including suspicious loan applications as the additional scenario. Show identity reuse and cross-system links using those same records. Add loan-to-mule flow detection only after all mandatory checks pass. The detailed execution plan and fraud catalogue are in [STAGE1_PLAN.md, section 0](STAGE1_PLAN.md#0-revision-4-executable-plan-for-a-strict-120-minute-deadline).

Changes below are applied to the planning document, **not to application code**. No application tests or fraud-performance benchmarks were executed in this document review. Older reviews remain in git history; the earlier plan is retained as clearly labelled historical design detail.

## What the document review found

| Document | Finding | Decision |
| --- | --- | --- |
| `ProblemStatement-Stage-1.pdf` | Five pages specify a working end-to-end system, four minimum Level 1 behaviours and one additional scenario; broader fraud catalogue is on pp2-3 | R1-R13 in the plan map requirements to observable proof and owner |
| `All problem Statements.pdf` | Challenge 1 repeats the fraud scope; other challenges concern regulation, offers, early warning, service voice, collections voice and claims leakage | Do not import their capabilities into our mandatory scope; claims leakage supplies future ideas only |
| `STAGE1_PLAN.md` revisions 1-3 | Good evidence/case design, but too many P0 indicators, larger datasets, expired wall-clock milestones and cloud work | Section 0 supersedes scope/timing; use local SQLite and small fixtures, freeze features at T+105 |
| Research / `FRAUD_THREAT_EXPANSION.md` | Useful 32-family threat catalogue and benign alternatives; early sections propose an alert-first agentic MVP and a broad service stack | Use section 32 for hypotheses; do not replace ingestion/detection with an existing-alert copilot; no agent orchestration or new service stack in two hours |
| `EVALUATION.md` | Valuable test library but ambitious synthetic/scale metrics and some outdated expectations | Use G1-G12 plus R1-R13 as the timeboxed gate; retain extended tests for later |
| `OWNERSHIP.md` | B is named; A and C are blank; shared-file ownership matters | Assign A/C at T+0; retain folder ownership and one editor for shared types |

The official minimum table's fourth row is **legitimate lookalikes**, not a fourth fraud category. Research sections 22/26/27 blur broader catalogue goals with minimum behaviours. Our plan covers identity/cross-system context with exact links while explicitly deferring advanced media, insurer and multi-hop implementations. The brief permits rules/statistics/ML; no requirement forces an LLM.

## Corrections applied to the plan

| Priority | Issue in earlier material | Required implementation change |
| --- | --- | --- |
| P0 | Whole-file high-value p90 leaks future events; pooled currencies distort amounts | Prior successful same-currency baseline or configured threshold; pre-payment balance only |
| P0 | TX-01 and TX-02 count the same anomaly twice | Keep TX-01 only in P0; max within correlated signal families before noisy-OR |
| P0 | ATO sequence treats successful new-device login as two sequential events | New-device attribute belongs to success; require subsequent sensitive event with reliable ordering |
| P0 | Any transfer after failures gets High; every failure disables all mitigation | Require corroborating access-context evidence for a High chain; ordinary follow-up payment is not sufficient |
| P0 | First observed device/payee is assumed genuinely new | Short-history status; only observed facts; explicit device-change data can supply additional evidence |
| P0 | Shared surname/address proves household, nearest login proves transaction device | Mark possible household and inferred links; do not silently infer identity, kinship or session ownership |
| P0 | Shared device/IP alone opens High loan cases | Separate application-category detector with corroborating contact/payout/conflict or coordinated activity |
| P0 | Same-rules rerun skips alerts but may publish an empty latest run | Return existing completed snapshot; use latest completed run for selected dataset |
| P0 | Changing cluster membership can generate duplicate cases | Stable window/incident keys; retain immutable per-run evidence and attach to existing case |
| P0 | Absent data becomes zero risk | Separate coverage status from score; show skipped detectors, unresolved links and short history |
| P0 | Latest-run aggregates obscure denominators | Separate accepted records, evaluated units and flagged incidents; label risk distribution explicitly |
| P0 | Original alert protection undermined by public destructive reset endpoint | Omit reset API; separate disposable local demo database; preserve immutable alerts/decisions |
| P0 | Sixteen-rule build, large generator and integration late in the schedule | Small paired fixtures first, real vertical integration by T+55, all mandatory behaviour by T+80 |
| P1 | Graph shapes treated as proof of organised fraud | Require temporal and independent corroboration; merchant, payroll, treasury and household alternatives |
| Later | Product ownership/gap claims and free hosting assumptions not verified | Leave as historical inspiration; make no current vendor deficiency, ownership or hosting promise |

## Evaluation expectations that must change with implementation

These are explicit corrections to the retained `EVALUATION.md` library; section 0 of the plan has precedence.

- LNK-02: nearby login is **derived**, possibly ambiguous; it does not prove the transfer's device.
- LNK-06 / DV-T2: matching surname/address means possible household; use independent supplied household context or ordinary behaviour to justify mitigation.
- TX-T3: two prior payments plus a large amount need not be Medium/High; short history is uncertainty, not proof of fraud.
- AP-T1: evaluate the cluster at the current cutoff. Earlier applications cannot become High using future applications; a later cluster alert can cite the earlier applications as evidence.
- RS-P4: monotonicity applies with fixed context/coverage; adding historical data may legitimately change a baseline or mitigation. Test risk-signal changes separately from dataset changes.
- RS-P5: apply the ATO floor only when the full corroborated temporal chain is present.
- RS-P8: High requires multiple independent facts, not several correlated rules on one amount.
- CS-11: new rule version produces a completed result snapshot; identical-run reuse must not empty the dashboard.
- DB-02: reconcile the stated denominator (evaluated units or alerts); do not mix Low results with actionable alert counts silently.
- Large D2/D3/D6 datasets, AUC/precision targets, multiple database trigger tests and fixed 13:15/13:35 runs are extended work. They are not claims of achieved performance or prerequisites within this two-hour window.

## Creative additions worth prioritizing

The plan's F01-F22 catalogue gives evidence, missing inputs, benign controls and protective responses. Recommended differentiation order:

1. **Loan swarm with identity reuse (P0 extra):** application evidence makes the shared device meaningful. Compare against legitimate assisted/household applications.
2. **Loan-to-mule flow (only P1):** connect explicit disbursement to subsequent outflow and recipient evidence; show the timeline without needing a graph UI.
3. **Recipient convergence despite different devices (later):** catch a common destination when device sharing is absent; compare against a legitimate dealer.
4. **APP scam with normal authentication (later):** demonstrate why a familiar device does not clear an unusual recipient; requires recipient or customer-context evidence.
5. **Trusted supplier destination change (later):** monitor bank-account history instead of trusting the vendor display name; compare with verified bank migration.
6. **Household camouflage (later):** benign relationship evidence must remain visible but cannot automatically clear synchronized borrowing and recipient convergence.
7. **Coverage blind spot (P0 visibility):** missing login data should visibly reduce coverage; it must not create an assurance that a payment is safe.

Deepfake onboarding, insider collusion, refund pivots, collateral reuse, cross-product claims and feedback manipulation remain useful roadmap scenarios with explicit feed dependencies. Do not advertise working detection without the necessary evidence and implemented tests.

A protective-action recommendation should say who must verify what, using which established source, and at what point intervention could help. No claim of prevention is justified merely by displaying an alert. Independently verifying changed payment instructions follows [FBI BEC guidance](https://www.fbi.gov/how-we-can-help-you/common-frauds-and-scams/business-email-compromise?source=govdelivery). Deepfake-related institutional fraud is documented by [FinCEN](https://www.fincen.gov/news/news-releases/fincen-issues-alert-fraud-schemes-involving-deepfake-media-targeting-financial), but CSV transaction rules do not constitute a deepfake detector.

## Immediate handoff

- At T+0 assign A/C, confirm the actual start time, check organiser sample availability and lock the data/API examples.
- If no organiser samples arrive, use clearly labelled synthetic fixtures and keep schema assumptions explicit.
- Keep all six dashboard filters, all three formats, one extra loan scenario and preserved alert decisions inside P0.
- At T+95 start AP-03 only when R1-R13 pass. Otherwise fix defects. Freeze features at T+105.
- Record actual results, rehearse offline and package by T+120. The older 6 PM note does not extend this budget.
