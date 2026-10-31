# Suggestions for the Stage 01 Plan

Date: 2026-10-31 · Reviews: `Docs/STAGE1_PLAN.md` against `Docs/ProblemStatement-Stage-1.pdf`

**Bottom line:** The direction is right. Keep the per-customer baselines, mitigating factors, immutable alerts and an app that works without the LLM. Fix the items below before coding, because several change the schema and the scoring contract. Do 1–3, 7, 9 and 12 first.

## Scoring and detection

| # | Plan ref | Problem | Fix |
| --- | --- | --- | --- |
| 1 | 3.4 step 2, calibration cases | The ATO chain needs TX-01/02, but a regular high-value customer's transfer is within their norm, so neither fires. "Same transfer + failed logins + new device" does not reach High | Use a separate `high_value` flag in the chain, based on balance or absolute amount |
| 2 | 3.4 step 2 | The ×1.5 multiplier is unreliable: 0.4 × 1.5 = 0.6 leaves a full ATO chain at Medium, and a base above 0.67 goes past 100 | Replace it with a score floor (e.g. minimum 80) when a chain is confirmed; mitigation cannot go below that floor |
| 3 | 3.3 TX-01, TX-03 | In batch mode, using full history leaks the future: a fraud transaction inflates its own baseline, and "new beneficiary" is judged wrongly | Compare each event only with earlier, successful, outbound transactions |
| 4 | 3.3 TX-01 | MAD = 0 for fixed payments such as rent or EMI, which causes division by zero | Put a minimum floor on the denominator; add a global fallback when no peer segment exists |
| 5 | 3.3 MT-* | Tenure mitigation lowers the score of ATO victims, who are often long-tenure, clean-history customers | Turn off tenure and regular-payee mitigation while login signals are active |
| 6 | 3.4 steps 1, 5 | Noisy-OR is not additive, so "+32, +18, −20" is undefined | Split the final score in proportion to `-ln(1 - wᵢsᵢ)` so contributions sum to it |

## Alerts and cases

| # | Plan ref | Problem | Fix |
| --- | --- | --- | --- |
| 7 | 3.4 step 4, 3.5 | The brief wants every detected activity classified, but alerts start at 40, so Low never appears and the risk distribution is incomplete | Create Low alerts too; auto-create cases only for Medium and above. Define "hard rule" or remove it |
| 8 | 3.4 calibration cases | "Low or Medium" is too loose for a lookalike, because Medium opens a case, which is itself a false positive | Expect Low |
| 9 | 3.5, 3.7 `/api/detect/run` | Alerts are insert-only, so re-running detection duplicates them | Add `detection_run_id` and a stable dedupe key. Enforce immutability with a SQLite `BEFORE UPDATE` trigger |
| 10 | 3.1, 3.5 | Shared-device and ATO alerts span several customers or events, but the model assumes one | Add an `alert_entities` link table and a nullable `product`. Filter dates on event time, not `created_at` |
| 11 | 3.5 statuses | The flow is one-way, but the brief says classification can change later | Allow reversals such as False Positive → Requires Investigation, and log each change |

## Ingestion and hidden tests

| # | Plan ref | Problem | Fix |
| --- | --- | --- | --- |
| 12 | 3.1 `transaction` | The brief's transaction fields do not include `device_id`, `ip` or `customer_id` | Derive the customer from the sender account; link device and login data by customer + time window |
| 13 | Section 4 P0 | Loan and claim files may not be provided: the brief's sample data lists only three sources | Make the pipeline run on any subset and show which indicators were skipped. Keep mandatory fields minimal, since anonymised data may omit name or DOB |
| 14 | 3.2 step 2, 3.7 `/api/ingest` | The UI can correct a mapping, but no API accepts the correction | Add a mapping override parameter. Auto-apply fuzzy matches only at high confidence, so `sender_account` and `beneficiary_account` cannot get mixed up |
| 15 | 3.2 steps 3, 5 | "Duplicate IDs are invalid" conflicts with "upsert on ID" | Reject duplicates within a file. Across files, skip identical rows and raise a conflict warning when data differs |
| 16 | 3.1 | pandas turns `00123` into `123`, and some logs may have no `event_id` | Read files with `dtype=str`; generate a hash ID for logs without one |

## Team and scope

| # | Plan ref | Problem | Fix |
| --- | --- | --- | --- |
| 17 | Section 5 | Workstream A carries ingestion, the generator, cases and the dashboard API, and B's calibration waits on A's data | B makes a small hand-made golden dataset (5–6 customers) for calibration |
| 18 | Section 4 | P0 is large for the time available | If behind at 12:45, cut rapidfuzz, the mapping UI, TX-05 and AP-02, in that order |
| 19 | 3.3, 3.6, Section 4 | Some claims are stronger than the evidence, and the brief penalises unsupported AI claims | Do not say "150+ features" unless they are computed. Change "verified against N records" to "citations checked", because the guard only checks that IDs exist. Label precision/recall "on synthetic data" |
