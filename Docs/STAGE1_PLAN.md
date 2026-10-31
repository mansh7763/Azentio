# Stage 01 Plan — Digital Fraud Investigation System

## 0. Revision 4: executable plan for a strict 120-minute deadline

Reviewed 2026-10-31. **This section controls the build scope, priorities, timing and corrections wherever older sections or other planning documents disagree.** Earlier design detail remains below for reference; its wall-clock milestones, expanded P0 list and cloud rollout are superseded. **T+0 is 12:50 on 2026-10-31:** feature freeze T+105 = 14:35, hard stop T+120 = 14:50. Owners: A Harsh, B mansh7763, C Bhuvan. Documentation changes are proposals, not implemented features or passed tests.

**Decision:** deliver upload -> validate/link -> detect -> explain risk -> dashboard -> case decision, locally, within two hours. Implement suspicious loan applications as the mandatory additional scenario. Reuse that same data to demonstrate identity reuse and lending-to-banking links. Only after the required journey passes, add one temporal money-flow extension. Creative value comes from combining evidence, testing innocent alternatives, and explaining the intervention point, rather than counting rules.

### 0.1 Official requirements and proof of completion

Source: `ProblemStatement-Stage-1.pdf`, visually reviewed pages 1-5. The larger pack repeats challenge 1; challenges 2-7 concern regulation, recommendations, credit warning, service voice, collections voice and claims leakage. They are not additional requirements for our submission.

**Two different lists must not be confused:** pages 2-3 describe the broader identity, device-sharing, ATO and cross-system fraud catalogue. Page 4 explicitly lists the Level 1 minimum behaviours: suspicious transfers, shared devices, repeated login failures and legitimate lookalikes, plus one additional scenario. Cover the broader catalogue cheaply through exact identity links and the loan scenario, without claiming that all identity/media/insurance capabilities are mandatory Level 1 implementations.

| ID | Official requirement | Required observable proof | Owner |
| --- | --- | --- | --- |
| R1 | p4: upload/select customer/account, transaction and device/login data; CSV, Excel, JSON | Upload CSV customers/accounts, XLSX transactions, JSON logins; display accepted records from each | A/C |
| R2 | p4: validate, identify missing mandatory information, never silently ignore invalid data | Dirty fixture produces file/row/field/reason; accepted + rejected + skipped equals input rows | A |
| R3 | p4: common structure, links through customer/account/application/device identifiers | Alert evidence joins login -> customer -> account -> transaction; loan -> customer/device/account | A/B |
| R4 | p4: suspicious transfers | Unusual amount relative to prior history, velocity and new beneficiary have working rules | B |
| R5 | p4: shared devices, assess suspicious relationship | Suspicious shared-device group alerts; ordinary family sharing does not become High | B |
| R6 | p4: repeated failures, especially subsequent success/sensitive activity | Failure burst detected; ordered new-device success then transfer receives higher risk | B |
| R7 | p4: legitimate lookalikes | Regular large payment, ordinary shared device, password recovery without payment have expected lower risk | B/C |
| R8 | p4: at least one additional scenario | Suspicious loan application has its own category, evidence and actionable case; not just a renamed shared-device alert | B |
| R9 | p4: multi-indicator risk, numeric 0-100 and/or bands, explained | Explain matched facts and mitigating context; regular large payment Low versus ATO High | B/C |
| R10 | p4: processed/flagged counts, risk distribution, fraud categories; six filters | Customer, transaction, product, risk, date, detection type all work on real results | C |
| R11 | p5: alert event, reasons, supporting records | Open alert and inspect source rows, IDs and ordered timeline | A/C |
| R12 | p5: actionable alert case, ID, affected entity, category, risk, evidence, status; decisions preserved separately | Record Requires Investigation then False Positive; original alert unchanged, both decisions retained | A/C |
| R13 | p1/p5: working end-to-end submission; synthetic/anonymised data, no unsupported AI claims | Fresh local start, full demo with network/LLM unavailable; describe rules honestly | All |

The official brief allows rules, statistics, ML or combinations. An LLM, graph database, autonomous agents, cloud deployment and production payment blocking are not prerequisites. Organiser schemas/hidden tests are mentioned but their actual contents are unavailable here; hidden-test expectations remain hypotheses. The 6:00 PM HackCulture deadline comes from the event briefing, not these five PDF pages. Treat it as the outer limit and T+120 as the team's own target; confirm it at the venue.

### 0.2 What actually fits

Assumption: three available human workstreams as in `OWNERSHIP.md`. This is an aggressive budget, not a guarantee. Existing working code may be reused only after a quick runnable check. No Nora service dependency is assumed.

| Build now (P0) | Conditional single extension (P1) | Defer beyond two hours |
| --- | --- | --- |
| FastAPI + SQLite + existing React/Vite UI approach; one canonical store | AP-03 loan disbursement -> rapid onward movement, rendered as an evidence table | Neo4j, vector DB, LangGraph, streaming, ML training, multimodal/deepfake classifiers |
| Explicit entity selector, exact aliases, visible row validation; CSV/XLSX/JSON | Maximum ten minutes, only if R1-R13 pass by T+95 | Fuzzy schema inference, rules editor/backtesting UI, automated entity merging |
| TX-01, TX-03, TX-04, HV-01; DV-01/02/03; LG-01/02/03; AP-01; basic exact ID-01; MT context | Prefer this extension to graphs or chat: reuses loan, account and transfer records | Isolation Forest, 5k/250k data generators, calibrated probability claims, cloud migration |
| Scores, evidence, all six filters, immutable alerts and two decisions | If AP-03 data is unavailable, spend the time on robustness; do not invent a disbursement | Duplicate-claim pipeline, insurer/provider analytics, live integrations, automatic holds |
| Small committed synthetic fixtures with positive/negative pairs; template explanations | No second extension | Multi-hop graph UI, PDF case export, full customer 360, extra case statuses |

AP-01 is the mandatory extra scenario, not an optional stretch. Basic identity detection is an exact shared-contact/identity-conflict check attached to a device/application cluster, not a new identity-resolution subsystem. Cross-system coverage in P0 is a lending application linked to bank/customer/device evidence; the complete loan-to-cash-out chain is P1. Insurance correlation remains an explicit coverage gap until insurance data and a detector exist.

### 0.3 Minute-by-minute execution and hard gates

| Elapsed | A: ingestion/store/cases | B: detection/risk | C: UI/dashboard/demo | Gate |
| --- | --- | --- | --- | --- |
| 0-10 | Lock minimal schemas, aliases and API examples | Lock signal/result types and paired fixtures | Start UI and confirm API calls | Assign A/C, app boots; no architecture debate after minute 10 |
| 10-30 | Three parsers, SQLite and rejection report | Transaction/login rules on fixtures | Upload and alert/detail/queue shell | One real uploaded file visible by T+30 |
| 30-55 | Linking, immutable alert insert, case decision API | Device/context/AP-01/ID-01, scoring | Dashboard counts, six filters, detail evidence | First full real upload-to-decision path by T+55 |
| 55-80 | Duplicate/conflict handling, cross-file joins | ATO/benign calibration; missing-data outcomes | Replace remaining mocks; decision history | Mandatory scenarios runnable by T+80 |
| 80-95 | Dirty files, restart persistence | Paired tests, temporal ordering, rerun stability | All R1-R13 checks and fixes | No P1 unless every gate passes |
| 95-105 | Help fix defects or supply explicit disbursement link | Optional AP-03 only if green | Optional flow evidence table | Feature freeze at T+105 |
| 105-115 | Fresh database/startup rehearsal | Final fixtures and rule version recorded | Rehearse five-minute demo | Repeatable run, no external services needed |
| 115-120 | Package code and run instructions | Record actual pass/fail results | Save demo evidence and submit | Hard stop at T+120 |

If T+30 slips, drop fuzzy mapping, elaborate styling and all P1 immediately. If T+55 slips, all three focus on integration; keep mandatory formats, cases and the extra scenario. If T+80 slips, use the simplest evidence tables and fixed config instead of charts/editors. Do not present an incomplete mandatory capability as complete. If fewer people are available, re-estimate at T+0 and report the risk; do not quietly assume six person-hours of work can fit into two.

### 0.4 Correctness changes to apply before coding

1. **No future leakage:** all baselines, device novelty, contacts, clusters and chains use records at or before the scoring cutoff; the event being scored is excluded from its own history. HV-01 uses a configured per-currency threshold or p90 of prior successful outbound events in that currency, never all loaded transactions. Do not compare INR and USD together. Balance drain requires the balance immediately before the payment; unknown/post-payment balance means skip that feature.
2. **History uncertainty:** keep observed novelty as a fact but disable standalone novelty points below five prior relevant events. An independently supplied device-change event can still support ATO. First-seen-in-file is not proof of a genuinely new device. No usable baseline means `insufficient_history`, not a declaration of safety. Peer fallback also uses prior same-currency data only.
3. **Correlated rules:** TX-01 and TX-02 measure the same amount abnormality; implement only TX-01 in P0. Group related signals and use the maximum weighted strength within each family before combining families. Phone formatting variants are one fact, not multiple independent identity signals.
4. **ATO order:** failures precede a successful login whose device is new; that success is the new-device event, not a separate later timestamp. Sensitive change/payment follows it within the configured window. Equal timestamps need a trustworthy source sequence, otherwise order is unresolved. A payment before the login cannot complete the chain. Use one configurable chain window (initially 30 minutes for the demo); retain the evidence timestamps.
5. **ATO calibration:** new-device success + failure burst + high-value transfer gives a floor of 85. Recovery/new phone without payment or beneficiary change remains at most Medium. Remove the old automatic High floor for any payment after login failures: an ordinary payment from the usual device is not sufficient. A suspicious beneficiary-change chain needs corroborating access-context evidence for High.
6. **Mitigation:** same surname/address is only possible household context, not verified kinship. Shared IP can be an office/NAT; missing names/addresses mean unknown. Established regular behaviour may reduce risk, but must not erase a corroborated takeover chain. Mere login failures alone do not suspend all mitigations.
7. **Linking:** exact sender-account -> customer link first. Nearest prior login is a time-based inference, not proof that its device initiated a payment. Show `derived` and any competing session; do not use an ambiguous derived link to assert a confirmed ATO chain. No guessed joins by similar names.
8. **Reruns:** identity of a run is dataset snapshot hash + rules version + cutoff. Same completed run returns its existing result; it must not create an empty latest run after skipping all alerts. New versions create immutable snapshots and reuse a case by stable incident key. Show the latest completed run for the selected dataset, retaining older evidence. Device clusters/bursts have a fixed window key; member changes do not generate arbitrary case identities.
9. **Scope and data quality:** unknown fields/absent feeds are visible. Store `evaluated`, `skipped_missing_data`, `insufficient_history`, `unresolved_link` independently of risk. Missing login data is not evidence of a clean login. A bad feed is an operational/data-quality issue unless separate evidence establishes abuse.
10. **Audit safety:** keep SQLite update/delete protection on original alerts and append-only decisions. Drop the public table-dropping `/api/admin/reset` endpoint; use a separate disposable local demo database for rehearsals. Production controls and Postgres trigger parity are deferred.

### 0.5 Minimum data and scoring contract

Keep existing endpoint/type names in section 3.7 where practical; implement only ingest, demo load, records, detect, dashboard, alert list/detail, case list/detail and case decision for P0. No rules/graph/AI/admin endpoints are needed. File-based `rules.yaml` plus stored version/hash is enough for configurable deterministic rules.

| Entity | Minimum usable data | Optional context / limitation |
| --- | --- | --- |
| Customer/account | customer_id; account_id -> customer_id | Contacts, onboarding, identity token, household verification; all IDs strings |
| Transaction | txn_id, sender_account, beneficiary_account, timestamp, amount, currency, status | Channel/product; session/device if explicitly supplied; no FX guessing |
| Login/event | event_id or stable generated ID, customer/account reference, timestamp, outcome/event_type | device_id, IP, location; missing device disables new-device inference |
| Application | application_id, customer_id, timestamp, product | device/contact and payout account; AP-01 needs sufficient linked attributes |
| Provenance | dataset/batch, source system/file/sheet/row, raw record, event and ingestion time | Preserve raw fields beside normalized values |
| Detection result | unit/incident key, cutoff, rule version, score/band, category, reasons, evidence, coverage status | Direct/derived relationship labels; proposed protective action |

Import unresolved parent references with warnings; rerun linking when parents arrive. Exact duplicate row is skipped and counted; same key with different content is a conflict, not an overwrite. Invalid amount/date/mandatory key is quarantined with a reason. Keep labels such as `is_fraud` in the evaluation fixture manifest, never as detector inputs. Keep explicit supported date/timezone conventions; ambiguous dates require mapping or a visible rejection.

Use the existing noisy-OR formula over independent signal families: `raw = 100 * (1 - product(1 - family_strength))`; apply bounded contextual mitigation, then applicable chain floor, clamp to 0-100. Low <40, Medium 40-69, High >=70. These are prototype ranking scores, not fraud probabilities. Clamp strengths below 1; zero active signals means zero contribution, not division by zero. Show risk contributions summing to raw, negative mitigation, floor adjustment and final score. Group contributions make double-counting visible.

Scoring units remain transaction, login burst, device/identity cluster and application. Link a burst to its payment incident when present; preserve the burst evidence. Every evaluated unit can have a Low result, but actionable Medium/High alerts create cases. Dashboard distinguishes accepted source rows, evaluated units and flagged incidents; they are different denominators. Show low-risk lookalikes in results even when no alert was raised. Risk distribution is explicitly labelled by evaluated unit; fraud-category counts need not sum to incident count if multi-label categories are used.

Initial detector parameters (configurable hypotheses, validate on fixture pairs): failure burst >=5 in 10 minutes; transfer velocity >=5 in 20 minutes; shared device >=3 distinct customers; loan cluster >=3 applicants in 72 hours. Counts alone are not High: require independent behavioural/identity corroboration. AP-01 uses multiple applicants + common device plus shared contact/payout or identity conflict; same office IP/employer alone stays Low. A compact identity-conflict rule surfaces inconsistent DOB for the same supplied identity token as a review reason, without declaring synthetic identity proven.

### 0.6 Creative fraud catalogue: observable evidence and how to interrupt it

These are proposed, testable scenarios, not claims of observed fraud or implemented detection. The existing research section 32 contains 32 broad families; this shortlist turns the most useful ones into build decisions and adds compound variants. Every detector needs a benign pair and a missing-data test. Controls below are recommendations displayed in a case; any simulated action is labelled **simulation**. The prototype does not actually stop bank payments.

| Pattern / priority | Evidence and proposed detection | Innocent alternative / missing evidence | Protective response to recommend |
| --- | --- | --- | --- |
| F01 Identity stitching / P0 basic | Conflicting identity attributes or repeated contact across distinct profiles, corroborated by shared device and loan activity | Family contact, data-entry error; no proof of forged documents | Independently reverify identity and account ownership before loan approval |
| F02 Shared-device loan swarm / P0 extra | >=3 applicants in 72h, same device plus contact/payout overlap; separate application-category alert | Assisted branch applications; legitimate shared employer/IP | Review linked applications together; verify each borrower and payout owner |
| F03 ATO journey / P0 | Failure burst -> new-device success -> unusual/high-value transfer or suspicious payee change | Forgotten password, replacement phone, ordinary follow-up payment | Verify via established independent channel; propose session revocation and payment review |
| F04 Loan-to-mule funnel / first P1 | Explicit application/disbursement/account link, then >=70% aggregate successful outflow in 48h plus new recipient/network evidence | Loan used to pay a genuine supplier; current balance is not disbursement amount | Payout ownership review and receiving-account investigation; suggest hold only before settlement |
| F05 Recipient convergence despite different devices / later | Several apparently unrelated borrowers pay the same new recipient shortly after funding | Dealer/merchant collection account; device independence does not prove innocence | Verify recipient business purpose; group linked cases instead of only device alerts |
| F06 APP scam with a normal login / later | Usual device and successful authentication, but unusual new-payee payment plus recipient complaints or independent risk facts | Legitimate first-time purchase; absence of complaints is unknown, not clean | Contextual scam warning and independent callback; step-up login alone may not prevent authorised deception |
| F07 Recovery/contact substitution / later | Recovery/contact change -> changed access -> new payee/payment | Customer moved or replaced phone; requires profile-change feed | Confirm through previously verified channel, not the just-changed phone/email; cooling period |
| F08 Trusted supplier, changed destination / later | Same vendor identity/invoice context but bank account changed before payment | Legitimate bank migration; needs versioned payee/vendor records | Independent callback and dual approval of bank-detail changes |
| F09 Dormant account awakening / later | Long observed inactivity -> access/context change -> new-recipient transfer burst | Seasonal business, resumed account use; short file history cannot establish dormancy | Review access and purpose; targeted verification before sensitive transfers |
| F10 Slow cumulative drain / later | Individually modest payments but rolling cumulative outflow/new-payee concentration diverges from prior history | Tuition instalments or recurring bills; require sufficiently long history | Aggregate exposure review and customer confirmation rather than one-payment threshold |
| F11 Temporal circular flow / later | A -> B -> C -> A ordered same-currency transfers with repeated timing/value pattern | Treasury sweep, refund, settlement | Source/purpose verification; preserve paths; do not sum repeated hops as new loss |
| F12 Loan-and-claim bridge / later | Borrowers and claimants share payout recipient plus corroborating device/document links across products | Same legitimate provider or broker; requires claim/policy feed | Joint lending/insurance review and independent payout-ownership verification |
| F13 Reused claim invoice / later | Same invoice/incident/entity across distinct claims; detect exact structured duplicates first | Instalments, correction/resubmission, routine repeated treatment | Verify original invoice and settlement status before further payment |
| F14 Claim-provider cluster / later | Repeated claimant-provider-payee relations with abnormal billing versus comparable providers | Large specialist hospital; volume alone insufficient | Sample audit with provider/service context; no automated denial |
| F15 Collateral reused across identities / later | Same asset identifier in overlapping active loans with inconsistent claimed ownership | Refinance or released security; needs asset/loan lifecycle data | Verify ownership and existing encumbrances before disbursement |
| F16 Income evidence mismatch / later | Declared income/employer inconsistent with observed credits plus repeated document/contact patterns | Cash income, missing bank accounts, job change | Independent employer/income verification; absence of salary is not proof of fraud |
| F17 Refund destination pivot / later | Refund bank differs from original payer and follows profile change, across repeated linked orders | Approved refund exception; requires original-payment/refund references | Return to original instrument or obtain independently reviewed exception |
| F18 Insider exception concentration / roadmap | Unusual override clusters tied to payout changes, missing second approval and linked recipients | Authorised operational backlog; needs employee/approval audit data | Dual control, restricted audit review and immutable approval records |
| F19 Feed/control blind spot / P0 visibility, later abuse detection | Missing login feed, duplicate IDs, schema changes or abnormal timestamp gaps | Integration outage; data quality does not establish malicious intent | Coverage warning, quarantine invalid rows, reconcile source counts; never show complete protection |
| F20 Deepfake-assisted onboarding / roadmap | Trusted liveness/document-provider findings corroborated by identity inconsistency and reuse | Verification error; no media/provider fields in baseline data | Layered identity checks and human review; no claim of deepfake detection from CSV transaction data |
| F21 False-positive feedback laundering / roadmap | Repeated dismissals by one reviewer tied to recipient cluster despite unchanged evidence | Experienced specialist handling legitimate exceptions | Sample independent review; no automatic allowlisting/retraining from a case decision |
| F22 Household camouflage / later compound variant | Shared-address/device context looks benign, but independent profiles converge on a payout destination and synchronized borrowing | Genuine family financing; relationship context alone neither convicts nor clears | Keep benign evidence visible while independently verifying each application and recipient |

F04 should compute outflow only after an explicitly linked disbursement and through the evaluation cutoff, excluding failed/reversed transfers and handling refunds consistently. Without provenance, say 'rapid outflow following a credit', not 'stolen loan proceeds'. Fungible balances mean temporal proximity does not prove the exact money's path. External recipients can be nodes without known customer ownership; do not invent it.

For every built scenario show: **observed facts -> suspicious hypothesis -> benign alternative -> missing evidence -> proposed action**. A suggested pre-settlement hold can prevent exposure; a settled payment needs recovery/escalation review. Displaying a recommendation is not evidence that a loss was prevented.

External grounding checked for this review: FinCEN documents deepfake-related fraud against financial institutions ([13 November 2024 alert](https://www.fincen.gov/news/news-releases/fincen-issues-alert-fraud-schemes-involving-deepfake-media-targeting-financial)); it does not validate our detector. FBI guidance supports independent verification of changed payment instructions ([Business Email Compromise](https://www.fbi.gov/how-we-can-help-you/common-frauds-and-scams/business-email-compromise?source=govdelivery)). Remaining catalogue rows are design hypotheses adapted from the supplied research, not prevalence or accuracy claims. Vendor ownership/product-gap assertions in older sections have not been reverified and are not needed in the pitch.

### 0.7 Acceptance fixtures and five-minute demo

Use 12-20 synthetic customers and enough prior records to exercise baselines (roughly 100-300 events). Build fixtures directly before writing a large generator. Keep no-fraud and fraud labels separately. All expected outputs below are targets until executed.

| Test | Pair or mutation | Expected outcome |
| --- | --- | --- |
| G1 | Regular high-value supplier payment / identical payment after corroborated ATO | Low / High, with concrete evidence and suspended mitigation reason only in second |
| G2 | Ordinary family shared device / device plus multi-identity coordinated loan applications | Low / actionable loan and shared-device findings with distinct reasons |
| G3 | Failure burst alone / failure-success-new-device-payment chain | Low or Medium / High; no per-failure case flood |
| G4 | Ordinary new phone with reset and no payee/payment / anomalous transfer to new payee | First <=Medium; second shows amount and beneficiary evidence |
| G5 | Five rapid transfers to new recipients / established scheduled business payments | Burst elevated; benign context reduces unsupported suspicion |
| G6 | Payment before login attack / payment after | First not ATO; second can match; future events do not change earlier score |
| G7 | Same office IP/employer alone / corroborated device + payout/contact overlap | First not High; second reviewable application cluster |
| G8 | No login feed, short history or unresolved account / complete fixture | Explicit coverage limitation versus evaluated result; never silently safe |
| G9 | CSV/XLSX/JSON versions and dirty variants | Same logical detections; invalid rows explained, IDs preserve leading zeros |
| G10 | Same files/run twice, then case decisions, then restart | Stable counts/case IDs; original alert unchanged; decision log persists |
| G11 | Shuffle rows, add future rows or duplicate amount indicator | No order/future leakage or double-counting inflation |
| G12 | Optional F04 / ordinary loan-funded supplier payment | Flow alert requires corroboration; benign payout remains explained |

Also check all six filters individually and together, score bounds/contribution sums, live KPI reconciliation and original-alert immutability. `EVALUATION.md` remains the extended test library, but its clock times, dataset sizes, score targets and conflicting rules are superseded by this section. Report actual test counts and synthetic scope, not unmeasured precision/recall or production accuracy. Separate newly added tests from legacy tests whose expectations need correction.

Demo: (0:00-0:45) upload mixed formats and show a dirty row; (0:45-1:30) compare ordinary high payment with ATO; (1:30-2:15) family device versus loan swarm and identity evidence; (2:15-3:00) filters and source-record timeline; (3:00-4:00) case decisions and preserved alert; (4:00-5:00) rerun stability, coverage limitation and F04 only if implemented. Change an input or use the paired fixture so judges see recomputation. Proposed action card explains how intervention could work without claiming live blocking.

**Submission gate:** R1-R13 demonstrated, fixture results recorded, reproducible local start command/README, original alert preserved, all advertised features actually working. Package by T+120; no new features after T+105.

---


## Historical design detail (Revisions 1-3; subject to section 0)


Date: 2026-10-31 · Source: `Docs/ProblemStatement-Stage-1.pdf`

**Bottom line:** Ship Level 1 as one working path, ingest → detect → score → alert → case, by about 14:00. Build it on an explainable, entity-centric risk engine that can grow into the later levels without a rewrite. We win on three things: robust ingestion (hidden tests), explanations that show both why risk went up *and* why it went down (the "legitimate lookalikes" requirement), and an identity graph that reveals coordinated fraud.

**Revision 2 (11:50):** all 19 items from the first review are applied. Each change is marked "(suggestion #N)" where it lands.

**Revision 3:** all 24 items from the second review in `Docs/suggestions.md` are applied, marked "(review 2 #N)". Main changes: four defined scoring units (3.4), corrected contribution maths, ordered attack chains with a Medium floor when no money moved, latest-run-only dashboard, delete-proof alerts, and a deployment plan (section 8). Item 13 (owner names and emails) is for each teammate to fill in.

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
│  CSV/XLSX/JSON  ──▶   SQLite / Postgres    ──▶   per-customer baselines ──▶ indicator library    │
│                       (customers,                                                               │
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

**Database (review 2 #16):** SQLite locally (each person keeps their own data, and work continues if the venue network fails); **Aiven Postgres when deployed**. One SQLAlchemy codebase, selected by `DATABASE_URL` (`sqlite:///./fraud.db` by default; the Aiven URL needs `sslmode=require`). Write only SQL that works on both, except the immutability triggers (3.5).

| Entity | Key fields | Links |
| --- | --- | --- |
| `customer` | customer_id, name, dob, national_id_hash, phone, email, address, onboarding_date, kyc_status, segment | → accounts, devices, applications, claims |
| `account` | account_id, customer_id, product (savings/current/loan/card/policy), open_date, status, balance | → transactions |
| `transaction` | txn_id, sender_account, timestamp, amount, currency, type, channel, beneficiary_account, beneficiary_name, status · *optional:* customer_id, device_id, ip | → beneficiary, device |
| `login_event` | event_id (hash-generated if missing), customer_id, timestamp, device_id, ip, geo (city/country), outcome (success/fail), auth_method, event_type (login/password_reset/device_change/beneficiary_add) | → device |
| `device` | device_id, first_seen, os, fingerprint | ← many customers |
| `application` (lending) | application_id, customer_id, product, amount, timestamp, device_id, ip, phone, email, declared_income, status, disbursement_account | → device, account |
| `claim` (insurance) | claim_id, policy_id, customer_id, incident_date, amount, type, description, payout_account, timestamp | → account |
| `ingestion_batch` | batch_id, source_system, file_name, entity_type, accepted, rejected, errors[] | ← every row |
| `alert` | **immutable** snapshot (see 3.5): `detection_run_id`, `dedupe_key`, nullable `product`, `event_time` | → case |
| `alert_entities` | alert_id, entity_type, entity_id, role (primary/linked) | one alert ↔ many customers, accounts, devices or events (shared device, ATO chain) |
| `case` + `case_event` | mutable case plus an append-only decision log | → alerts |

**Linking rules (suggestion #12):** the brief's transaction fields are amount, timestamp, sender, beneficiary, channel and status, with no device, IP or customer. So:
- `customer_id` comes from the sender account (`account.customer_id`).
- A transaction is linked to a device or IP by the customer's most recent successful login within a time window (default 30 min) before it. The link is marked `derived` in the evidence.
- Mandatory fields stay minimal: IDs, timestamps, amounts. Name, DOB and other PII are optional, since anonymised data may leave them out.

### 3.2 Ingestion that survives hidden tests

1. **Format sniffing:** `.csv` (encoding and delimiter detection), `.xlsx` (every sheet = a candidate entity), `.json` (array or `{records: [...]}`, nested objects flattened). **Read everything as text** (`dtype=str`) and convert types explicitly per field, so IDs like `00123` keep their leading zeros.
2. **Entity detection and header mapping:** column names are normalised (lowercase, strip spaces/underscores) and matched against an alias dictionary (`cust_id`, `customerId`, `customer id` → `customer_id`). Fuzzy matching (`rapidfuzz`) is a fallback that is **auto-applied only at high confidence (≥ 90)**. Below that, the column is left unmapped and flagged, so look-alike columns such as `sender_account` and `beneficiary_account` can never be swapped. The UI shows the proposed mapping, and `/api/ingest` accepts a `mapping` override (JSON `{source_column: canonical_field}`) so a correction can also be applied through the API.
3. **Validation** with Pydantic models per entity: required fields (kept minimal), types, date parsing, amount > 0, enum values, links to unknown records (e.g. a transaction for an unknown account → warning, still loaded).
4. **Duplicates (suggestion #15):** a repeated ID **within one file** is rejected with a reason. Across files or re-uploads: an identical row is skipped silently and counted; a row with the same ID but different data is kept as it was, and a **conflict warning** is shown.
5. **Missing IDs:** log rows without an `event_id` get a stable hash ID (customer + timestamp + device + outcome), so re-uploads stay idempotent.
6. **Quarantine, not silence:** invalid rows go to `rejected_rows` with row number + field + reason, shown in a **Data quality report** (accepted / rejected / skipped / conflicts / warnings per file, downloadable).
7. **Any subset works (suggestion #13):** the brief's sample data lists only three sources (customers/accounts, transactions, login logs). Loan and claim files may not be provided. Detection runs on whatever was loaded. Each run reports which indicators ran and which were **skipped because their data is missing** (e.g. "AP-01 skipped: no applications loaded").
8. **Two buttons:** "Load demo dataset" (our generator) and "Upload files", so a judge can always see the app working.

### 3.3 Detection: the indicator library

Each indicator is a small function plus a config entry with `id`, `name`, `category`, `weight`, `params` and `enabled`. It returns `Signal{indicator_id, entity, score 0–1, reason text, evidence_ids[], direction: risk|mitigating}`. That covers "configurable rules".

**Where rule config lives (review 2 #18):** `rules.yaml` holds the **defaults only**. Edits made in the UI are saved in the database (`rule_override` table) and applied on top of the defaults, so a restart or redeploy does not lose them. "Reset to defaults" deletes the overrides.

**Point-in-time rule (suggestion #3):** in batch mode, every feature for an event is computed **only from events strictly before it**. The baseline uses earlier, *successful*, *outbound* transactions only. Otherwise a fraudulent transfer inflates its own baseline, and "new beneficiary" would be judged against payments that happen later.

**Short history (review 2 #3):** with point-in-time features, a customer's first beneficiary and first device always look "new", which floods a short dataset with false positives. So TX-03 (new beneficiary) and DV-03 (new device) are **skipped when the customer has fewer than 5 prior events** of that kind, and the **onboarding device** (the first device seen for the customer) is never treated as new.

**Baseline safety (suggestion #4):** the robust z-score denominator is `max(1.4826·MAD, 0.1·median, floor_amount)`. Fixed payments such as rent or EMI have MAD = 0, so this avoids division by zero. Fallback order when the customer's own history is short: customer (≥ 5 prior txns) → peer segment → global baseline.

**High value is separate from unusual (suggestion #1):** `HV-01 high_value` fires on absolute size, either amount ≥ the high-value threshold or ≥ 50 % of the account balance. It is not a risk signal by itself. It exists so the ATO chain can fire even for a customer who *regularly* makes large transfers, where TX-01/02 stay silent. **The threshold defaults to the p90 of all outbound amounts in the loaded data (review 2 #7)**, so it works for any currency or scale. A fixed value can still be set in config.

| ID | Indicator (scenario) | Logic | Level |
| --- | --- | --- | --- |
| TX-01 | Amount far above the customer's own norm | robust z over **prior** successful outbound txns, floored denominator; fallback customer → segment → global | P0 |
| TX-02 | Amount above the customer's p95 / historical max | amt > prior p95 and > 2× prior median | P0 |
| TX-03 | New beneficiary | beneficiary never paid by this customer **before this transaction**; skipped when < 5 prior transfers | P0 |
| HV-01 | High-value flag (chain input only) | amt ≥ p90 of loaded outbound amounts (or a configured value) or ≥ 50 % of balance; weight 0 on its own | P0 |
| TX-04 | Rapid transfers / velocity | ≥ N transfers or ≥ X total within T minutes (1 h, 24 h windows) | P0 |
| TX-05 | Fan-out to many new beneficiaries | ≥ k distinct new beneficiaries in 24 h | P0 |
| TX-06 | Unusual hour | txn hour outside the customer's usual hour band | P1 |
| TX-07 | Balance drain | transfer ≥ 80 % of the balance | P1 |
| TX-08 | Structuring | several transfers just under a reporting limit within 7 days | P1 |
| DV-01 | Device shared by many customers | distinct customers per device ≥ k | P0 |
| DV-02 | Shared-device relationship assessment | shared surname/address/household → **mitigating**; unrelated identities, different cities, applications or transfers from the shared device → risk. **No name or address in the data → neutral result, shown as "relationship assessment unavailable"** (review 2 #8) | P0 |
| DV-03 | New device for this customer | device not seen in the customer's history; the onboarding device is never new; skipped when < 5 prior logins | P0 |
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

**Mitigation is suspended during account takeover (suggestion #5):** ATO victims are often long-tenure customers with clean histories and regular payees. When a **login signal (LG-01..03)** is active for the customer within the chain window, the *tenure*, *regular-payee* and *recurring-pattern* mitigations are switched off. **A new device (DV-03) alone does not suspend them (review 2 #9)**, so a regular payer who just changed phones is not penalised. The explanation says so ("Mitigation suspended: suspicious login 14 min earlier").

**The "hundreds of parameters" story (suggestion #19):** each indicator can run over several time windows (1 h / 24 h / 7 d / 30 d) and dimensions (customer, account, device, IP, beneficiary). The pitch quotes **only the number of features we actually compute**, counted from code by the feature catalogue screen (P1). We don't say "150+" unless the catalogue shows it.

### 3.4 Risk scoring and explanations

**Scoring units (review 2 #1).** Scoring "every event" would give five alerts for one failed-login burst, and an ATO chain would never land in one score, because the logins and the transfer are separate events. So exactly four things get scored, each producing at most one alert:

| Unit | What it is | Signals it collects |
| --- | --- | --- |
| **Transaction** | one outbound transfer | TX-*, HV-01, plus **context**: LG and DV signals for the same customer in the chain window *before* it |
| **Login burst** | a run of failed logins (and the success that ends it), grouped per customer | LG-01..03, DV-03; only alerted on its own when **no transaction follows** in the window (otherwise it is context on that transaction) |
| **Device cluster** | one device and all customers seen on it | DV-01, DV-02; one alert per device, not per login |
| **Application** | one loan application (or one claim, P1) | AP-*, CL-*, plus the device cluster it belongs to |

1. **Combine risk signals** with a noisy-OR, so many weak signals add up while no single one saturates the score:
   `risk = 1 − Π(1 − wᵢ·sᵢ)` over risk signals, where `wᵢ` is the indicator weight and `sᵢ` its strength (0–1). Each `wᵢsᵢ` is clamped to at most 0.99 so the log in step 5 never hits ln(0).
2. **Mitigating signals** damp the score: `damped = risk × Π(1 − mⱼ)` (subject to the ATO suspension in 3.3).
3. **Attack-chain floors instead of multipliers (suggestion #2):** a multiplier can leave a full chain at Medium (0.4 × 1.5 = 0.6) or push the score past 100. When a known chain is confirmed, the score becomes `max(damped, floor)`, and **mitigation can never take it below the floor**:
   - ATO chain: failed logins → success (`LG-02`) → new device (`DV-03`) → high-value transfer (`HV-01`), **in that order** (review 2 #6), within 24 h → floor **85**
   - ATO chain with money or payee movement: `LG-02` → `LG-03` beneficiary change, or a transfer, within 24 h → floor **70**
   - ATO chain, partial (no money moved): `LG-02` → (`DV-03` or a password reset) → floor **55** (Medium). **High requires a beneficiary change or a transfer (review 2 #4)**, so a real user who forgot their password and logged in from a new phone is not High.
   - Loan mule chain: `AP-01` → `AP-03`, in that order → floor **80**
   A chain is the only "hard rule". There are no other overrides. A transfer that happens *before* the suspicious login never completes a chain.
4. **Scale to 0–100 and band it:** Low < 40, Medium 40–69, High ≥ 70 (configurable).
5. **Additive explanation (suggestion #6, corrected by review 2 #2):** noisy-OR is not additive, so each risk signal's share is `cᵢ = −ln(1 − wᵢsᵢ)`. On the 0–100 scale:
   - each **risk line** = `undamped × cᵢ / Σc` (these lines sum to the undamped score);
   - the **mitigation line** = `damped − undamped` (negative; split across mitigating signals by the same log-share method);
   - the **floor line** = `final − damped` (only when a chain floor lifted the score).
   Risk lines + mitigation + floor = final, exactly. Rounding is done last, and any rounding remainder goes to the largest line so the displayed integers also sum to the score. This is shown as a **waterfall bar** in the UI, and every line links to its evidence records.
6. **Entity rollup:** customer risk = max event risk plus a graph uplift from linked risky entities (P1).

The brief's two calibration cases become **unit tests** (suggestion #8):
- A high-value transfer from a customer who regularly makes similar transfers → **Low** (< 40). Medium would open a case, which is itself a false positive.
- The same transfer after failed logins and a new-device login → **High** (≥ 70, through the ATO floor).
- Forgot password: failed logins → reset → login from a new phone, **no money moved** → **Medium or lower** (review 2 #4).
- A transfer made *before* the failed logins → no chain (review 2 #6).
- Plus one test per scenario on a small hand-made **golden dataset** (see Workstream B).

### 3.5 Alerts and cases

- **Every scoring unit with at least one risk signal is classified (suggestion #7; units defined in 3.4).** The brief says every detected activity gets a risk classification, so Low results are stored as alerts too and appear in the risk distribution. The alert list **defaults to Medium + High**, with a toggle to show Low, so the queue stays usable.
- **Alert** holds: `alert_id`, `detection_run_id`, `dedupe_key`, `event_time` (when the activity happened), `created_at`, event ref, linked entities (via `alert_entities`), category, nullable `product`, detection types, score, band, contributions[], **evidence snapshot (JSON copy of the records)**, rules version.
- **Immutability is enforced by the database (suggestion #9, review 2 #5 and #19),** not just the API: `BEFORE UPDATE` **and** `BEFORE DELETE` triggers on `alert` raise an error. The trigger SQL is chosen by `engine.dialect.name`: plain triggers on SQLite, a trigger function + triggers on Postgres.
- **Demo reset is a separate path (review 2 #5):** `POST /api/admin/reset` drops and recreates the tables (no row deletes), so the triggers never need to be bypassed.
- **No duplicates on re-run (suggestion #9):** `dedupe_key = hash(scoring unit type + primary entity + event ids)`. Re-running detection with the same rules version skips existing keys.
- **Rule changes do not double-count (review 2 #5):** if the rules changed, a new alert is written under the new `detection_run_id` and the old one stays as history, but:
  - the **dashboard and alert list read the latest run only** (older runs are visible in the alert's history);
  - a new alert whose `dedupe_key` already has a case **attaches to that existing case** instead of opening a new one, and the case log records "re-scored: 62 → 78 under rules v3".
- **Date filters use `event_time`, not `created_at` (suggestion #10),** so "last 7 days" means when the activity happened, not when we ran detection.
- **Case** is auto-created for **Medium and High alerts only**, per alert or grouped per customer within 72 h (P1). It holds: `case_id`, alert_ids, category, customer/account, risk, status, assignee, notes.
- **Statuses can change in any direction (suggestion #11):** `New`, `Requires Investigation`, `False Positive`, `Escalated`, `Confirmed Fraud`, `Closed`. Any status can move to any other, including reversals such as False Positive → Requires Investigation. A note is required for a reversal. Level 1 requires at least Requires Investigation and False Positive.
- **Decision log:** an append-only `case_event` row (who, when, from → to, note) for every change. The case page shows the original alert snapshot beside the current decision and the full history, which visibly meets "preserve the original alert even when its classification changes".

### 3.6 AI case intelligence (deterministic first, LLM on top)

- **Always available, no LLM:** a template narrative built from the contributions ("Flagged because 3 failed logins at 02:10 were followed by a login from a new device in Lagos and a transfer of ₹4.8 L to a new beneficiary 12 minutes later").
- **With Groq (P1):** the evidence JSON goes to the model with a strict prompt. It returns `{summary, likely_typology, key_evidence:[{claim, record_ids}], recommended_actions, report_draft}`.
- **Grounding guard:** the backend checks that every `record_id` the model cites exists in the evidence. Any claim without a valid ID is dropped. The UI labels the section **"AI-generated · citations checked"**, not "verified" (suggestion #19), because the guard confirms the IDs exist, not that the claim is true. This addresses "unsupported AI claims" without overclaiming.
- **PII masking** before the call: names and phone numbers are replaced with tokens.

### 3.7 API contract (agree on this in the first 10 minutes)

| Method | Path | Owner | Returns |
| --- | --- | --- | --- |
| POST | `/api/ingest` (multipart; optional `entity_type`, optional `mapping` JSON override) | A | batch report: accepted, rejected, skipped, conflicts, errors[], applied mapping, unmapped columns |
| POST | `/api/demo/load` | A | loads the generated dataset |
| GET | `/api/records/{entity}?filters` | A | paginated records |
| GET | `/api/customers/{id}/360` | A | profile, accounts, txns, logins, devices, apps, claims, linked entities |
| POST | `/api/detect/run` | B | runs all indicators, writes alerts (deduped); returns `detection_run_id`, counts, indicators run and **indicators skipped (missing data)** |
| GET | `/api/rules` / PUT `/api/rules/{id}` | B | indicator config (weights, thresholds, enabled) |
| POST | `/api/rules/simulate` | B | alert counts before/after a config change (P1) |
| GET | `/api/graph/{entity_id}?depth=2` | B | nodes, edges for the link graph |
| GET | `/api/dashboard/summary?filters` | C (file `backend/app/api/dashboard.py`) | latest run only: processed counts, flagged, by band, by category, by detection type, over time (by `event_time`), skipped indicators |
| POST | `/api/admin/reset` | A | drops and recreates tables, optionally reloads demo data |
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
| P0 | Indicators TX-01..05, HV-01, DV-01..03, LG-01..03, AP-01..02, MT-* | The four required scenarios + one extra; HV-01 feeds the ATO chain (review 2 #12) |
| P0 | Noisy-OR score, bands, mitigation, contribution list | Required risk assessment |
| P0 | Dashboard KPIs + 6 filters + alert detail with evidence | Required |
| P0 | Case queue, decision (Requires Investigation / False Positive), decision log, immutable alert | Required |
| **P1 — differentiators (after Level 1, or early if ahead)** | Contribution waterfall chart, risk-raising vs mitigating factors | Wins the lookalike story visually |
| P1 | Identity link graph + ring detection (GR-01), shared-device household check | Coordinated fraud; likely Level 2+ |
| P1 | Customer 360 timeline across banking, lending and insurance | Cross-system scenario |
| P1 | Duplicate claims (CL-01), loan disbursement → outbound (AP-03), structuring, impossible travel | More scenarios = more hidden tests passed |
| P1 | Grounded Groq case summary + report draft | AI that is checked, not decorative |
| P1 | Rules editor + what-if simulation | Configurability you can see |
| P1 | Detection scorecard: precision/recall per scenario, always labelled **"on our synthetic data"** | Evidence our engine works, without overclaiming |
| **P2 — future / pitch only** | Streaming (Kafka) real-time scoring, feedback-trained model (LightGBM + SHAP), graph neural nets, consortium device intelligence, behavioural biometrics, SAR filing integration, case SLA and assignment, RBAC | Roadmap slide |

**Cut list (suggestion #18):** if P0 is behind at **12:45**, cut in this order until it fits: (1) rapidfuzz fuzzy matching (keep the alias dictionary), (2) the mapping-correction UI (keep the API `mapping` override), (3) TX-05 fan-out, (4) AP-02 application velocity. The extra scenario still stands on AP-01.

---

## 5. Three workstreams

All three are equal in effort: each owns one layer end to end, plus one stretch differentiator. The contract in 3.7 lets everyone build against stub data from minute 15.

### Workstream A — Data platform, cases and API (owner: Harsh)

**Mission:** every byte enters cleanly, links correctly and is served to the UI. Owns persistence of alerts and cases.

- **Modules:** `backend/app/ingest/` (parsers, header mapper, validators, quarantine), `backend/app/models.py` (SQLAlchemy), `backend/app/api/` (records, alerts, cases, admin reset — **not** `dashboard.py`, which is C's; review 2 #10), `backend/app/datagen/` (synthetic data generator), `backend/app/db.py` (engine from `DATABASE_URL`, triggers per dialect).
- **Deployment-ready from the start (review 2 #19, #20):** immutability triggers for SQLite and Postgres; `psycopg` in the backend dependencies; inserts in batches (`executemany` / bulk insert), never row by row; demo data loaded on startup when the database is empty.
- **Features:**
  1. Canonical schema for the 7 entities + ingestion_batch + alert + alert_entities + case + case_event; the `BEFORE UPDATE` trigger on `alert`.
  2. CSV / XLSX / JSON ingestion read as text, alias + high-confidence fuzzy mapping, `mapping` override, duplicate and conflict handling, hash IDs for logs, data quality report; works on any subset of files. Derive transaction customer and device links (3.1).
  3. Synthetic data generator (Faker, seeded): ~200 customers, ~5k transactions, ~3k login events, ~150 loan applications, ~100 claims. Planted with **labelled** patterns: ATO chains, mule ring via shared device + loan applications, rapid fan-out, household device sharing (legit), regular high-value payers (legit lookalikes), duplicate claims. Also exported as CSV, XLSX and JSON files with deliberately dirty rows, to demo the validation.
  4. Alert store (insert-only, deduped by key) and case API with reversible statuses and the decision log.
  5. Customer 360 endpoint (P1).
  - *Rebalanced (suggestion #17):* the dashboard summary endpoint moved to C, and B builds its own golden dataset, so B no longer waits on A's generator.
- **Tools:** FastAPI, SQLAlchemy + SQLite (local) / Postgres via psycopg (deployed), pandas, openpyxl, Pydantic v2, rapidfuzz, Faker.
- **Inputs:** uploaded files; `Alert` objects from B. **Outputs:** clean tables, REST endpoints, labelled demo dataset.
- **Depends on:** B for the `Alert` shape (fixed in 3.7). **Blocks:** C needs endpoints (stub JSON by 11:50); B needs the generator only for the end-to-end run, not for calibration.
- **Milestones:** 11:50 schema + stub endpoints · 12:15 generator v1 pushed · 12:45 ingestion with validation report · 13:15 alerts/cases/decision API.

### Workstream B — Detection and risk intelligence engine (owner: mansh7763)

**Mission:** turn records into correct, explainable risk. Owns everything the hidden tests will most likely score.

- **Modules:** `backend/app/features/` (customer baselines, velocity windows, device/IP stats), `backend/app/detect/` (indicator library + `rules.yaml`), `backend/app/graph/` (NetworkX identity graph), `backend/app/score/` (noisy-OR, mitigation, chain floors, contributions), `backend/tests/`.
- **Features:**
  1. **Golden dataset first (suggestion #17):** 5–6 hand-made customers in `backend/tests/golden/` covering: a regular high-value payer (expect Low), the same customer under ATO (expect High), a household sharing a device (expect Low), unrelated customers sharing a device with loan applications (expect High), a failed-login burst with no follow-up (expect Low/Medium), and a rapid transfer burst to new beneficiaries (expect High). Calibration runs on this from 12:00, independent of A's generator.
  2. Point-in-time behavioural profile per customer (prior events only): median, MAD with a floored denominator, p95, max, usual beneficiaries, devices, hours and cities; fallback customer → segment → global.
  3. P0 indicators TX-01..05, HV-01, DV-01..03, LG-01..03, AP-01..02, MT-*; each returns a `Signal` with evidence IDs. Each indicator declares the data it needs and is reported as skipped when that data is missing.
  4. Shared-device relationship check (household vs unrelated); mitigation suspended during ATO.
  5. Risk scoring: noisy-OR, mitigation, chain floors, bands, additive contributions that sum to the score; dedupe keys; alert generation.
  6. Unit tests: the brief's calibration cases plus every golden-dataset expectation (pytest).
  7. P1: identity graph + ring detection, Isolation Forest signal, CL-01, AP-03, rules simulation endpoint, precision/recall scorecard against the generator's labels (labelled "on synthetic data").
- **Tools:** pandas, numpy, scikit-learn (IsolationForest), NetworkX, rapidfuzz (claim description similarity), PyYAML, pytest.
- **Inputs:** canonical tables from A. **Outputs:** `Alert` objects to A's store; `/api/detect/run`, `/api/rules`, `/api/graph`.
- **Depends on:** A only for the end-to-end run; calibration uses the golden dataset. **Blocks:** C's alert screens need real alerts by ~13:00.
- **Milestones:** 11:50 `Signal` / `Alert` types + rules.yaml skeleton · 12:00 golden dataset · 12:30 transfers + login indicators · 13:00 devices + loan apps + mitigation + scoring · 13:20 golden tests green · P1 afterwards: graph, anomaly, claims, scorecard.

### Workstream C — Investigation experience and AI case intelligence (owner: Bhuvan)

**Mission:** make the system usable and the intelligence visible. Owns the demo and the AI layer.

- **Modules:** `frontend/` (React + Vite + Tailwind), `backend/app/ai/` (Groq client, prompts, grounding guard, PII masking, template narrative), `backend/app/api/dashboard.py` (dashboard summary endpoint, explicitly C's; review 2 #10).
- **Deployment-ready from the start (review 2 #21):** the API base URL comes from `VITE_API_URL`; `frontend/vercel.json` has an SPA rewrite to `index.html`, so refreshing a page does not return 404.
- **Features:**
  1. **Data screen:** upload (drag and drop, multiple files), mapping preview, data quality report, "Load demo data" button.
  2. **Dashboard** (screen *and* the `/api/dashboard/summary` endpoint, moved from A): KPI tiles (records processed, flagged, high-risk, open cases), risk-band distribution including Low, category and detection-type breakdowns, alerts over time by `event_time`; the 6 filters; a "detection coverage" note listing indicators skipped for missing data.
  3. **Alert detail:** event, contribution list (waterfall in P1), supporting records table, plain-language explanation.
  4. **Case queue:** list with filters and status chips; alert list defaults to Medium + High with a "show Low" toggle; case page with the original alert snapshot, evidence, decision buttons (any status, a note required for reversals), notes, decision timeline.
  5. Template narrative (no LLM) for Level 1. P1: Groq grounded summary + report draft labelled "AI-generated · citations checked".
  6. P1: link graph view (react-force-graph) with ring highlighting; customer 360 timeline; rules editor with simulation.
- **Tools:** React, Vite, TypeScript, Tailwind, Recharts, react-force-graph-2d, axios; Groq SDK (JSON mode).
- **Inputs:** REST endpoints from A and B. **Outputs:** the full UI, `/api/cases/{id}/ai-summary`, the demo flow and the deck screenshots.
- **Depends on:** A's stubs (11:50) and B's alert shape. Builds on mock JSON until real endpoints are ready. **Blocks:** nobody, which is why C also owns the demo script and the submission.
- **Milestones:** 11:50 app shell + routing + types · 12:30 upload + dashboard on stubs · 13:00 alert detail + case queue on stubs · 13:30 switched to real API · 13:45 end-to-end demo → **submit Level 1** · P1 afterwards: graph, waterfall, Groq summary.

### Balance check

| | A | B | C |
| --- | --- | --- | --- |
| P0 effort | Ingestion + generator + records/alerts/cases APIs | Golden dataset + ~16 indicators + scoring + tests | 4 screens + dashboard API + template narrative |
| P1 differentiator | Customer 360, labelled dataset, dirty-file demo | Graph rings, anomaly model, scorecard | Waterfall, graph view, grounded AI |
| Hardest part | Header mapping on unknown schemas | Calibration (lookalikes vs ATO) | Making evidence readable at a glance |

### Integration rules

- Folders are owned: A = `backend/app/{ingest,models,api,datagen,db}` (except `api/dashboard.py`), B = `backend/app/{features,detect,graph,score}` + `backend/tests` + `evals/`, C = `frontend/` + `backend/app/ai` + `backend/app/api/dashboard.py`. `schemas.py` and `main.py` change only with a heads-up in chat. The source of truth is `.github/workstreams.json`; see `Docs/OWNERSHIP.md` for the overlap warnings.
- Merge to `main` at least every 45 minutes. The 13:15 and 13:35 slots are for integration only.
- A single command runs everything (`run.ps1` / `run.sh`: backend on :8000, frontend on :5173).
- **Backend dependencies (review 2 #14)** go in `backend/requirements.txt` with Python 3.12 pinned (the root `requirements.txt` stays as the PDF-reading tools).
- **All config from the environment (review 2 #17):** `DATABASE_URL`, `GROQ_API_KEY`, `CORS_ORIGINS` (backend) and `VITE_API_URL` (frontend). Their names go in `.env.example` with no real values. Uvicorn listens on `$PORT` (default 8000).

---

## 6. Level 1 timeline (today)

| Time | A | B | C |
| --- | --- | --- | --- |
| 11:30–11:50 | Repo scaffold (FastAPI), `schemas.py` together with B, stub endpoints | `Signal`/`Alert` types, rules.yaml skeleton | Vite + Tailwind shell, routes, `types.ts`, mock JSON |
| 11:50–12:45 | Generator v1 (12:15), ingestion + validation | Golden dataset (12:00), profiles, TX and LG indicators | Upload screen, dashboard on mocks |
| 12:45–13:15 | Alerts/cases/decision API | DV, AP, MT indicators, scoring, alert generation | Alert detail, case queue on mocks |
| 13:15–13:35 | **Integrate:** load demo → run detection → dashboard → case decision | Calibration tests; fix false positives | Switch to the real API |
| 13:35–13:50 | Test with the organiser's sample files (if given); fix mapping | Same | Run the demo path twice; **submit Level 1** |
| After L1 | Customer 360, dirty-file demo; **deploy backend to Render + Aiven** (review 2 #22) | Graph rings, anomaly, CL-01, scorecard | Waterfall, graph view, Groq summary; **deploy frontend to Vercel** |

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
| Aiven, Render or the venue network goes down (review 2 #23) | Run locally on SQLite with the demo data; the demo never depends on the deployed copy |

---

## 8. Deployment (after Level 1; review 2 #24)

**Hard deadline: code, prototype and deck locked on HackCulture by 6:00 PM (review 2 #15).** A hosted URL is optional, so deployment never blocks a submission.

| Part | Service | Settings |
| --- | --- | --- |
| Frontend | **Vercel** | Root `frontend/`; env `VITE_API_URL` = the Render URL; `vercel.json` SPA rewrite |
| Backend | **Render** (web service) | Root `backend/`; start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`; env `DATABASE_URL`, `GROQ_API_KEY`, `CORS_ORIGINS` = the Vercel URL |
| Database | **Aiven Postgres** | Connection string with `sslmode=require` in Render's `DATABASE_URL` |

- **Not Vercel for the backend:** its serverless functions do not suit a local database file, file uploads, or a long detection run.
- Demo data loads on startup when the database is empty, so a fresh deploy is never blank.
- **Before deploying, check the current free-tier limits** of Vercel, Render and Aiven, especially Render's memory, since pandas and scikit-learn are memory-heavy. These have not been verified.

## Sources

- Featurespace ARIC — [Finovate](https://finovate.com/?p=51769), [NVIDIA blog](https://blogs.nvidia.com/blog/2022/08/25/featurespace-blocks-financial-fraud)
- Quantexa — [Fraud solutions](https://www.quantexa.com/solutions/fraud), [Risk.net award](https://www.risk.net/ja/node/7875606)
- Feedzai — [RiskOps](https://feedzai.com/riskops), [AWS Marketplace listing](https://aws.amazon.com/marketplace/pp/prodview-lis6xav4rqwgm)
- NICE Actimize — [IFM-X announcement](https://www.niceactimize.com/press-releases/nice-actimize-announces-next-gen-fraud-management-platform-leveraging-advanced-ai-and-the-cloud-to-fight-fraud-and-enhance-customer-experience-338)
- BioCatch — [Connect solution brief](https://www.biocatch.com/hubfs/BioCatch_Connect_SolutionBrief_2023.pdf?hsLang=en)
- LexisNexis ThreatMetrix — [Product page](https://risk.lexisnexis.co.uk/products/threatmetrix)

These are mostly vendor materials; their performance claims are unverified and only used for design inspiration.
