# Foundation + Detection Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A running FastAPI skeleton with shared schemas and placeholder endpoints for the team, plus `run_detection()`, a pure-Python engine that turns canonical records into scored, explained, deduplicated alerts.

**Architecture:** The foundation is a FastAPI app whose routers return Pydantic-validated sample data until A and C replace them. The engine is a pipeline of pure functions over pandas DataFrames (prepare → profiles → indicators → scoring units → chains → score → explain → alerts) with no DB, network or clock. A hand-built golden dataset with expected bands drives TDD.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, pandas, numpy, PyYAML, pytest; `.venv` at repo root.

**Spec:** `Docs/specs/2026-10-31-foundation-and-detection-engine-design.md` (rules restated from `Docs/STAGE1_PLAN.md` revision 3; test IDs from `Docs/EVALUATION.md`).

## Global Constraints

- All commands run from `backend/` with `../.venv/Scripts/python -m pytest` (Git Bash) — written below as `pytest`.
- B writes only in `backend/app/{features,detect,graph,score}`, `backend/tests`, `evals/`. Foundation files for A/C are placeholders marked `# PLACEHOLDER - owner <A|C> replaces`.
- Config from env only: `DATABASE_URL` (default `sqlite:///./fraud.db`), `GROQ_API_KEY`, `CORS_ORIGINS` (comma list, default `http://localhost:5173`), `PORT` (default 8000).
- Engine is pure: no DB, network, wall clock or randomness. Sort by `(timestamp, id)` everywhere.
- IDs are strings exactly as given. Timestamps are tz-aware UTC.
- Bands: Low < 40, Medium 40–69, High ≥ 70. Floors: full ATO 85, ATO with money/payee movement 70, partial ATO 55, loan mule 80. Chain window 24 h, ordered.
- `cᵢ = −ln(1 − min(wᵢsᵢ, 0.99))`; integer contribution points sum exactly to the score.
- Short history: TX-03 / DV-03 skipped when < 5 prior events of that kind; onboarding device never new.
- HV-01 threshold default = p90 of outbound amounts; weight 0 (context only, never creates an alert alone).
- Commit after each task with the attribution line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; pull before push.

## Review Focus

1. **A customer with zero prior transactions** making a transfer: profile fields are empty; TX-01/02 must fall back to segment → global baseline, not crash or divide by zero. → test in Task 3.
2. **Logins without `device_id` or `ip`** (anonymised logs): DV indicators and transaction→device linking must skip those rows, not fail. → test in Task 5.
3. **Two events with the identical timestamp** for one customer (batch exports often do this): "strictly earlier" must use `(timestamp, id)` ordering so results are deterministic. → test in Task 3.
4. **Amounts as strings with commas or currency symbols** reaching the engine from A (`"1,50,000"`): `prepare()` must coerce or raise a clear `ValueError` naming the column, never silently produce NaN scores. → test in Task 2.
5. **A dataset with only `customers` + `transactions`**: the engine runs, login/device/application indicators appear in `indicators_skipped` with a reason. → test in Task 7.

---

## File Structure

```
backend/
  requirements.txt
  app/
    __init__.py
    config.py                     # env settings                          [shared]
    schemas.py                    # all shared Pydantic shapes            [shared]
    main.py                       # app + routers                         [shared]
    db.py                         # engine/session from DATABASE_URL      [→ A]
    api/__init__.py
    api/sample_data.py            # fixed sample objects                  [→ A]
    api/records.py                # placeholders                          [→ A]
    api/alerts.py                 # placeholders                          [→ A]
    api/cases.py                  # placeholders                          [→ A]
    api/dashboard.py              # placeholder                           [→ C]
    ai/__init__.py                #                                       [→ C]
    features/__init__.py
    features/profiles.py          # point-in-time baselines               [B]
    detect/__init__.py
    detect/dataset.py             # Dataset, prepare()                    [B]
    detect/config.py              # RulesConfig, load_rules()             [B]
    detect/rules.yaml             # defaults                              [B]
    detect/indicators/__init__.py
    detect/indicators/transfers.py   # TX-01..05, HV-01                   [B]
    detect/indicators/logins.py      # LG-01..03                          [B]
    detect/indicators/devices.py     # DV-01..03                          [B]
    detect/indicators/applications.py# AP-01..02                          [B]
    detect/indicators/mitigation.py  # MT-*                               [B]
    detect/registry.py            # Indicator registry, run + skip        [B]
    detect/units.py               # ScoringUnit assembly                  [B]
    detect/engine.py              # run_detection()                       [B]
    detect/router.py              # /api/detect/run, /api/rules           [B]
    score/__init__.py
    score/chains.py               # ordered chains, floors                [B]
    score/scoring.py              # noisy-OR, mitigation, band            [B]
    score/explain.py              # additive contributions                [B]
  tests/
    conftest.py                   # golden dataset fixture
    golden/build_golden.py        # writes golden CSVs + expected.yaml
    golden/*.csv, golden/expected.yaml
    test_health.py
    test_dataset.py
    test_transfers.py
    test_scoring.py
    test_logins_chains.py
    test_devices_apps.py
    test_engine.py                # golden cases + properties
run.ps1, run.sh, .env.example (repo root)
```

---

### Task 1: Foundation — skeleton, shared schemas, placeholders

**Files:**
- Create: `backend/requirements.txt`, `backend/app/{__init__,config,schemas,main,db}.py`, `backend/app/api/{__init__,sample_data,records,alerts,cases,dashboard}.py`, `backend/app/ai/__init__.py`, `backend/app/detect/{__init__,router}.py`, `run.ps1`, `run.sh`
- Modify: `.env.example` (add names only)
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Produces in `app/schemas.py` (all `pydantic.BaseModel`, `str` enums):
  - `Band = Low|Medium|High`; `Category = suspicious_transfer|account_takeover|shared_device|loan_application_fraud|duplicate_claim`; `UnitType = transaction|login_burst|device_cluster|application`; `Direction = risk|mitigating`; `CaseStatus = New|Requires Investigation|False Positive|Escalated|Confirmed Fraud|Closed`.
  - Records: `Customer(customer_id, name?, dob?, phone?, email?, address?, onboarding_date?, segment?)`, `Account(account_id, customer_id, product?, open_date?, status?, balance?: float)`, `Transaction(txn_id, sender_account, timestamp, amount: float, currency?, type?, channel?, beneficiary_account, beneficiary_name?, status?, customer_id?, device_id?, ip?)`, `LoginEvent(event_id?, customer_id, timestamp, device_id?, ip?, city?, country?, outcome, event_type?)`, `Application(application_id, customer_id, product?, amount?, timestamp, device_id?, ip?, phone?, email?, status?, disbursement_account?)`, `Claim(claim_id, policy_id, customer_id, incident_date, amount, description?, payout_account?, timestamp?)`.
  - Engine output: `Signal(indicator_id, entity_id, customer_id?, event_ids: list[str], event_time: datetime, strength: float, weight: float, direction: Direction, category: Category|None, reason: str, evidence_ids: list[str])`, `Contribution(indicator_id: str|None, kind: Literal["risk","mitigation","floor"], points: int, reason: str, evidence_ids: list[str])`, `AlertEntity(entity_type, entity_id, role: Literal["primary","linked"])`, `Alert(alert_id, detection_run_id, dedupe_key, unit_type: UnitType, primary_entity_id, customer_id?, event_ids, event_time, created_at, category: Category, product?, detection_types: list[str], score: int, band: Band, contributions: list[Contribution], entities: list[AlertEntity], evidence: dict[str, list[dict]], narrative: str, rules_version: str)`, `DetectionRun(run_id, rules_version, records_processed: dict[str,int], alerts_total: int, counts_by_band: dict[str,int], indicators_run: list[str], indicators_skipped: dict[str,str])`.
  - Cases/API: `Case(case_id, alert_ids, category, customer_id?, account_id?, score, band, status: CaseStatus, assignee?, notes?, created_at, updated_at)`, `CaseEvent(case_id, at, actor, from_status?, to_status, note?)`, `CaseDecision(status: CaseStatus, note?, actor="analyst")`, `IngestReport(batch_id, file_name, entity_type, accepted, rejected, skipped, conflicts, errors: list[dict], mapping: dict[str,str], unmapped: list[str])`, `DashboardSummary(records_processed: dict[str,int], alerts_total, counts_by_band, counts_by_category, counts_by_detection_type, over_time: list[dict], indicators_skipped: dict[str,str])`, `Page[T](items: list[T], total: int)`.
- Produces: `app.main.app` (FastAPI) with every route in plan 3.7 and `GET /api/health -> {"status":"ok"}`.

- [ ] **Step 1: Write `backend/requirements.txt`** — fastapi, uvicorn[standard], pydantic>=2, sqlalchemy>=2, psycopg[binary], pandas, numpy, openpyxl, pyyaml, python-multipart, rapidfuzz, faker, groq, python-dotenv, httpx, pytest (versions = those installed in `.venv`: `pip freeze`). Comment line: `# Python 3.12`.
- [ ] **Step 2: Write the failing test** `tests/test_health.py`:

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)

def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}

@pytest.mark.parametrize("method,path", [
    ("get", "/api/alerts"), ("get", "/api/alerts/ALT-1"), ("get", "/api/cases"), ("get", "/api/cases/CASE-1"),
    ("get", "/api/dashboard/summary"), ("get", "/api/records/transactions"), ("get", "/api/customers/C001/360"),
    ("get", "/api/rules"), ("post", "/api/detect/run"), ("post", "/api/demo/load"), ("post", "/api/admin/reset"),
])
def test_contract_routes_exist(method, path):
    assert getattr(client, method)(path).status_code == 200

def test_case_decision_placeholder():
    r = client.post("/api/cases/CASE-1/decision", json={"status": "False Positive", "note": "ok"})
    assert r.status_code == 200 and r.json()["status"] == "False Positive"
```

- [ ] **Step 3: Run** `pytest tests/test_health.py -v` → FAIL (`ModuleNotFoundError: app`).
- [ ] **Step 4: Implement** config, schemas, db (`get_engine()`, `SessionLocal`, SQLite `check_same_thread=False`), placeholder routers returning objects from `api/sample_data.py` (3 alerts: High ATO, Medium shared device, Low lookalike; 2 cases; 1 dashboard summary), `detect/router.py` with `POST /api/detect/run` returning a sample `DetectionRun` for now and `GET /api/rules` returning `{}`; `POST /api/ingest` accepting `UploadFile` and returning a sample `IngestReport`. `main.py` adds CORS from `CORS_ORIGINS` and includes all routers under `/api`. `run.sh`/`run.ps1`: `cd backend && ../.venv/Scripts/python -m uvicorn app.main:app --reload --port ${PORT:-8000}`.
- [ ] **Step 5: Run** `pytest tests/test_health.py -v` → all PASS. Run `uvicorn` once and open `/docs` → 200.
- [ ] **Step 6: Commit + push** `feat: backend foundation with shared schemas and placeholder endpoints`; tell the team in chat which files are now A's and C's.

---

### Task 2: Dataset, rules config, golden dataset

**Files:**
- Create: `app/detect/dataset.py`, `app/detect/config.py`, `app/detect/rules.yaml`, `tests/golden/build_golden.py`, `tests/conftest.py`, `tests/test_dataset.py`
- Generated: `tests/golden/{customers,accounts,transactions,logins,applications}.csv`, `tests/golden/expected.yaml`

**Interfaces:**
- Produces:
  - `@dataclass class Dataset: frames: dict[str, pd.DataFrame]` with `has(name) -> bool` (present and non-empty), `get(name) -> pd.DataFrame` (empty frame if absent), `Dataset.from_frames(**frames)`, `Dataset.from_csv_dir(path) -> Dataset` (reads every `<table>.csv` with `dtype=str`).
  - `prepare(ds: Dataset, cfg: RulesConfig) -> Dataset`: parse timestamps to UTC; coerce `amount`/`balance` (strip `,`, currency symbols, spaces) to float or raise `ValueError("transactions.amount: cannot parse '<value>' in row <n>")`; sort by `(timestamp, id)`; add `transactions.customer_id` from `accounts` when missing; add `transactions.device_id` / `device_link` (`"given"`|`"derived"`|`None`) from the customer's last successful login within `cfg.windows.link_minutes` before the txn; add `seq` (global order index) to every event table.
  - `RulesConfig` (Pydantic): `indicators: dict[str, IndicatorConfig(weight: float, enabled: bool=True, params: dict)]`, `mitigations: dict[str, IndicatorConfig]`, `bands: {medium: 40, high: 70}`, `floors: {ato_full: 85, ato_movement: 70, ato_partial: 55, loan_mule: 80}`, `windows: {chain_hours: 24, link_minutes: 30, burst_minutes: 15, success_after_burst_minutes: 30}`, `min_history: 5`, property `version -> str` (first 12 hex of sha256 of the sorted JSON).
  - `load_rules(overrides: dict | None = None) -> RulesConfig` (deep-merge overrides onto `rules.yaml`).
  - Fixture `golden` (session scope) → prepared `Dataset` of `tests/golden`; fixture `expected` → parsed `expected.yaml`.

- [ ] **Step 1: Write `rules.yaml`** with these starting weights (tuned later, each with a `# why` comment): TX-01 0.45, TX-02 0.30, TX-03 0.25, TX-04 0.40, TX-05 0.45, HV-01 0.0, DV-01 0.35, DV-02 0.35, DV-03 0.25, LG-01 0.30, LG-02 0.35, LG-03 0.35, AP-01 0.55, AP-02 0.30; mitigations MT-PAYEE 0.60, MT-RECUR 0.50, MT-KNOWN 0.20, MT-TENURE 0.15, MT-HOUSE 0.60. Params: TX-01 `z_min: 3`, TX-04 `count: 5, minutes: 60`, TX-05 `new_payees: 4, hours: 24`, DV-01 `min_customers: 3`, LG-01 `failures: 5`, AP-01 `min_applicants: 3`, AP-02 `count: 3, days: 7`, MT-PAYEE `min_prior: 3, tolerance: 0.25`, `floor_amount: 100`.
- [ ] **Step 2: Write `build_golden.py`** — deterministic (no randomness), base date `2026-09-01T00:00Z`, ~10 customers, each with ≥ 6 prior normal transfers and ≥ 6 prior successful logins on their usual device unless the case needs short history. Cases and `expected.yaml` entries (selector = `unit_type` + `event_id` or `entity_id`; expectation = `band` | `max_band` | `no_alert` + optional `category`, `one_alert_for`):
  - `LK-T5` C001 pays SUP-1 ₹200,000 monthly ×6, then ₹210,000 → `max_band: Low` (no alert or Low).
  - `LK-T6` C002 same history as C001; then 6 failed logins in 5 min, success on new device DEV-X, then ₹210,000 to SUP-1 → `band: High`, `category: account_takeover`.
  - `LG-T6` C003: 6 failures → password_reset → success on new device, no transfer within 24 h → `max_band: Medium`.
  - `LG-T7` C004: ₹150,000 transfer, *then* 6 failures → success new device; no later transfer → the transfer has no chain (`max_band: Medium`).
  - `TX-T1/T5/T6` C005: 8 transfers ₹2,000–5,000 to 3 payees, then ₹150,000 to new BEN-NEW → `band: High`, `category: suspicious_transfer`.
  - `TX-T2` C006: then 6 transfers in 20 min to 5 new payees → the last one `band: High`.
  - `TX-T4` C007: EMI ₹12,000 ×6 to BANK-EMI, then ₹12,000 → `no_alert`.
  - `DV-T2` C008 + C009: same surname and address, both use DEV-HOME → device cluster `max_band: Low`.
  - `DV-T1/AP-T1/DV-T5` C010–C013: different names/cities, all log in on DEV-RING (many logins), 4 loan applications from DEV-RING with the same phone within 3 days → device cluster `band: High`, `one_alert_for: DEV-RING`; each application `band: High`, `category: loan_application_fraud`.
  - `LG-T2/T8` C014: 6 failures in 5 min, no success → `one_alert_for: login_burst C014`, `max_band: Medium`.
- [ ] **Step 3: Run** `python tests/golden/build_golden.py` → CSVs + `expected.yaml` written.
- [ ] **Step 4: Write failing tests** `test_dataset.py`:

```python
def test_from_csv_dir_keeps_ids_as_text(tmp_path): ...   # "00123" stays "00123"
def test_prepare_derives_customer_and_device(golden):  # C002's ATO transfer -> customer C002, device DEV-X, device_link "derived"
def test_prepare_rejects_unparseable_amount():          # "abc" -> ValueError mentioning "transactions.amount"
def test_prepare_parses_formatted_amount():            # "1,50,000" -> 150000.0, "₹2,000" -> 2000.0   (Review Focus 4)
def test_rules_version_changes_with_override():        # load_rules().version != load_rules({"indicators":{"TX-01":{"weight":0.5}}}).version
```

- [ ] **Step 5: Run** `pytest tests/test_dataset.py -v` → FAIL; **implement**; re-run → PASS.
- [ ] **Step 6: Commit** `feat(detect): dataset preparation, rules config and golden dataset`.

---

### Task 3: Point-in-time profiles and transfer indicators

**Files:**
- Create: `app/features/profiles.py`, `app/detect/indicators/transfers.py`, `tests/test_transfers.py`

**Interfaces:**
- Consumes: `Dataset`, `RulesConfig`, `Signal`.
- Produces:
  - `transaction_profiles(ds: Dataset, cfg: RulesConfig) -> pd.DataFrame` indexed by `txn_id` with columns `prior_n, prior_median, prior_mad, prior_p95, prior_max, denom, z, is_new_payee (bool|None when prior_n < min_history), prior_same_payee_similar (int), baseline_source ("customer"|"segment"|"global")`. Prior = strictly earlier by `seq`, same customer, `status` successful (missing status = successful), outbound.
  - `denominator(median, mad, floor_amount) -> float = max(1.4826*mad, 0.1*median, floor_amount)`.
  - `transfer_signals(ds, cfg, profiles) -> list[Signal]` emitting TX-01..05 and HV-01 (`entity_id = txn_id`, `customer_id`, `event_ids=[txn_id, ...]`, `category = suspicious_transfer`, reasons with concrete values, e.g. `"₹150,000 is 41× the customer's usual ₹3,600"`).
  - `hv_threshold(ds, cfg) -> float` = configured value or p90 of outbound amounts.

- [ ] **Step 1: Write failing tests:**

```python
def test_fraud_amount_not_in_own_baseline(golden):        # C005 big txn: prior_max <= 5000 (TX-T5)
def test_first_payment_to_later_repeated_payee_is_new(golden)  # TX-T6
def test_emi_mad_zero_no_error_and_no_tx01(golden):       # C007 last EMI: denom >= 100, no TX-01 (TX-T4)
def test_no_history_uses_global_baseline():                # 1 customer, 0 prior -> baseline_source "global", finite z (Review Focus 1)
def test_same_timestamp_order_is_deterministic():          # two txns same ts, shuffled input -> identical profiles (Review Focus 3)
def test_regular_payer_no_tx01_tx02_tx03(golden):          # C001 last txn: none of TX-01/02/03, HV-01 present
def test_fanout_emits_tx04_tx05(golden):                   # C006 last txn has TX-04 and TX-05
def test_short_history_skips_tx03():                       # 2 prior txns -> is_new_payee None, no TX-03 (TX-T8)
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (per-customer loop over rows in `seq` order keeping running lists is fine at this size). **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(detect): point-in-time profiles and transfer indicators`.

---

### Task 4: Scoring and additive explanations

**Files:**
- Create: `app/score/scoring.py`, `app/score/explain.py`, `tests/test_scoring.py`

**Interfaces:**
- Produces:
  - `@dataclass ChainMatch(name: str, floor: int, evidence_ids: list[str], reason: str)` (defined here; Task 5 fills it).
  - `@dataclass ScoreBreakdown(undamped: float, damped: float, final: float, score: int, band: Band, mitigation_suspended: bool)` — floats on the 0–100 scale.
  - `score(risk: list[Signal], mitigating: list[Signal], chain: ChainMatch | None, suspend_mitigation: bool, cfg: RulesConfig) -> ScoreBreakdown`: `undamped = 100·(1 − Π(1 − min(wᵢsᵢ, .99)))`; `damped = undamped·Π(1 − mⱼ·sⱼ)` (skip when suspended — suspended applies only to MT-PAYEE, MT-RECUR, MT-TENURE); `final = max(damped, chain.floor)` if chain else `damped`; `score = round(final)`; band from `cfg.bands`.
  - `band_for(score: int, cfg) -> Band`.
  - `contributions(risk, mitigating, chain, breakdown) -> list[Contribution]`: risk line points ∝ `cᵢ` of `undamped`; one mitigation line per mitigating signal ∝ its `−ln(1−mⱼsⱼ)` share of `damped − undamped`; a floor line `final − damped` if > 0; largest-remainder rounding so `sum(points) == breakdown.score`.

- [ ] **Step 1: Failing tests** (pure, hand-made `Signal`s):

```python
def test_range_and_band(): ...                    # RS-P1/P2 over a grid of weights
def test_contributions_sum_exactly(): ...         # RS-P3, incl. mitigation and floor cases (20 with −30 damp; floor lifting 40→85)
def test_monotonic_add_risk_never_lowers(): ...   # RS-P4
def test_monotonic_add_mitigation_never_raises(): # RS-P4
def test_floor_beats_mitigation(): ...            # RS-P5: chain floor 85 + heavy mitigation -> 85
def test_weight_clamped_no_log_zero(): ...        # w*s = 1.0 -> finite
def test_single_indicator_never_high(cfg): ...    # RS-P8: every default indicator alone at strength 1 -> < 70
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS (if RS-P8 fails, lower the offending weight in `rules.yaml` and note why).
- [ ] **Step 5: Commit** `feat(score): noisy-OR scoring with floors and additive contributions`.

---

### Task 5: Login indicators, scoring units and ordered chains

**Files:**
- Create: `app/detect/indicators/logins.py`, `app/detect/units.py`, `app/score/chains.py`, `tests/test_logins_chains.py`

**Interfaces:**
- Consumes: `Dataset`, `transaction_profiles`, `transfer_signals`, `ChainMatch`.
- Produces:
  - `login_bursts(ds, cfg) -> list[Burst]` where `@dataclass Burst(customer_id, failure_ids: list[str], start, end, success_id: str|None, success_time, success_device: str|None, new_device: bool|None, after_actions: list[tuple[str, str, datetime]])` (`(kind, event_id, time)`, kind ∈ `password_reset|beneficiary_add|profile_change`).
  - `login_signals(ds, cfg, bursts) -> list[Signal]`: LG-01 per burst (≥ `failures` within `burst_minutes`), LG-02 if success within `success_after_burst_minutes`, LG-03 per sensitive action after LG-02 within `chain_hours`; DV-03 for the success device when new (respecting short history and onboarding device). Skip login rows with no `device_id` for DV checks (Review Focus 2).
  - `@dataclass ScoringUnit(unit_type: UnitType, primary_entity_id: str, customer_id: str|None, event_ids: list[str], event_time: datetime, product: str|None, signals: list[Signal], context: list[Signal])`.
  - `build_units(ds, signals: list[Signal], bursts: list[Burst], cfg) -> list[ScoringUnit]`: one per transaction with ≥ 1 risk signal or any context; LG/DV signals of a burst attach as `context` to the customer's transfers **after** the burst success within `chain_hours`; a burst becomes its own `login_burst` unit only when no transfer follows in that window; one `device_cluster` unit per device (DV-01/02); one `application` unit per application.
  - `match_chain(unit: ScoringUnit, bursts: list[Burst], cfg) -> ChainMatch | None`, ordered (burst success < new device/actions < transfer, all within `chain_hours`): `ato_full` (LG-02 + DV-03 + HV-01) 85; `ato_movement` (LG-02 then beneficiary change — `beneficiary_add` event **or** TX-03 on this transfer — or a transfer) 70; `ato_partial` (LG-02 + DV-03 or password_reset, no transfer; only on `login_burst` units) 55. `loan_mule` (AP-01 → AP-03) is reserved, returns None until AP-03 exists.

- [ ] **Step 1: Failing tests:**

```python
def test_one_burst_one_unit(golden):              # C014 -> exactly 1 login_burst unit (LG-T8)
def test_burst_without_success_not_high(golden):  # C014 score < 70 (LG-T2)
def test_ato_full_chain_high(golden):             # C002 transfer -> chain ato_full, score >= 85 (LK-T6)
def test_forgot_password_medium_max(golden):      # C003 -> ato_partial, 40 <= score < 70 (LG-T6)
def test_transfer_before_login_no_chain(golden):  # C004 transfer -> match_chain None (LG-T7)
def test_logins_without_device_skipped():         # rows with device_id None -> no DV-03, no error (Review Focus 2)
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(detect): login bursts, scoring units and ordered ATO chains`.

---

### Task 6: Device, application and mitigation indicators

**Files:**
- Create: `app/detect/indicators/devices.py`, `app/detect/indicators/applications.py`, `app/detect/indicators/mitigation.py`, `tests/test_devices_apps.py`

**Interfaces:**
- Produces:
  - `device_signals(ds, cfg) -> list[Signal]`: DV-01 per device with ≥ `min_customers` distinct customers (`entity_id = device_id`, evidence = login ids, `category = shared_device`); DV-02 risk when the customers do not share surname+address or any of them has an application/transfer from the device; DV-02 **mitigating** (`MT-HOUSE`) when all share surname and address; when name/address columns are missing → no DV-02, reason `"relationship assessment unavailable"` recorded on DV-01's reason.
  - `application_signals(ds, cfg) -> list[Signal]`: AP-01 per application whose device, IP, phone or email is shared by ≥ `min_applicants` distinct customers (`category = loan_application_fraud`); AP-02 ≥ `count` applications by one customer or device within `days`. Applications from a device that has a DV-01 also carry DV-01 as context.
  - `mitigation_signals(ds, cfg, profiles, bursts) -> list[Signal]` (direction `mitigating`): MT-PAYEE (≥ `min_prior` prior payments to the same payee within ±`tolerance` of the amount), MT-RECUR (monthly cadence ±3 days to same payee), MT-KNOWN (txn device known and city usual), MT-TENURE (onboarded ≥ 365 days before and no prior alerts in data).

- [ ] **Step 1: Failing tests:**

```python
def test_household_device_low(golden):           # DEV-HOME cluster score < 40 (DV-T2)
def test_ring_device_high_one_alert(golden):     # DEV-RING -> exactly 1 device_cluster unit, score >= 70 (DV-T1, DV-T5)
def test_ring_applications_high(golden):         # each C010–C013 application score >= 70 (AP-T1)
def test_no_names_relationship_unavailable():    # customers without name/address -> reason contains "unavailable" (review 2 #8)
def test_regular_payer_low(golden):              # C001 last txn: MT-PAYEE present, score < 40 (LK-T5)
def test_mitigation_suspended_only_by_login(golden): # C002: MT-PAYEE not applied (LG active); new device alone does not suspend
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS; tune weights in `rules.yaml` only if a golden case misses, with a `# why` comment.
- [ ] **Step 5: Commit** `feat(detect): device, application and mitigation indicators`.

---

### Task 7: Engine, registry, router and golden suite

**Files:**
- Create: `app/detect/registry.py`, `app/detect/engine.py`, `tests/test_engine.py`
- Modify: `app/detect/router.py` (replace placeholder)

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `@dataclass Indicator(id: str, requires: tuple[str, ...], kind: Literal["transfer","login","device","application","mitigation"])`; `REGISTRY: list[Indicator]`; `available(ds, cfg) -> tuple[list[str], dict[str, str]]` returning (ids to run, `{id: "missing table: logins"}` skipped).
  - `@dataclass DetectionResult(run: DetectionRun, alerts: list[Alert])`.
  - `run_detection(dataset: Dataset, config: RulesConfig | None = None, run_id: str | None = None) -> DetectionResult`: prepare → profiles → signals (enabled, available only) → bursts → units → per unit: chain, suspension flag (any LG signal in unit context/signals), `score`, `contributions`; alert for every unit with ≥ 1 risk signal of weight > 0; `dedupe_key = sha256(f"{unit_type}|{primary_entity_id}|{','.join(sorted(event_ids))}")`; `alert_id = "ALT-" + dedupe_key[:10]`; `run_id` default `"RUN-" + sha256(rules_version + dataset fingerprint)[:10]`; `created_at` = max event time in the dataset (keeps purity); `category` = chain category if a chain matched, else category of the highest risk line; `evidence` = the referenced rows from each table as dicts; `narrative` = the risk lines' reasons joined in score order.
  - `POST /api/detect/run` body `{"rules": {...overrides}}` optional → runs on the golden dataset until A provides a loader (`TODO(A): replace with DB-backed Dataset`) → returns `{"run": DetectionRun, "alerts": [Alert]}`. `GET /api/rules` → effective config; `PUT /api/rules/{indicator_id}` → in-memory override for now (`TODO(A): persist in rule_override`).

- [ ] **Step 1: Failing tests** `test_engine.py`:

```python
@pytest.mark.parametrize("case", EXPECTED_CASES, ids=lambda c: c["id"])
def test_golden_case(golden_result, case): ...   # every expected.yaml entry: band / max_band / no_alert / category / one_alert_for

def test_contributions_sum_and_evidence_exist(golden_result): ...   # RS-P3, EX-01, EX-02 on every alert
def test_deterministic(golden): ...                                  # two runs -> identical alerts JSON (RS-P6)
def test_row_order_independent(golden): ...                          # shuffled frames -> identical alerts (RS-P7)
def test_dedupe_keys_unique(golden_result): ...                      # no duplicate dedupe_key within a run
def test_only_customers_and_transactions(golden): ...                # Review Focus 5 / ING-18: runs; LG-*, DV-*, AP-* in indicators_skipped with "missing table"
def test_detect_endpoint_returns_alerts(): ...                       # TestClient POST /api/detect/run -> 200, alerts non-empty, Alert-valid
```

- [ ] **Step 2: Run** `pytest -v` → new tests FAIL. **Step 3: Implement.** **Step 4: Run** `pytest -v` → **all** PASS (Tasks 1–7).
- [ ] **Step 5: Commit + push** `feat(detect): run_detection engine, registry and detect API`; tell A the signature `run_detection(Dataset.from_frames(...))` and that `/api/detect/run` returns real alerts from the golden data.
