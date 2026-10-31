# Stage 01 Plan — Digital Fraud Investigation System

Date: 2026-10-31 · Source: `Docs/ProblemStatement-Stage-1.pdf`

**Bottom line:** Ship Level 1 as one working path, ingest → detect → score → alert → case, by about 14:00. Build it on an explainable, entity-centric risk engine that can grow into the later levels without a rewrite. We win on three things: robust ingestion (hidden tests), explanations that show both why risk went up *and* why it went down (the "legitimate lookalikes" requirement), and an identity graph that reveals coordinated fraud.

---

## 1. What the brief actually asks

### 1.1 Rules of the game (page 1)

| Rule | What it means for us |
| --- | --- |
| Level 1 suggested time 0–3 h | Lock the Level 1 scope (P0 below) by ~13:45, then move to P1 |
| Points for **observable behaviour**, not slides | Every feature must be clickable in the demo. Architecture talk earns nothing |
| **Unsupported AI claims** lose points | Deterministic explanations first. The LLM only rephrases evidence and must cite record IDs. No "AI-powered" label on rules |
| Synthetic / anonymised data only | Our generator makes all data. No real PII, no live payment calls |
| Organiser provides **schemas, sample data, hidden tests**, sandbox credentials, rubric | Ingestion must accept *their* files with different column names and dirty rows without crashing. **Action now:** ask the organisers where the schemas and sample data are |
| Organiser gives no AI keys | We use our own Groq keys. The app must still work fully with the LLM switched off |
| "Dashboard that reflects real behaviour, not a static dashboard" | Every number on screen is computed from the ingested data. Nothing is hard-coded |

### 1.2 Fraud scenarios the whole challenge covers (pages 2–3)

These shape the architecture even if Level 1 only tests part of them:

1. **Identity fraud and synthetic profiles:** inconsistent identity attributes, repeated contact details, odd links between "independent" customers.
2. **Device sharing and coordinated fraud:** many customers on one device, IP or phone. Legitimate sharing (family) must be recognised.
3. **Account takeover:** failed logins, password resets, device changes, unusual locations, then a large transfer or a beneficiary change.
4. **Cross-system organised fraud:** correlating lending, insurance and core banking. The brief's example: several loans under different identities on one device, paid into linked accounts, then sent out in unusual transfers.

### 1.3 Level 1 requirements, as a checklist

**1. Data ingestion and integration**
- [ ] Upload or select data from different systems: customers/accounts, transactions, device/login logs
- [ ] Accept CSV, Excel and JSON
- [ ] Validate uploads, flag missing mandatory fields, reject invalid data **with visible reasons** (never drop rows silently)
- [ ] One common data model linking records by customer, account, application, device and transaction IDs

**2. Detection rules and behavioural analysis** (configurable rules, statistics, ML, or a mix)
- [ ] Suspicious transfers: unusual amounts, rapid transfers, new beneficiaries, mismatch with the customer's history
- [ ] Shared devices: many profiles on one device, plus a judgement on whether the relationship is suspicious
- [ ] Repeated login failures: escalate when a success follows, especially before sensitive activity
- [ ] Legitimate lookalikes: do **not** flag normal behaviour that only looks suspicious
- [ ] At least one more scenario from the catalogue (suspicious loan applications **or** duplicate insurance claims)

**3. Risk assessment**
- [ ] 0–100 score and/or Low / Medium / High
- [ ] Combines several indicators; no single threshold
- [ ] High-value transfer from a customer who often makes similar ones is **not** automatically fraud
- [ ] Failed logins + new device + high-value transfer → much higher risk
- [ ] Shows the factors behind each risk level

**4. Fraud alert dashboard**
- [ ] Counts of processed records and flagged events, risk distribution, fraud categories
- [ ] Filters: customer, transaction, product, risk level, date, detection type
- [ ] Opening an alert shows the event, why it was flagged, and the supporting records

**5. Basic fraud case queue**
- [ ] Each actionable alert creates a case: unique ID, fraud category, customer/account, risk level, evidence, status
- [ ] User opens the case and records a decision: **Requires Investigation** or **False Positive**
- [ ] **The original alert is kept unchanged** when the case decision changes (audit trail)

**Submission:** a working app showing ingestion, detection, risk assessment, the alert dashboard and a basic case queue.

### 1.4 Reading between the lines

- **Later levels will probably be investigation, cross-system correlation, synthetic identity and AI case intelligence.** The opening section (pages 2–3) describes all four. A model built around entities (customer, device, account, application, claim) and the links between them gets us there without a rewrite.
- **Hidden tests most likely feed data files and check flags and scores.** Ingestion robustness and deterministic results matter more than visual polish.
- **"Legitimate lookalikes" is the trap.** A system that flags every big transfer fails it. Per-customer baselines and mitigating factors are the answer, and they make a strong demo.

---

## 2. How leading platforms do it (and what we borrow)

The release said institutions use hundreds of parameters. Leading platforms group those parameters into a few families: per-customer behaviour, device and network intelligence, entity resolution and graphs, and rules plus ML scoring with explanations, all feeding case management.

| Platform | Core idea | What we borrow |
| --- | --- | --- |
| **Featurespace ARIC** (now Visa) | "Adaptive Behavioural Analytics": a live behavioural profile per customer; each event is scored against *that customer's own* history. ARIC stands for Adaptive, Real-time, Individual, Change identification ([Finovate](https://finovate.com/?p=51769), [NVIDIA blog](https://blogs.nvidia.com/blog/2022/08/25/featurespace-blocks-financial-fraud)) | Per-customer baseline (median, MAD, p95, usual beneficiaries, devices and hours). Risk = deviation from *self*, which is exactly the lookalike requirement |
| **Quantexa** | Entity resolution builds a single view of each person or organisation across systems, then network analytics expose mule rings and lending fraud ([Quantexa fraud](https://www.quantexa.com/solutions/fraud), [Risk.net](https://www.risk.net/ja/node/7875606)) | Identity graph: customers linked through shared device, IP, phone, email, address and beneficiary account. Connected components = candidate rings |
| **Feedzai RiskOps** | One platform for fraud, identity and AML. Rules plus ML in one risk engine, "whitebox" explanations, an omnichannel case manager ([Feedzai RiskOps](https://feedzai.com/riskops), [AWS listing](https://aws.amazon.com/marketplace/pp/prodview-lis6xav4rqwgm)) | A hybrid score (rules + anomaly model) where each contribution is visible, with alerts and cases in one workflow |
| **NICE Actimize IFM-X** | End to end: ingestion → real-time risk score → decision → alert resolution. A library of fraud risk indicators plus ML; cross-channel and cross-payment ([NICE Actimize](https://www.niceactimize.com/press-releases/nice-actimize-announces-next-gen-fraud-management-platform-leveraging-advanced-ai-and-the-cloud-to-fight-fraud-and-enhance-customer-experience-338)) | A reusable **indicator library**: each rule is a named, versioned indicator with a reason code. One pipeline across banking, lending and insurance |
| **BioCatch** (now Visa) | Behavioural, device and session signals against a baseline of legitimate activity to catch account takeover; detects bots, malware and scams ([BioCatch ATO brief](https://www.biocatch.com/hubfs/BioCatch_Connect_SolutionBrief_2023.pdf?hsLang=en)) | Session-level ATO chain: failed logins → success → new device/location → reset → beneficiary change → large transfer, scored as one sequence |
| **LexisNexis ThreatMetrix** | A consortium "Digital Identity Network": device fingerprint, true location, VPN/proxy/Tor detection, a digital ID per persona ([LexisNexis](https://risk.lexisnexis.co.uk/products/threatmetrix)) | Device and IP intelligence features: device age, how many customers share a device, IP-to-location mismatch, impossible travel |
| Unit21, Sardine, SEON *(general knowledge, not checked today)* | No-code rule builders with backtesting; device and behaviour signals; AI-drafted investigation narratives | Rules editable as config, with a **what-if backtest** showing alert counts before and after a threshold change; an AI case summary |

**Takeaway:** none of these products relies on one model. They layer (1) behavioural deviation, (2) device/identity intelligence, (3) graph/entity context and (4) rules plus ML, then (5) explain and route to a case. We build a small but real version of each layer.

---

## 3. Solution architecture

```
                ┌──────────────────────────── Frontend (React) ──────────────────────────────┐
                │ Upload & data quality │ Dashboard │ Alert detail │ Case queue │ Graph │ Rules │
                └───────────────▲──────────────────────────────────────────────────▲────────┘
                                │ REST /api/*                                       │
┌───────────────────────────────┴───────────────────────────────────────────────────┴───────────┐
│ FastAPI backend                                                                                 │
│                                                                                                 │
│  [1] Ingestion        [2] Canonical store       [3] Feature & profile     [4] Detection engine  │
│  CSV/XLSX/JSON  ──▶   SQLite (customers,   ──▶   per-customer baselines ──▶ indicator library    │
│  header mapping       accounts, txns, logins,    velocity windows           (rules as config)   │
│  validation           devices, applications,     device/IP stats            + anomaly model     │
│  quarantine + report  claims)                    identity graph (NetworkX)  + graph detectors   │
│                                                                                    │            │
│  [7] AI case intelligence (Groq, optional)  ◀── [6] Alerts (immutable) & Cases ◀── [5] Risk     │
│  grounded summary, cited evidence,               decision log, audit trail       scoring +      │
│  next steps, report draft                                                         explanations  │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Canonical data model

Every source maps onto these tables. IDs are strings, stored exactly as given.

| Entity | Key fields | Links |
| --- | --- | --- |
| `customer` | customer_id, name, dob, national_id_hash, phone, email, address, onboarding_date, kyc_status, segment | → accounts, devices, applications, claims |
| `account` | account_id, customer_id, product (savings/current/loan/card/policy), open_date, status, balance | → transactions |
| `transaction` | txn_id, account_id, customer_id, timestamp, amount, currency, type, channel, beneficiary_id/account, beneficiary_name, status, device_id, ip | → beneficiary, device |
| `login_event` | event_id, customer_id, timestamp, device_id, ip, geo (city/country), outcome (success/fail), auth_method, event_type (login/password_reset/device_change/beneficiary_add) | → device |
| `device` | device_id, first_seen, os, fingerprint | ← many customers |
| `application` (lending) | application_id, customer_id, product, amount, timestamp, device_id, ip, phone, email, declared_income, status, disbursement_account | → device, account |
| `claim` (insurance) | claim_id, policy_id, customer_id, incident_date, amount, type, description, payout_account, timestamp | → account |
| `ingestion_batch` | batch_id, source_system, file_name, entity_type, accepted, rejected, errors[] | ← every row |
| `alert` | **immutable** snapshot (see 3.4) | → case |
| `case` + `case_event` | mutable case plus an append-only decision log | → alerts |

### 3.2 Ingestion that survives hidden tests

1. **Format sniffing:** `.csv` (encoding and delimiter detection), `.xlsx` (every sheet = a candidate entity), `.json` (array or `{records: [...]}`, nested objects flattened).
2. **Entity detection and header mapping:** column names are normalised (lowercase, strip spaces/underscores) and matched against an alias dictionary (`cust_id`, `customerId`, `customer id` → `customer_id`), with fuzzy matching (`rapidfuzz`) as a fallback. The UI shows the proposed mapping so the user can correct it.
3. **Validation** with Pydantic models per entity: required fields, types, date parsing, amount > 0, enum values, duplicate IDs, links to unknown records (e.g. a transaction for an unknown account → warning, still loaded).
4. **Quarantine, not silence:** invalid rows go to `rejected_rows` with row number + field + reason, shown in a **Data quality report** (accepted / rejected / warnings per file, downloadable).
5. **Idempotent:** re-uploading the same file does not duplicate records (upsert on ID).
6. **Two buttons:** "Load demo dataset" (our generator) and "Upload files", so a judge can always see the app working.

### 3.3 Detection: the indicator library

Each indicator is a small function plus a config entry (`rules.yaml`) with `id`, `name`, `category`, `weight`, `params` and `enabled`. It returns `Signal{indicator_id, entity, score 0–1, reason text, evidence_ids[], direction: risk|mitigating}`. Thresholds live in config and can be edited in the UI. That covers "configurable rules".

| ID | Indicator (scenario) | Logic | Level |
| --- | --- | --- | --- |
| TX-01 | Amount far above the customer's own norm | robust z = (amt − median) / (1.4826·MAD) over the customer's history; fallback to segment peers when history < 5 txns | P0 |
| TX-02 | Amount above the customer's p95 / historical max | amt > p95 and > 2× median | P0 |
| TX-03 | New beneficiary | beneficiary never paid before by this customer | P0 |
| TX-04 | Rapid transfers / velocity | ≥ N transfers or ≥ X total within T minutes (1 h, 24 h windows) | P0 |
| TX-05 | Fan-out to many new beneficiaries | ≥ k distinct new beneficiaries in 24 h | P0 |
| TX-06 | Unusual hour | txn hour outside the customer's usual hour band | P1 |
| TX-07 | Balance drain | transfer ≥ 80 % of the balance | P1 |
| TX-08 | Structuring | several transfers just under a reporting limit within 7 days | P1 |
| DV-01 | Device shared by many customers | distinct customers per device ≥ k | P0 |
| DV-02 | Shared-device relationship assessment | shared surname/address/household → **mitigating**; unrelated identities, different cities, applications or transfers from the shared device → risk | P0 |
| DV-03 | New device for this customer | device not seen in the customer's history | P0 |
| DV-04 | IP shared across many customers / IP-to-location mismatch / impossible travel | geo-distance ÷ time between logins > 900 km/h | P1 |
| LG-01 | Failed-login burst | ≥ N failures in T minutes | P0 |
| LG-02 | Failures followed by a success | success within T after the burst → ATO candidate | P0 |
| LG-03 | Sensitive action after a suspicious login | password reset, beneficiary add, profile change or large transfer within T of LG-02 | P0 |
| AP-01 | Several loan applications sharing device/IP/phone/email under different identities | per-attribute count of distinct applicants | P0 (extra scenario) |
| AP-02 | Application velocity | ≥ k applications from one identity or device in 7 days | P0 |
| AP-03 | Disbursement → rapid outbound transfer | loan credited, then ≥ 70 % sent out within 48 h to new beneficiaries | P1 |
| CL-01 | Duplicate insurance claims | same policy/customer + same incident date ± 3 days + amount within 5 % + description similarity ≥ 0.8 | P1 (second extra scenario) |
| ID-01 | Synthetic identity signals | one phone/email/address across "independent" customers; DOB/ID inconsistencies; thin file + quick credit applications | P1 |
| GR-01 | Ring detection | connected component in the identity graph with ≥ 3 customers and ≥ 1 alerting member | P1 |
| ML-01 | Multivariate anomaly | Isolation Forest on the transaction feature vector; contributes a **bounded** weight and never alerts alone | P1 |
| MT-* | **Mitigating factors** (lookalikes) | regular payee (≥ 3 prior payments of similar size), recurring pattern (salary/rent cadence), known device + usual location, long tenure + clean history, household device sharing | P0 |

**The "hundreds of parameters" story:** each indicator is computed over several time windows (1 h / 24 h / 7 d / 30 d) and several dimensions (customer, account, device, IP, beneficiary). About 25 indicators × windows × dimensions gives 150+ features. The feature catalogue screen (P1) lists them, which answers that comment from the release with something real.

### 3.4 Risk scoring and explanations

1. **Combine risk signals** with a noisy-OR, so many weak signals add up while no single one saturates the score:
   `risk = 1 − Π(1 − wᵢ·sᵢ)` over risk signals, where `wᵢ` is the indicator weight and `sᵢ` its strength (0–1).
2. **Combination bonuses** for known attack chains (from the brief):
   `LG-02 + DV-03 + TX-01/02 within 24 h → ×1.5` (ATO chain), `AP-01 + AP-03 → ×1.4` (loan mule chain).
3. **Mitigating signals** damp the score: `final = risk × Π(1 − mⱼ)`, capped so mitigation can never hide a full ATO chain.
4. **Scale to 0–100 and band it:** Low < 40, Medium 40–69, High ≥ 70 (configurable).
5. **Explanation** = an ordered list of contributions (`+32 Amount 6.4× customer median`, `+18 New beneficiary`, `−20 Regular payee: 5 similar payments in 90 days`). This is shown as a **waterfall bar** in the UI. Every line links to its evidence records.
6. **Entity rollup:** customer risk = max event risk plus a graph uplift from linked risky entities (P1).

The brief's two calibration cases become **unit tests**:
- A high-value transfer from a customer who regularly makes similar transfers → Low or Medium, not High.
- The same transfer after failed logins and a new-device login → High.

### 3.5 Alerts and cases

- **Alert** is created when score ≥ 40 or a hard rule fires. It holds: `alert_id`, created_at, event ref, customer/account, category, detection types, score, band, contributions[], **evidence snapshot (JSON copy of the records)**, rules version. **Never updated** (the API exposes no update for alerts).
- **Case** is opened per alert, or grouped per customer within 72 h (P1). It holds: `case_id`, alert_ids, category, customer/account, risk, status, assignee, notes.
- **Statuses:** `New → Requires Investigation → (Escalated) → Confirmed Fraud | Closed` or `New → False Positive`. Level 1 requires at least Requires Investigation and False Positive.
- **Decision log:** an append-only `case_event` row (who, when, from → to, note) for every change. The case page shows the original alert snapshot beside the current decision, which visibly meets "preserve the original alert".

### 3.6 AI case intelligence (deterministic first, LLM on top)

- **Always available, no LLM:** a template narrative built from the contributions ("Flagged because 3 failed logins at 02:10 were followed by a login from a new device in Lagos and a transfer of ₹4.8 L to a new beneficiary 12 minutes later").
- **With Groq (P1):** the evidence JSON goes to the model with a strict prompt. It returns `{summary, likely_typology, key_evidence:[{claim, record_ids}], recommended_actions, report_draft}`.
- **Grounding guard:** the backend checks that every `record_id` the model cites exists in the evidence. Any claim without a valid ID is dropped and the UI labels the section "AI-generated, verified against N records". This directly addresses "unsupported AI claims".
- **PII masking** before the call: names and phone numbers are replaced with tokens.

### 3.7 API contract (agree on this in the first 10 minutes)

| Method | Path | Owner | Returns |
| --- | --- | --- | --- |
| POST | `/api/ingest` (multipart, `entity_type` optional) | A | batch report: accepted, rejected, errors[], mapping |
| POST | `/api/demo/load` | A | loads the generated dataset |
| GET | `/api/records/{entity}?filters` | A | paginated records |
| GET | `/api/customers/{id}/360` | A | profile, accounts, txns, logins, devices, apps, claims, linked entities |
| POST | `/api/detect/run` | B | runs all indicators, writes alerts; returns counts |
| GET | `/api/rules` / PUT `/api/rules/{id}` | B | indicator config (weights, thresholds, enabled) |
| POST | `/api/rules/simulate` | B | alert counts before/after a config change (P1) |
| GET | `/api/graph/{entity_id}?depth=2` | B | nodes, edges for the link graph |
| GET | `/api/dashboard/summary?filters` | A | processed counts, flagged, by band, by category, by detection type, over time |
| GET | `/api/alerts?filters` · GET `/api/alerts/{id}` | A | alert list and detail (with contributions and evidence) |
| POST | `/api/cases` · GET `/api/cases?filters` · GET `/api/cases/{id}` | A | case CRUD |
| POST | `/api/cases/{id}/decision` | A | appends a decision; returns the case and its log |
| POST | `/api/cases/{id}/ai-summary` | C | grounded AI summary |

Shared Python types live in `backend/app/schemas.py` (Pydantic): `Signal`, `Contribution`, `Alert`, `Case`, `CaseEvent`. The frontend mirrors them in `frontend/src/types.ts`.

---

## 4. Feature priorities

| Tier | Feature | Why |
| --- | --- | --- |
| **P0 — Level 1 (by ~13:45)** | Multi-format ingestion, header mapping, validation, quarantine report | Required; hidden tests |
| P0 | Canonical model + demo data generator with labelled ground truth | Required; we need data to show |
| P0 | Indicators TX-01..05, DV-01..03, LG-01..03, AP-01..02, MT-* | The four required scenarios + one extra |
| P0 | Noisy-OR score, bands, mitigation, contribution list | Required risk assessment |
| P0 | Dashboard KPIs + 6 filters + alert detail with evidence | Required |
| P0 | Case queue, decision (Requires Investigation / False Positive), decision log, immutable alert | Required |
| **P1 — differentiators (after Level 1, or early if ahead)** | Contribution waterfall chart, risk-raising vs mitigating factors | Wins the lookalike story visually |
| P1 | Identity link graph + ring detection (GR-01), shared-device household check | Coordinated fraud; likely Level 2+ |
| P1 | Customer 360 timeline across banking, lending and insurance | Cross-system scenario |
| P1 | Duplicate claims (CL-01), loan disbursement → outbound (AP-03), structuring, impossible travel | More scenarios = more hidden tests passed |
| P1 | Grounded Groq case summary + report draft | AI that is checked, not decorative |
| P1 | Rules editor + what-if simulation | Configurability you can see |
| P1 | Detection scorecard: precision/recall per scenario on labelled synthetic data | Evidence our engine works |
| **P2 — future / pitch only** | Streaming (Kafka) real-time scoring, feedback-trained model (LightGBM + SHAP), graph neural nets, consortium device intelligence, behavioural biometrics, SAR filing integration, case SLA and assignment, RBAC | Roadmap slide |

---

## 5. Three workstreams

All three are equal in effort: each owns one layer end to end, plus one stretch differentiator. The contract in 3.7 lets everyone build against stub data from minute 15.

### Workstream A — Data platform, cases and API (owner: ____)

**Mission:** every byte enters cleanly, links correctly and is served to the UI. Owns persistence of alerts and cases.

- **Modules:** `backend/app/ingest/` (parsers, header mapper, validators, quarantine), `backend/app/models.py` (SQLAlchemy), `backend/app/api/` (records, dashboard, alerts, cases), `backend/app/datagen/` (synthetic data generator).
- **Features:**
  1. Canonical schema for the 7 entities + ingestion_batch + alert + case + case_event.
  2. CSV / XLSX / JSON ingestion with alias and fuzzy header mapping; data quality report; idempotent upserts.
  3. Synthetic data generator (Faker, seeded): ~200 customers, ~5k transactions, ~3k login events, ~150 loan applications, ~100 claims. Planted with **labelled** patterns: ATO chains, mule ring via shared device + loan applications, rapid fan-out, household device sharing (legit), regular high-value payers (legit lookalikes), duplicate claims. Also exported as CSV, XLSX and JSON files with deliberately dirty rows, to demo the validation.
  4. Dashboard summary endpoint with all 6 filters.
  5. Alert store (insert-only) and case API with the decision log.
  6. Customer 360 endpoint (P1).
- **Tools:** FastAPI, SQLAlchemy + SQLite, pandas, openpyxl, Pydantic v2, rapidfuzz, Faker.
- **Inputs:** uploaded files; `Alert` objects from B. **Outputs:** clean tables, REST endpoints, labelled demo dataset.
- **Depends on:** B for the `Alert` shape (fixed in 3.7). **Blocks:** B needs clean data (supply the generator CSVs by 12:00); C needs endpoints (stub JSON by 11:50).
- **Milestones:** 11:50 schema + stub endpoints · 12:00 generator v1 pushed · 12:45 ingestion with validation report · 13:15 alerts/cases/decision API · 13:30 dashboard filters.

### Workstream B — Detection and risk intelligence engine (owner: ____)

**Mission:** turn records into correct, explainable risk. Owns everything the hidden tests will most likely score.

- **Modules:** `backend/app/features/` (customer baselines, velocity windows, device/IP stats), `backend/app/detect/` (indicator library + `rules.yaml`), `backend/app/graph/` (NetworkX identity graph), `backend/app/score/` (noisy-OR, combos, mitigation, contributions), `backend/tests/`.
- **Features:**
  1. Behavioural profile per customer: median, MAD, p95, max, usual beneficiaries, devices, hours and cities; peer-segment fallback.
  2. P0 indicators TX-01..05, DV-01..03, LG-01..03, AP-01..02, MT-*; each returns a `Signal` with evidence IDs.
  3. Shared-device relationship check (household vs unrelated).
  4. Risk scoring with bands, combination bonuses, mitigation and the contribution list; alert generation.
  5. Unit tests for the brief's calibration cases and each scenario (pytest).
  6. P1: identity graph + ring detection, Isolation Forest signal, CL-01, AP-03, rules simulation endpoint, precision/recall scorecard against the generator's labels.
- **Tools:** pandas, numpy, scikit-learn (IsolationForest), NetworkX, rapidfuzz (claim description similarity), PyYAML, pytest.
- **Inputs:** canonical tables from A. **Outputs:** `Alert` objects to A's store; `/api/detect/run`, `/api/rules`, `/api/graph`.
- **Depends on:** A for the generator data (works on a hand-made CSV until 12:00). **Blocks:** C's alert screens need real alerts by ~13:00.
- **Milestones:** 11:50 `Signal` / `Alert` types + rules.yaml skeleton · 12:30 transfers + login indicators · 13:00 devices + loan apps + mitigation + scoring · 13:20 calibration tests green · P1 afterwards: graph, anomaly, claims, scorecard.

### Workstream C — Investigation experience and AI case intelligence (owner: ____)

**Mission:** make the system usable and the intelligence visible. Owns the demo and the AI layer.

- **Modules:** `frontend/` (React + Vite + Tailwind), `backend/app/ai/` (Groq client, prompts, grounding guard, PII masking, template narrative).
- **Features:**
  1. **Data screen:** upload (drag and drop, multiple files), mapping preview, data quality report, "Load demo data" button.
  2. **Dashboard:** KPI tiles (records processed, flagged, high-risk, open cases), risk-band distribution, category and detection-type breakdowns, alerts over time; the 6 filters.
  3. **Alert detail:** event, contribution list (waterfall in P1), supporting records table, plain-language explanation.
  4. **Case queue:** list with filters and status chips; case page with the original alert snapshot, evidence, decision buttons (Requires Investigation / False Positive / Escalate), notes, decision timeline.
  5. Template narrative (no LLM) for Level 1. P1: Groq grounded summary + report draft with a "verified against N records" label.
  6. P1: link graph view (react-force-graph) with ring highlighting; customer 360 timeline; rules editor with simulation.
- **Tools:** React, Vite, TypeScript, Tailwind, Recharts, react-force-graph-2d, axios; Groq SDK (JSON mode).
- **Inputs:** REST endpoints from A and B. **Outputs:** the full UI, `/api/cases/{id}/ai-summary`, the demo flow and the deck screenshots.
- **Depends on:** A's stubs (11:50) and B's alert shape. Builds on mock JSON until real endpoints are ready. **Blocks:** nobody, which is why C also owns the demo script and the submission.
- **Milestones:** 11:50 app shell + routing + types · 12:30 upload + dashboard on stubs · 13:00 alert detail + case queue on stubs · 13:30 switched to real API · 13:45 end-to-end demo → **submit Level 1** · P1 afterwards: graph, waterfall, Groq summary.

### Balance check

| | A | B | C |
| --- | --- | --- | --- |
| P0 effort | Ingestion + generator + 4 APIs | ~15 indicators + scoring + tests | 4 screens + template narrative |
| P1 differentiator | Customer 360, labelled dataset, dirty-file demo | Graph rings, anomaly model, scorecard | Waterfall, graph view, grounded AI |
| Hardest part | Header mapping on unknown schemas | Calibration (lookalikes vs ATO) | Making evidence readable at a glance |

### Integration rules

- Folders are owned: A = `backend/app/{ingest,models,api,datagen}`, B = `backend/app/{features,detect,graph,score}` + `backend/tests`, C = `frontend/` + `backend/app/ai`. `schemas.py` and `main.py` change only with a heads-up in chat.
- Merge to `main` at least every 45 minutes. The 13:15 and 13:35 slots are for integration only.
- A single command runs everything (`run.ps1` / `run.sh`: backend on :8000, frontend on :5173).

---

## 6. Level 1 timeline (today)

| Time | A | B | C |
| --- | --- | --- | --- |
| 11:30–11:50 | Repo scaffold (FastAPI), `schemas.py` together with B, stub endpoints | `Signal`/`Alert` types, rules.yaml skeleton | Vite + Tailwind shell, routes, `types.ts`, mock JSON |
| 11:50–12:45 | Generator v1 (12:00), ingestion + validation | Profiles, TX and LG indicators | Upload screen, dashboard on mocks |
| 12:45–13:15 | Alerts/cases/decision API | DV, AP, MT indicators, scoring, alert generation | Alert detail, case queue on mocks |
| 13:15–13:35 | **Integrate:** load demo → run detection → dashboard → case decision | Calibration tests; fix false positives | Switch to the real API |
| 13:35–13:50 | Test with the organiser's sample files (if given); fix mapping | Same | Run the demo path twice; **submit Level 1** |
| After L1 | Customer 360, dirty-file demo | Graph rings, anomaly, CL-01, scorecard | Waterfall, graph view, Groq summary |

**Level 1 done =** a judge can (1) upload CSV/XLSX/JSON and see a validation report, (2) run detection, (3) see the dashboard with filters, (4) open an alert and see why with evidence, (5) open its case, mark Requires Investigation or False Positive, and see the original alert unchanged with a decision log.

---

## 7. Risks

| Risk | Mitigation |
| --- | --- |
| Organiser schemas differ from ours | Alias + fuzzy mapping with a UI override; ask the organisers for the sample files now |
| Over-flagging (fails lookalikes) | Mitigation signals + calibration unit tests; threshold tuning via the scorecard |
| Unsupported AI claims | Template narrative is the default; LLM output is grounded and checked |
| Integration crunch at 13:30 | Contract fixed at 11:50; stubs from minute 20; merges every 45 min |
| Groq outage or slow Wi-Fi | AI is optional; the app works fully offline |

## Sources

- Featurespace ARIC — [Finovate](https://finovate.com/?p=51769), [NVIDIA blog](https://blogs.nvidia.com/blog/2022/08/25/featurespace-blocks-financial-fraud)
- Quantexa — [Fraud solutions](https://www.quantexa.com/solutions/fraud), [Risk.net award](https://www.risk.net/ja/node/7875606)
- Feedzai — [RiskOps](https://feedzai.com/riskops), [AWS Marketplace listing](https://aws.amazon.com/marketplace/pp/prodview-lis6xav4rqwgm)
- NICE Actimize — [IFM-X announcement](https://www.niceactimize.com/press-releases/nice-actimize-announces-next-gen-fraud-management-platform-leveraging-advanced-ai-and-the-cloud-to-fight-fraud-and-enhance-customer-experience-338)
- BioCatch — [Connect solution brief](https://www.biocatch.com/hubfs/BioCatch_Connect_SolutionBrief_2023.pdf?hsLang=en)
- LexisNexis ThreatMetrix — [Product page](https://risk.lexisnexis.co.uk/products/threatmetrix)

These are mostly vendor materials; their performance claims are unverified and only used for design inspiration.
