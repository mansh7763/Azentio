"""Build the offline Stage 1 presentation from frozen evaluation reports and rule config."""
from pathlib import Path
import html
import json
import hashlib
import yaml

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "evals/reports"
cfg = yaml.safe_load((ROOT / "backend/app/detect/rules.yaml").read_text(encoding="utf-8"))
d2_report = json.loads((REPORT / "priority_freeze_d2.json").read_text())
d2 = d2_report["after_corrected_fixture"]
d3_report = json.loads((REPORT / "d3_heldout.json").read_text())
d3 = d3_report["metrics"]
golden = json.loads((REPORT / "golden_scorecard.json").read_text())
esc = html.escape

def table(headers, rows):
    return '<div class="table-wrap"><table><thead><tr>' + ''.join(f'<th>{esc(str(x))}</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{esc(str(x))}</td>' for x in r) + '</tr>' for r in rows) + '</tbody></table></div>'

def pct(v): return f'{100*v:.1f}%'

slides = []
def slide(title, body, note='', appendix=False):
    n = len(slides) + 1
    slides.append(f'<section id="s{n}" class="slide {"appendix" if appendix else ""}"><div class="eyebrow">FINSHIELD / {"REFERENCE" if appendix else "STAGE 1"} / {n:02}</div><h1>{title}</h1>{body}' + (f'<aside class="notes"><strong>Speaker note</strong><p>{note}</p></aside>' if note else '') + '</section>')

slide('Fraud signals.<br><em>Evidence investigators can use.</em>', '''
<p class="lead">FinShield brings banking and lending records into one explained investigation workflow.</p>
<div class="flow"><span>Upload</span><b>→</b><span>Validate &amp; link</span><b>→</b><span>Detect &amp; explain</span><b>→</b><span>Review &amp; record</span></div>
<p class="statement">Every scored signal has a name, a reason and supporting record IDs.</p>
<p class="muted">Stage 1 • Deterministic rules + customer statistics • Local FastAPI / pandas / SQLite / React</p>
<p class="tag">Investigation priority, not a fraud probability. No automatic payment blocking.</p>''',
'Opening, 20 seconds: “Our focus is the analyst’s decision: why is this activity unusual, what evidence supports it, and what legitimate explanation should we consider?” The engine demonstrated here does not use ML. AI-assisted narrative and ML are roadmap items, not detection claims.')

slide('One complete investigation journey', '''
<div class="cols"><div><h2>Bring the evidence together</h2><ol><li>Upload CSV, XLSX or JSON.</li><li>Validate rows; expose rejected or missing data.</li><li>Resolve account → customer and application → payout links.</li><li>Run rules and point-in-time customer baselines.</li></ol></div><div><h2>Give the analyst control</h2><ol start="5"><li>Filter alerts by customer, transaction, product, risk, date and detection type.</li><li>Open reasons, source records and timeline.</li><li>Record Requires Investigation or False Positive.</li><li>Preserve decisions in an append-only audit trail.</li></ol></div></div>
<p class="statement">The mandatory additional scenario is suspicious loan applications, linked to customer, device and banking evidence.</p>''',
'25 seconds: demonstrate the journey instead of reading the list. A customer’s phone/address is a current profile snapshot; versioned contact changes, KYC and external fraud intelligence are not available. A device inferred from a nearby login is contextual evidence, not proof of the initiating device.')

slide('We derive patterns from mechanisms', '''
<p class="lead">Start with the fraud objective, then ask what evidence it must leave in the data we actually have.</p>
<div class="flow"><span>Documented case<br>or team hypothesis</span><b>→</b><span>Fraud mechanism</span><b>→</b><span>Observable sequence</span><b>→</b><span>Benign twin</span><b>→</b><span>Measured rule</span></div>
''' + table(['Reusable mechanism','Question','Current examples'], [
['Access compromise','Did suspicious access precede money movement?','Login bursts + new-device success + takeover chain'],
['Identity / resource reuse','Do separate applicants share relevant resources?','Shared device, contact or payout'],
['Behaviour change','Is activity unusual relative to earlier behaviour?','Amount deviation, dormancy, structuring'],
['Coordination / money flow','Do accounts converge, disperse or cycle funds?','Recipient convergence, pass-through, circular flow']]) + '''
<p class="tag">A scam name is not a detector. We implement only the observable part of its mechanism.</p>''',
'35 seconds: RBI fraud-awareness materials and financial-intelligence typologies can supply hypotheses. We do not claim every implemented rule was sourced from a regulator. Existing rules without a recorded source are team-designed hypotheses. Thresholds and weights are engineering choices, tested on development data; they are not regulator-prescribed values.')

slide('Every fraud story needs an innocent twin', table(['Design step','Account takeover','Legitimate recovery'], [
['Objective / context','Access another person’s account and move funds','Recover access after forgotten credentials'],
['Shared observable facts','Failures followed by a successful login','Failures followed by a successful login'],
['Separating evidence','New device plus subsequent unusual money movement','No suspicious money movement; familiar activity'],
['Decision','Ordered chain can establish a High floor','Failures alone must not imply High fraud risk']]) + '''
<h2>Generate variants systematically</h2><p>Change timing, amounts, number of participants, shared identifiers, customer tenure and legitimate purpose. Test just below/above thresholds, reordered events, missing data and evasions.</p>
<p class="statement">Keep a candidate only if it adds coverage without increasing development-set lookalike or background false alarms.</p>''',
'30 seconds: a candidate card should record source/hypothesis, required fields, exact sequence, parameters, evidence IDs, overlapping family, benign twin, boundaries and coverage gaps. Do not turn labels or scenario IDs into detector inputs. If fraud and benign behaviour are indistinguishable in the available data, state the gap.')

slide('Weights express evidence strength', '''
<div class="cols"><div><h2>Weight versus strength</h2><p><strong>Weight</strong> is the configured maximum contribution of an indicator. <strong>Strength</strong> scales that contribution for this event.</p><p>New payee: 0.25<br>Unusual amount: 0.45<br>Coordinated loan applicants: 0.55</p><p>These are heuristic priorities, not measured probabilities.</p></div><div><h2>How we justify them</h2><ol><li>Start lower for common, weak evidence.</li><li>Use stronger weights for more specific combinations.</li><li>Cap each risk weight below 0.70.</li><li>Test benign twins and threshold boundaries.</li><li>Use D2 ablation and sensitivity analysis; report D3 once.</li></ol></div></div>
<p class="tag">The evaluation tooling supports ablation and ±20% weight sensitivity. This freeze report does not claim a completed optimisation of every weight.</p>''',
'30 seconds: “We chose conservative, reviewable starting weights and evaluate their consequences. A higher score means higher review priority. It is not an estimated likelihood of fraud.” Weight ordering is a design rationale; it is not empirical proof of reliability. Noisy-OR does not make correlated signals statistically independent.')

slide('An explainable score, step by step', '''
<div class="formula">Risk = 100 × [1 − ∏(1 − weight × strength)]</div>
<p>First keep only the strongest signal in each overlapping family. Then damp with applicable mitigations, apply any ordered-chain floor, and enforce relevant caps.</p>
<div class="cols"><div><h2>Worked example</h2><p>TX-01 amount 0.45 + TX-03 new payee 0.25, both at full strength:</p><div class="math">100 × (1 − 0.55 × 0.75)<br><strong>58.75 → 59 / Medium</strong></div><p>A second amount rule does not stack on the same fact.</p></div><div><h2>Risk bands</h2><div class="bands"><span>Low<br>&lt;40</span><span>Medium<br>40–69</span><span>High<br>≥70</span></div><p>Regular-payee, recurrence, household and own-account evidence may reduce risk. Corroborated takeover access suspends selected mitigations.</p></div></div>''',
'35 seconds: a score is calculated for a transaction, login burst, device cluster or application. The example assumes no mitigation or chain. Supporting known-device/tenure mitigations need a stronger mitigating fact. The family approach reduces double-counting but does not prove complete independence.')

slide('Sequences can be stronger than single events', table(['Sequence','Floor','Timing / condition'], [
['Failures → new-device success → high-value transfer','85 / High','Success within 30 min after burst; transfer within 30 min after success'],
['Failures → new-device success → new-beneficiary movement','70 / High','Ordered access and payee evidence'],
['Suspicious access without the full movement chain','55 / Medium','Partial takeover path is capped below High'],
['Flagged application → disbursement → cash-out','80 / High','Explicit loan link; ≥70% to new recipients within 48h']]) + '''
<p class="statement">An explanation must identify the actual ordered records. The loan chain has its own 48-hour window.</p>
<p class="muted">Customer amount baseline: median / MAD; denominator max(1.4826 × MAD, 0.1 × median, 100). Fewer than 5 own payments uses segment/global fallback at reduced strength.</p>''',
'25 seconds: compare a High account-takeover example with password recovery. “Earlier evidence” is essential: future rows must not change an earlier assessment. Static profile data cannot establish a historical contact change, and sparse or missing feeds remain coverage limits.')

metric_rows = []
for label,key in [('Fraud recall at Medium+','recall_medium_plus'),('Fraud recall at High','recall_high'),('Lookalike false positives at Medium+','lookalike_fp_medium_plus'),('Lookalike false positives at High','lookalike_fp_high'),('Precision of Medium+ alerts','precision_medium_plus'),('Background Medium+ alerts','background_flags_medium_plus'),('Medium+ alerts per 1,000 events','alerts_medium_plus_per_1k_events')]:
    fmt = pct if key not in ('background_flags_medium_plus','alerts_medium_plus_per_1k_events') else str
    metric_rows.append([label,fmt(d2[key]),fmt(d3[key])])
slide('Measured on labelled synthetic scenarios', table(['Measure','D2 • development','D3 • held out'],metric_rows) + f'''
<p><strong>{golden['passed']}/{golden['total']} golden scenarios pass.</strong> Each synthetic split contains 56 fraud incidents and 48 legitimate lookalike incidents.</p>
<p class="tag">Synthetic results are not real-bank accuracy. Incident recall and alert precision use different denominators.</p>''',
'40 seconds: lead with D3 recall, then immediately disclose lookalike errors and precision. D2 is used for development. D3 seed 3 was run once after detector freeze and is not used to tune this build. The family fixture was corrected before that run. Its correction is not claimed as a detection improvement. Golden tests validate intended behaviour, not generalisation.')

slide('What remains difficult is visible', '''
<div class="cols"><div><h2>Known detection gaps</h2><ul><li>Slow drain: 0/4 incidents caught on D2; TX-06 remains noisy.</li><li>Payments spread across window boundaries.</li><li>Mules with no visible shared identifiers or transaction paths.</li><li>Legitimate first-time business fan-out.</li><li>Profile/payee changes, claims and insider abuse without their source data.</li></ul></div><div><h2>Priorities after the freeze</h2><ol><li>Rework TX-06 against new-payee spending history and disjoint baseline windows.</li><li>Resolve known-supplier / shopping lookalikes without hiding attacks.</li><li>Expand per-rule outcome and feed monitoring.</li><li>Add evidence-linked graph paths, with household and merchant-hub tests.</li><li>Evaluate a bounded anomaly challenger.</li></ol></div></div>
<p class="tag">Same surname + address is possible household context, not verified kinship. A shared device or IP alone does not establish a fraud ring.</p>''',
'25 seconds: the TX-06 redesign is a proposal, not shipped in this freeze. Current historical windows end before the scored window but can overlap one another. The household-landline issue was a synthetic fixture collision; the identity rule was not weakened. Existing relationship rules already cover some graph motifs; a general graph engine remains roadmap.')

slide('Next: let models learn from rule evidence', '''
<p class="lead">Use current rule signals and weighted contributions as model features. Keep the deterministic engine as the champion.</p>
<div class="flow"><span>Frozen alert-time<br>features</span><b>→</b><span>Shadow model</span><b>→</b><span>Time-based<br>evaluation</span><b>→</b><span>Measured promotion</span></div>
''' + table(['Step','Inputs / method','Gate'],[
['1. Feature snapshot','Rule fired, strength, weight × strength, family maxima, baseline z, velocity, novelty, history count, missingness','Only evidence available at the scored event; record rules/model version'],
['2. No labels yet','Isolation Forest on earlier windows; rule contributions may be inputs alongside raw behavioural features','Unusual ≠ fraud. Shadow first; optional ML-01 weight ≤0.25, never alerts alone'],
['3. Verified outcomes later','Logistic model or LightGBM learns combinations from confirmed outcomes','Investigation/pending is unlabelled. Rule score must never serve as the fraud label'],
['4. Validate and explain','Time/customer separation, calibration if probabilities are shown, feature contributions / SHAP','Improve recall at matched workload and lookalike error; new holdout after D3']]) + '''
<p class="statement">Current weights can seed features or serve as a benchmark. They cannot train a fraud model by themselves.</p>''',
'35 seconds: training a model to reproduce our scores would only imitate the rule engine. Isolation Forest does not automatically optimise noisy-OR weights. With genuine outcome labels, a supervised model can learn coefficients or nonlinear interactions. Keep mitigations and chain policy explicit; do not add a second correlated score without testing double-counting. Feature deviations are context, not necessarily a faithful explanation of an Isolation Forest score. Validate explanations and avoid claiming SHAP proves causation.')

slide('Show the decision, then show the evidence', '''
<ol class="demo"><li><strong>Upload and validate</strong><span>Show accepted/rejected counts and missing-feed coverage.</span></li><li><strong>Open a High takeover alert</strong><span>Follow failures → success → transfer; inspect source IDs and score contributions.</span></li><li><strong>Compare a legitimate lookalike</strong><span>Show regular payments or ordinary household sharing with lower risk.</span></li><li><strong>Open the additional lending scenario</strong><span>Explain device/contact coordination and the linked application.</span></li><li><strong>Record two analyst decisions</strong><span>Requires Investigation → False Positive; show both audit events.</span></li></ol>
<p class="statement">“FinShield makes fraud hypotheses testable, scores reviewable and analyst decisions auditable.”</p>
<p class="muted">Suggested five-minute path: sections 1–4 (1:50), 5–7 (1:30), 8–10 (1:40). Use this section as the live-demo checklist; reference sections follow.</p>''',
'For a live demo, replace some explanatory slides with the application rather than extending the allotted time. Rehearse with synthetic data and network disabled. Do not claim live external integrations, production fraud prevention, completed ML, or insurance detection.')

definitions = {
'TX-01':'Amount z ≥3 against earlier baseline; fallback at reduced strength.',
'TX-02':'Disabled: duplicates amount evidence.', 'TX-03':'First payment to beneficiary; requires established customer history.',
'TX-04':'At least 5 transfers within 20 minutes.', 'TX-05':'At least 4 new payees within 24 hours; history required.',
'HV-01':'Earlier same-currency p90, at least 20 samples; chain input, no direct points.',
'TX-06':'24h / 7d new-payee outflow excluding largest payment ≥1.5× historical-window p95; known noisy gap.',
'TX-07':'At least 3 unusual payments in 24h, each 75–100% of pre-window trigger; z ≥1.',
'TX-08':'Dormant ≥90 days after ≥180 observed days, then first-time payees within 7 days.',
'TX-09':'At least 70% of a successful credit to ≥3 first-time payees within 24h; same currency.',
'DV-01':'At least 3 customers sharing a device within 30 days.',
'DV-02':'Shared device with unrelated-customer evidence and linked applications/transactions.',
'DV-03':'New device for customer with at least 5 earlier logins.',
'LG-01':'At least 5 failures within 10 minutes.', 'LG-02':'Success within 30 minutes after failed-login burst.',
'LG-03':'Sensitive action after failed-login burst.', 'AP-01':'At least 3 applicants on one device within 72h, with shared contact/payout evidence.',
'AP-02':'At least 3 applications from customer or device within 7 days.',
'AP-03':'At least 70% of successful linked disbursement to new recipients within 48h; same currency.',
'AP-04':'At least 3 applicants name one payout within 7 days; household exclusion.',
'ID-01':'Application contact conflicts with profile and is already used by another applicant/customer.',
'ID-02':'Normalised profile contact shared under a different name; household and onboarding-time checks.',
'NW-01':'At least 3 unrelated first-time payers converge in 72h; established merchant / household exclusions.',
'NW-02':'3–4 account circular flow within 72h; same currency, hops within 10%; own sweeps excluded.'}
for title, ids in [('Transfer and money-flow catalogue',['TX-01','TX-02','TX-03','TX-04','TX-05','HV-01','TX-06','TX-07','TX-08','TX-09']),('Access, identity and lending catalogue',['LG-01','LG-02','LG-03','DV-01','DV-02','DV-03','AP-01','AP-02','AP-03','AP-04','ID-01','ID-02','NW-01','NW-02'])]:
    slide(title,table(['Rule','Weight','Definition'],[[i,f"{cfg['indicators'][i]['weight']:.2f}",definitions[i]] for i in ids]),appendix=True)

slide('Mitigation and duplicate-evidence policy',table(['Mitigation','Weight','Context'],[
['MT-PAYEE','0.60','At least 3 earlier similar payments to this beneficiary'],['MT-RECUR','0.50','Monthly recurrence'],['MT-KNOWN','0.20','Usual device; only alongside strong mitigation'],['MT-TENURE','0.15','At least 365 days; only alongside strong mitigation'],['MT-HOUSE','0.60','Possible household on shared device; common loan-payout guard'],['MT-OWN','0.80','Transfer between accounts of the same customer']]) + '''
<p>Mitigation weights reduce risk; the &lt;0.70 cap applies to risk indicators. LG-02 plus DV-03 suspends MT-PAYEE, MT-RECUR and MT-TENURE.</p>
<p><strong>Families:</strong> amount {TX-01, TX-02, HV-01, TX-06, TX-07}; new payee {TX-03, TX-05}; failed login {LG-01–03}; identity {ID-01, ID-02}; coordination {AP-01, AP-04}; pass-through {AP-03, TX-09}.</p>''',appendix=True)

slide('Coverage by planted scenario',table(['Scenario','Kind','D2 Medium+','D3 Medium+'],[[k.replace('_',' '),v['kind'],f"{v['medium_plus']}/{v['total']}",f"{d3['by_scenario'][k]['medium_plus']}/{d3['by_scenario'][k]['total']}"] for k,v in d2['by_scenario'].items()]) + '<p class="muted">An incident is caught if an attributed alert reaches Medium or High. Attribution uses planted entity/event IDs; alert evidence IDs alone do not determine ownership.</p>',appendix=True)

slide('Six layers: what exists and what follows',table(['Layer','This build','Next step / prerequisite'],[
['Graph / links','Shared-entity, convergence and circular-path rules','General path evidence; hub suppression; no guilt by association'],
['Anomaly detection','Median/MAD per-customer statistics','Bounded multivariate model in shadow; evaluate before scoring'],
['Supervised ML','No trained fraud classifier or verified training corpus','Resolved outcomes, leakage-safe snapshots, fresh time holdout'],
['External intelligence','No live SIM-swap, device-risk, mule-list or KYC feeds','Real providers with query time, response provenance and missing-data states'],
['Human controls','Case decisions and append-only audit trail','Second review / dual approval; insider evidence needs staff logs'],
['Monitoring','Golden/synthetic evaluation and per-run coverage','Rule volumes, reviewed outcome rates, feed health and drift over time']]) + '''
<p>Combined issue priority: <a href="https://github.com/mansh7763/Azentio/issues/5">#5 evaluation</a> → <a href="https://github.com/mansh7763/Azentio/issues/6">#6 rule correctness</a> → <a href="https://github.com/mansh7763/Azentio/issues/7">#7 graph/monitoring roadmap</a> → <a href="https://github.com/mansh7763/Azentio/issues/8">#8 bounded ML proposal</a>. The older ML-first recommendation is not this freeze’s implementation status.</p>''',appendix=True)

slide('Judge questions: concise, honest answers',table(['Question','Answer'],[
['How did you derive these patterns?','Mechanism → observable event sequence → legitimate twin → discriminating evidence → development tests. Provenance must distinguish a published typology from a team hypothesis.'],
['Why these weights?','Heuristic evidence priorities, bounded below High individually, tested with paired scenarios. They are not calibrated probabilities.'],
['Can we put our weights into ML?','Yes, as weighted rule features or a benchmark. Learning fraud still requires valid outcomes; fitting to rule scores only distils existing rules.'],
['Do you detect unseen fraud?','Statistical rules flag some unusual activity. We have not established general unseen-fraud detection.'],
['Does a shared phone mean fraud?','No. Consider household context and corroborating behaviour. Some ambiguity is irreducible with these fields.'],
['Why not build every fraud scenario?','Unavailable evidence cannot support a defensible detector. We expose coverage gaps rather than inventing data.'],
['Why is precision below 50%?','The synthetic evaluation includes background and benign alerts. It exposes workload and calibration gaps; it is not a production acceptance claim.'],
['How do you prevent future leakage?','Use earlier events and time-based baselines, test appended future rows, and gate profiles by onboarding where available. Current profile snapshots are not versioned history.'],
['What is the first improvement?','Slow-drain specificity and remaining lookalikes, followed by monitoring and evidence-linked graph analysis. ML remains a measured challenger.']]),appendix=True)

slide('Freeze record and presentation sources',f'''
<p><strong>31 October 2026 • branch c/rules-evaluation • local working-tree freeze.</strong> No push, deployment or issue closure is implied.</p>
<p>Frozen fixes: currency separation in TX-06/TX-07/TX-09/AP-03; successful positive funding checks; AP-03 rejects future applications and outbound references; ID-01 excludes profiles onboarded later; missing currency has coverage reasons.</p>
<p>Evaluation correction: each family-landline incident has its own phone. D2 lookalike errors changed from 9/48 to 5/48 because of this fixture correction, not weaker identity detection. Original-fixture before/after metrics are retained separately.</p>
<p><strong>Verification:</strong> __TEST_RESULT__; golden {golden['passed']}/{golden['total']}; D3 reported once after detector freeze. Slow-drain redesign, ML, provider integration and new graph scoring are not included.</p>
<p><strong>Rules config hash:</strong> <code>{esc(d3_report['rules_version'])}</code>. This config hash alone does not identify implementation changes; see the accompanying file-hash manifest.</p>
<ul class="sources"><li><a href="STAGE1_PLAN.md">Stage 1 plan, revision 4 and R1–R13 requirements</a></li><li><a href="EVALUATION.md">Evaluation methodology</a></li><li><a href="../backend/app/detect/rules.yaml">Actual rule weights and parameters</a> · <a href="../backend/app/score/scoring.py">Score and family implementation</a></li><li><a href="../evals/reports/priority_freeze_d2.json">D2 before/after including unchanged-fixture comparison</a> · <a href="../evals/reports/d3_heldout.md">Held-out D3 report</a></li><li><a href="../evals/reports/golden_scorecard.md">Golden scorecard</a> · <a href="../evals/reports/stage1_freeze_manifest.json">Freeze manifest</a></li><li>Suggested typology sources for future provenance: <a href="https://systemhealth.rbi.org.in/Scripts/FAQDisplay.aspx_Id%3D153%281%29.html">RBI fraud-awareness materials</a> and <a href="https://fintrac-canafe.canada.ca/guidance-directives/transaction-operation/indicators-indicateurs/fin_mltf-eng">FINTRAC transaction indicators</a>. These do not establish the origin of every current rule.</li></ul>''',appendix=True)

style = '''
:root{--bg:#f4f3ee;--ink:#152c32;--muted:#50686b;--accent:#007c78;--line:#cbd8d5;--paper:#fffefa}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font:18px/1.55 'Segoe UI',Arial,sans-serif}header{position:sticky;top:0;z-index:5;background:#152c32;color:white;display:flex;align-items:center;gap:12px;padding:12px 4vw;box-shadow:0 2px 15px #0002}header strong{margin-right:auto;letter-spacing:.08em}button,select{font:inherit;font-size:14px;border:1px solid #819a9d;border-radius:5px;padding:7px 12px;background:transparent;color:inherit;cursor:pointer}select{max-width:260px}option{color:#152c32;background:white}button:hover{background:#ffffff20}#counter{font-size:14px;min-width:50px}.slide{max-width:1280px;margin:24px auto;padding:48px 64px;background:var(--paper);min-height:690px;border-bottom:5px solid var(--accent);scroll-margin-top:85px}.eyebrow{font-size:12px;font-weight:700;letter-spacing:.16em;color:var(--accent);margin-bottom:20px}h1{font-size:44px;line-height:1.13;letter-spacing:-.035em;max-width:1050px;margin:0 0 28px;font-weight:650}h1 em{font-style:normal;color:var(--accent)}h2{font-size:24px;margin:15px 0 14px}p{margin:14px 0}.lead{font-size:25px;max-width:950px}.cols{display:grid;grid-template-columns:1fr 1fr;gap:52px}.flow{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:36px 0}.flow span{font-size:19px;border-top:3px solid var(--accent);padding:18px 4px;flex:1}.flow b{color:var(--accent)}.statement{font-size:25px;line-height:1.4;border-left:4px solid var(--accent);padding:12px 0 12px 22px;margin-top:32px}.tag{padding:13px 18px;background:#e8f2ef;font-size:16px}.muted{font-size:16px;color:var(--muted)}.formula{font-size:32px;padding:22px 0;color:var(--accent);font-weight:600}.math{font-size:26px;padding:15px 0}.bands{display:flex;margin:20px 0;gap:8px}.bands span{flex:1;padding:12px;text-align:center;background:#e3eee7}.bands span:nth-child(2){background:#fff0c8}.bands span:nth-child(3){background:#f8dad5}ul,ol{padding-left:25px}li{margin:11px 0}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:17px;line-height:1.4}th{text-align:left;background:#183b40;color:white;font-size:15px;font-weight:600}td,th{padding:13px 15px;vertical-align:top;border-bottom:1px solid var(--line)}tbody tr:nth-child(even){background:#f1f5f2}td:first-child{font-weight:600}a{color:#00726e}code{font-size:16px}.notes{display:none;border-top:1px dashed #7d9494;margin-top:32px;padding-top:15px;font-size:16px;color:#405a61}.show-notes .notes{display:block}.demo li{padding:8px 0}.demo span{display:block;font-size:17px;color:var(--muted)}.appendix{min-height:unset}.appendix h1{font-size:36px}.appendix table{font-size:15px}.appendix td,.appendix th{padding:10px 13px}.sources{font-size:16px}.present .slide{display:none;margin:0 auto;min-height:calc(100vh - 65px);border-bottom:0}.present .slide.active{display:block}footer{text-align:center;padding:30px;color:var(--muted);font-size:14px}.present footer{display:none}:focus-visible{outline:3px solid #f8b84b;outline-offset:3px}@media(max-width:800px){.slide{padding:30px 22px;margin:12px;min-height:unset}h1{font-size:34px}.cols{grid-template-columns:1fr;gap:10px}.flow{flex-wrap:wrap}.flow span{min-width:120px}header{flex-wrap:wrap;padding:10px}header strong{font-size:15px}select{max-width:150px}body{font-size:16px}.formula{font-size:24px}.lead,.statement{font-size:22px}}@media print{@page{size:A4 landscape;margin:12mm}body{background:white;font-size:12px}header,footer,.notes{display:none!important}.slide,.present .slide{display:block!important;margin:0;padding:12px 20px;min-height:0;border:0;break-after:page;max-width:none}.slide:last-of-type{break-after:auto}h1{font-size:29px;margin-bottom:20px}.eyebrow{margin-bottom:10px}h2{font-size:18px}.lead,.statement{font-size:19px}.flow{margin:20px 0}.flow span{font-size:14px}table,.appendix table{font-size:11px}td,th,.appendix td,.appendix th{padding:7px}.tag,.muted{font-size:12px}li{margin:6px 0}a{color:inherit;text-decoration:none}tr{break-inside:avoid}.formula{font-size:25px}.sources{font-size:12px}}
'''
script = '''
const slides=[...document.querySelectorAll('.slide')],select=document.querySelector('#jump');let index=0;
slides.forEach((s,i)=>{const o=document.createElement('option');o.value=i;o.textContent=(i+1)+'. '+s.querySelector('h1').textContent;select.append(o)});
function show(i,scroll=true){index=Math.max(0,Math.min(slides.length-1,i));slides.forEach((s,j)=>s.classList.toggle('active',j===index));select.value=index;document.querySelector('#counter').textContent=(index+1)+' / '+slides.length;if(scroll){if(document.body.classList.contains('present'))window.scrollTo(0,0);else slides[index].scrollIntoView()}}
document.querySelector('#prev').onclick=()=>show(index-1);document.querySelector('#next').onclick=()=>show(index+1);select.onchange=()=>show(+select.value);
document.querySelector('#mode').onclick=()=>{const on=document.body.classList.toggle('present');document.querySelector('#mode').textContent=on?'Read document':'Present';document.querySelector('#mode').setAttribute('aria-pressed',on);show(index)};
document.querySelector('#notes').onclick=()=>{const on=document.body.classList.toggle('show-notes');document.querySelector('#notes').setAttribute('aria-pressed',on)};
document.querySelector('#print').onclick=()=>window.print();
document.addEventListener('keydown',e=>{if(['SELECT','INPUT','TEXTAREA'].includes(e.target.tagName))return;if(e.key==='ArrowRight'||e.key==='PageDown'){e.preventDefault();show(index+1)}if(e.key==='ArrowLeft'||e.key==='PageUp'){e.preventDefault();show(index-1)}if(e.key==='Home')show(0);if(e.key==='End')show(slides.length-1);if(e.key==='Escape'&&document.body.classList.contains('present'))document.querySelector('#mode').click()});show(0,false);
'''
doc = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FinShield | Stage 1 presentation & technical briefing</title><style>'+style+'</style></head><body><header><strong>FINSHIELD</strong><button id="prev" aria-label="Previous section">←</button><span id="counter" aria-live="polite"></span><button id="next" aria-label="Next section">→</button><select id="jump" aria-label="Jump to section"></select><button id="mode" aria-pressed="false">Present</button><button id="notes" aria-pressed="false">Speaker notes</button><button id="print">Print / PDF</button></header><main>'+''.join(slides)+'</main><footer>Offline document • No external scripts, fonts or services • Arrow keys to navigate • Escape to leave presentation mode</footer><script>'+script+'</script></body></html>'
test_file = REPORT / 'stage1_tests.txt'
test_result = test_file.read_text(encoding='utf-8').strip() if test_file.exists() else 'final regression result pending'
doc = doc.replace('__TEST_RESULT__', esc(test_result))
target = ROOT / 'Docs/FinShield_Stage1_Presentation.html'
target.write_text(doc,encoding='utf-8')
files = list((ROOT/'backend/app/detect').rglob('*.py')) + list((ROOT/'backend/app/score').rglob('*.py')) + list((ROOT/'backend/app/features').rglob('*.py')) + [ROOT/'backend/app/detect/rules.yaml',ROOT/'evals/generate.py',ROOT/'evals/evaluate.py']
manifest={'freeze_date':'2026-10-31','branch':'c/rules-evaluation','rules_version':d3_report['rules_version'],'test_result':test_result,'note':'Local working tree including pre-existing edits; D3 reported once, no tuning afterward. Config version is not a code version.','sha256':{str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
(REPORT/'stage1_freeze_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(f'Wrote {target} ({len(slides)} sections)')
