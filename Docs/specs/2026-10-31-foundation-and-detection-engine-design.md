# Design: Team Foundation + Detection Engine (Workstream B)

Date: 2026-10-31 · Owner: mansh7763 (workstream B) · Builds on `Docs/STAGE1_PLAN.md` (revision 3) and `Docs/EVALUATION.md`

## Intent

Two things, in order:

1. **Foundation (first ~20 min):** a running backend skeleton and the shared data shapes, so all three workstreams can start in parallel. A and C get placeholder endpoints returning sample JSON and take over their files afterwards.
2. **Detection engine (B's own work):** a pure-Python function that turns canonical records into scored, explained, deduplicated alerts. It is the part the hidden tests most likely score, and it must pass the brief's calibration cases (a regular high-value payer is Low; the same transfer after an account takeover is High).

**Why this shape:** the engine has no database or web dependency, so it can be built and tested from minute one on a hand-written dataset, without waiting for A's ingestion or C's screens.

## Goals

- `uvicorn app.main:app` runs, `/api/health` answers, and every endpoint in plan 3.7 exists (placeholder or real).
- `schemas.py` is the single source of the shapes all three workstreams use.
- `run_detection(dataset, config)` implements plan 3.3–3.5: point-in-time profiles, P0 indicators, the four scoring units, ordered chains with floors, noisy-OR scoring, additive contributions, bands, dedupe keys, skipped-indicator reporting.
- Golden dataset + pytest cover the B-owned cases in `Docs/EVALUATION.md` sections 3 and 4.

## Non-goals (for Level 1)

- Persistence, case creation, ingestion, the dashboard query (A and C own these).
- P1 indicators (graph rings, Isolation Forest, claims, AP-03, structuring, impossible travel), rules simulation, the scorecard on synthetic data. They come after Level 1, on the same interfaces.
- Real-time or streaming scoring.

## Anti-goals (failure even if it "works")

- Flagging the regular high-value payer as Medium or High.
- Contributions that don't add up to the score, or any reason without evidence IDs.
- Different results for the same input (non-determinism, row-order dependence).
- A crash because a file (logins, applications, claims) or a column (name, address, device) is missing.
- Foundation that takes over A's or C's real work: placeholders only, then hand over.

## Constraints

- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, pandas, numpy, PyYAML, pytest (all already in `.venv`; `psycopg` added for Postgres).
- Folders follow `Docs/OWNERSHIP.md`. B's code lives only in `backend/app/{features,detect,graph,score}`, `backend/tests`, `evals/`.
- Config from the environment: `DATABASE_URL`, `GROQ_API_KEY`, `CORS_ORIGINS`, `PORT`.
- Level 1 gate at ~13:45 (plan section 6).

---

## Part 1 — Foundation

### File tree created

```
backend/
  requirements.txt          # pinned app stack, python 3.12 noted in a comment
  app/
    __init__.py
    main.py                 # FastAPI app, CORS from env, includes all routers   [shared]
    config.py               # reads env vars once                                 [shared]
    schemas.py              # all shared Pydantic shapes                          [shared]
    db.py                   # engine + session from DATABASE_URL (SQLite default)  [→ A]
    api/
      __init__.py
      records.py            # placeholder: ingest, demo load, records, customer 360, admin reset  [→ A]
      alerts.py             # placeholder: alerts list/detail                       [→ A]
      cases.py              # placeholder: cases list/detail/decision               [→ A]
      dashboard.py          # placeholder: dashboard summary                        [→ C]
      sample_data.py        # the fixed sample JSON the placeholders return         [→ A]
    ai/__init__.py          # empty                                                 [→ C]
    detect/router.py        # REAL from the start: /api/detect/run, /api/rules      [B]
  tests/
    test_health.py          # app starts, every contract endpoint returns 200
run.ps1 / run.sh            # start backend on :8000 (frontend line added by C)
.env.example                # DATABASE_URL, GROQ_API_KEY, CORS_ORIGINS, PORT, VITE_API_URL (names only)
```

`backend/app/detect/router.py` lives in B's folder rather than `api/`, so B never edits A's files.

### `schemas.py` contents

- **Canonical records** (input to the engine, output of A's ingestion): `Customer`, `Account`, `Transaction`, `LoginEvent`, `Application`, `Claim`, with the fields from plan 3.1. Mandatory fields are IDs, timestamps and amounts only; everything else is `Optional`.
- **Engine output:** `Signal`, `Contribution`, `Alert`, `AlertEntity`, `DetectionRun`.
- **Cases:** `Case`, `CaseEvent`, `CaseDecision` (request body), and the status enum `New | Requires Investigation | False Positive | Escalated | Confirmed Fraud | Closed`.
- **Enums:** `Band` (Low/Medium/High), `Category` (suspicious_transfer, account_takeover, shared_device, loan_application_fraud, duplicate_claim), `UnitType` (transaction, login_burst, device_cluster, application), `Direction` (risk, mitigating).
- **API wrappers:** `IngestReport`, `DashboardSummary`, `Page[T]`.

### Placeholder behaviour

Each placeholder returns a fixed, realistic example built from the schemas (e.g. 3 alerts: one High ATO, one Medium shared device, one Low lookalike), so C's screens show real-looking data and the shapes are checked by Pydantic. Placeholders are marked `# PLACEHOLDER — owner A replaces` at the top.

### Hand-over

One commit "Foundation", announced in chat. After it, A owns `db.py`, `api/records.py`, `api/alerts.py`, `api/cases.py`, `api/sample_data.py`; C owns `api/dashboard.py` and `ai/`. `schemas.py`, `main.py`, `config.py` are shared (change with a heads-up).

---

## Part 2 — Detection engine

### Interface

```python
def run_detection(dataset: Dataset, config: RulesConfig | None = None, run_id: str | None = None) -> DetectionResult
```

- `Dataset`: canonical pandas DataFrames, keyed `customers`, `accounts`, `transactions`, `logins`, `applications`, `claims`. Any may be missing or empty. `Dataset.from_frames(...)` and `Dataset.from_csv_dir(path)` build one (the latter used by tests and by A's demo load).
- `RulesConfig`: defaults from `detect/rules.yaml`, with overrides merged on top (A later stores UI overrides in the DB and passes them in).
- `DetectionResult`: `run: DetectionRun` (id, rules version hash, counts by band, indicators run, **indicators skipped with reason**) and `alerts: list[Alert]`.
- Pure function: no DB, no network, no clock (all time comes from the data). Same input → same output.

### Pipeline

```
Dataset ──▶ prepare (types, sort by timestamp+id, derive txn customer, link txn→device by login window)
        ──▶ profiles (point-in-time, per customer)
        ──▶ indicators (each declares required tables; missing → skipped)
        ──▶ assemble scoring units (transaction · login burst · device cluster · application)
        ──▶ chains (ordered, within window) → floors
        ──▶ score (noisy-OR → mitigation, with ATO suspension → floor → 0–100 → band)
        ──▶ explain (additive contributions, evidence IDs, plain-language reason per line)
        ──▶ alerts (dedupe key, evidence snapshot, linked entities)
```

### Modules (all in B's folders)

| Module | Responsibility |
| --- | --- |
| `detect/dataset.py` | `Dataset`, loading, `prepare()` (string IDs, UTC timestamps, sorting, derived links) |
| `features/profiles.py` | point-in-time customer baselines: prior median, MAD (floored), p95, max, counts, known beneficiaries, known devices, onboarding device, usual hours; segment and global fallbacks |
| `detect/indicators/transfers.py` | TX-01..05, HV-01 |
| `detect/indicators/devices.py` | DV-01..03 |
| `detect/indicators/logins.py` | LG-01..03 |
| `detect/indicators/applications.py` | AP-01..02 |
| `detect/indicators/mitigation.py` | MT-* (regular payee, recurring pattern, known device + location, tenure, household) |
| `detect/registry.py` | indicator registry: id, required tables, function; runs enabled ones, records skipped |
| `detect/rules.yaml` | weights, thresholds, windows, band cut-offs, chain floors (defaults) |
| `detect/units.py` | groups signals into the four scoring units; attaches prior-window LG/DV context to transactions; one alert per burst and per device |
| `score/chains.py` | ordered chain matching and floors (85 full ATO, 70 ATO with payee/money movement, 55 partial ATO, 80 loan mule) |
| `score/scoring.py` | noisy-OR with clamping, mitigation with ATO suspension, floor, banding |
| `score/explain.py` | additive contributions (risk lines, mitigation line, floor line), rounding remainder to the largest line, reason text with concrete values |
| `detect/engine.py` | `run_detection`, dedupe keys, `Alert` construction, run summary |
| `detect/router.py` | `POST /api/detect/run` (calls the engine on data A provides; until A is ready, on the golden dataset), `GET/PUT /api/rules` |

### Key rules (from plan revision 3, restated so this doc stands alone)

- **Point-in-time:** every feature for an event uses only strictly earlier events; baselines use earlier successful outbound transfers only.
- **Short history:** TX-03 and DV-03 skipped when the customer has < 5 prior events of that kind; the onboarding device is never "new".
- **HV-01 threshold:** p90 of all outbound amounts in the dataset unless configured; also fires at ≥ 50 % of balance when balance is known.
- **DV-02 without names/addresses:** neutral, reason "relationship assessment unavailable".
- **Mitigation suspension:** only when an LG signal is active in the chain window, not for DV-03 alone.
- **What counts as a "beneficiary change"** *(my call)*: a login-log row with `event_type = beneficiary_add`, **or** the customer's first transfer to a beneficiary they never paid before. The brief's login logs may not include a `beneficiary_add` event, so the transfer itself has to count.
- **Chains are ordered:** failed logins → success → (new device / reset / beneficiary change) → transfer, all within 24 h; anything before the login never completes a chain. High needs a beneficiary change or a transfer.
- **Contributions:** `cᵢ = −ln(1 − min(wᵢsᵢ, 0.99))`; risk line = `undamped × cᵢ/Σc`; mitigation = `damped − undamped`; floor = `final − damped`; integers sum exactly to the score.
- **Dedupe key:** `sha256(unit type + primary entity id + sorted event ids)`; the rules version (hash of the effective config) is stored on the alert, not in the key, so A can attach re-scored alerts to existing cases.
- **Determinism:** sort by (timestamp, id) everywhere; no randomness; no wall-clock time.

### Golden dataset and tests

`backend/tests/golden/` holds hand-written CSVs (customers, accounts, transactions, logins, applications) for about 8 customers, plus `expected.yaml` mapping each case to its expected band and category. Cases (IDs from `Docs/EVALUATION.md`):

| Customer | Cases |
| --- | --- |
| Regular high-value payer | LK-T1, LK-T5 (Low) |
| Same profile under ATO | LG-T1, LK-T6 (High) |
| Forgot password, no money moved | LG-T6 (≤ Medium) |
| Transfer before suspicious login | LG-T7 (no chain) |
| Normal small spender → big transfer to new payee | TX-T1, TX-T5, TX-T6 (High) |
| Rapid fan-out | TX-T2 (High) |
| Fixed EMI payer | TX-T4 (Low, no error) |
| Household on one device | DV-T2 (Low) |
| Unrelated customers on one device with loan apps | DV-T1, AP-T1, DV-T5 (High, one device alert) |
| Failed burst, no success | LG-T2, LG-T8 (one alert, ≤ Medium) |

Plus property tests on every golden alert: RS-P1 range, RS-P2 band consistency, RS-P3 additivity, RS-P4 monotonicity (add/remove a signal), RS-P5 floor, RS-P6 determinism, RS-P7 row-order independence, RS-P8 no single-indicator High, EX-01/02 evidence present and real. And skip tests: dataset with only customers + transactions runs and reports skipped indicators (ING-18).

### Build order

1. Foundation (Part 1) → commit and announce.
2. `schemas` engine types + `dataset.py` + golden CSVs + `expected.yaml` + failing tests.
3. Profiles + transfer indicators + scoring + explain → transfer cases pass.
4. Login indicators + units + chains → ATO cases pass.
5. Device + application + mitigation indicators → device, loan and lookalike cases pass.
6. Engine wrapper (dedupe, run summary, skipped) + router → property tests pass; hand `run_detection` to A.

## Left to the builder

- Exact default weights and thresholds in `rules.yaml`, chosen so the golden expectations pass (record them in the file with a one-line reason each).
- The wording of reason texts, as long as each names concrete values.
- Internal helper structure inside each module.
