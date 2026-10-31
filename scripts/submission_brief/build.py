"""Build Docs/FinShield_Submission_Brief.pdf (16:9 pages) from this file.

Numbers come from evals/reports/*.json where a chart needs them; prose numbers are copied from the reports named in
each page's source line. Run from the repo root:  python scripts/submission_brief/build.py
Needs Google Chrome (headless print-to-pdf).
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT_HTML = HERE / "FinShield_Submission_Brief.html"
OUT_PDF = ROOT / "Docs" / "FinShield_Submission_Brief.pdf"
CHROME = next((p for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                           r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe") if Path(p).exists()), None)

STABILITY = json.loads((ROOT / "evals/reports/ml_stability.json").read_text(encoding="utf-8"))

# ---------------------------------------------------------------- colours
INK, GREEN, MID, SOFT, AMBER, SOFT_AMBER, RED, GREY, LINE = (
    "#14302a", "#1f5e50", "#5f8f82", "#e6f0ec", "#b07a1f", "#f6ecd7", "#a4473f", "#5b6b66", "#d9e1dd")


# ---------------------------------------------------------------- SVG helpers
def box(x, y, w, h, title, lines=(), fill="#fff", stroke=GREEN, tcolor=INK, tsize=15, lsize=12.2, dash=False, r=8):
    d = ' stroke-dasharray="5 4"' if dash else ""
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1.4"{d}/>',
           f'<text x="{x + 12}" y="{y + 22}" font-size="{tsize}" font-weight="700" fill="{tcolor}">{title}</text>']
    for i, ln in enumerate(lines):
        out.append(f'<text x="{x + 12}" y="{y + 42 + i * 16}" font-size="{lsize}" fill="{GREY}">{ln}</text>')
    return "".join(out)


def arrow(x1, y1, x2, y2, color=GREEN, dash=False):
    d = ' stroke-dasharray="5 4"' if dash else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.8"{d} marker-end="url(#ah)"/>')


def label(x, y, text, size=11.5, color=GREY, anchor="start", weight=400):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{weight}">{text}</text>'


def architecture_svg() -> str:
    s = ['<svg viewBox="0 0 1168 540" width="1168" height="540" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI, Arial, sans-serif">',
         f'<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{GREEN}"/></marker></defs>']
    # band backgrounds
    s.append(f'<rect x="0" y="0" width="860" height="540" rx="12" fill="{SOFT}" opacity=".55"/>')
    s.append(label(14, 20, "DETERMINISTIC DECISION PATH  (the only place a score, band or case is created)", 11.5, GREEN, weight=700))
    s.append(f'<rect x="876" y="0" width="292" height="540" rx="12" fill="{SOFT_AMBER}" opacity=".7"/>')
    s.append(label(890, 20, "ADVISORY LAYER  (no write path to scores)", 11.5, AMBER, weight=700))

    # row 1: sources -> ingest -> store
    s.append(box(14, 34, 150, 92, "Source files", ["CSV · Excel · JSON", "banking · lending ·", "insurance"], fill="#fff"))
    s.append(box(196, 34, 214, 92, "1 · Ingest", ["parsers + header mapping", "mandatory-field validation", "provenance · rejected rows kept"]))
    s.append(box(442, 34, 404, 92, "2 · Canonical store  (SQLAlchemy · DATABASE_URL)",
                 ["customers · accounts · transactions · logins · applications · claims",
                  "detection_run · alert (immutable) · fraud_case · case_incident",
                  "case_event (append-only audit) · agent_suggestion"]))
    s.append(arrow(164, 80, 194, 80)); s.append(arrow(410, 80, 440, 80))

    # row 2: deterministic engine
    s.append(box(14, 160, 196, 118, "3 · Features", ["point-in-time customer", "profiles: norms, payees,", "devices, tenure, recurrence", "(no look-ahead)"]))
    s.append(box(236, 160, 250, 118, "4 · Detection  (rules.yaml)", ["23 risk indicators + 6 mitigations", "4 attack-chain floors · windows", "config hashed to a rules version", "missing data is flagged, not safe"]))
    s.append(box(512, 160, 334, 118, "5 · Scoring  (explainable)", ["noisy-OR of counted signals;", "strongest signal per fact family", "mitigations damp · chain floors lift", "contributions add up to the score"]))
    s.append(arrow(210, 219, 234, 219)); s.append(arrow(486, 219, 510, 219))
    s.append(arrow(644, 126, 644, 158, MID)); s.append(label(652, 146, "reads / writes", 10.5))

    # row 3: investigation services
    s.append(box(14, 312, 196, 120, "6 · Graph", ["shared device · phone ·", "email · payout account", "hub cap · every edge keeps", "its record IDs"]))
    s.append(box(236, 312, 250, 120, "7 · Consolidate + prioritise", ["linked group or same", "customer within 72 h", "risk · exposure/currency ·", "related events · evidence"]))
    s.append(box(512, 312, 334, 120, "8 · Case workflow", ["8 analyst actions (holds = recommendations)", "split with pinned incidents · reclassify", "append-only audit · JSON/Markdown report", "originals never change"]))
    s.append(arrow(210, 372, 234, 372)); s.append(arrow(486, 372, 510, 372))
    s.append(arrow(512, 278, 380, 310, MID)); s.append(label(404, 296, "immutable alerts", 10.5))

    # row 4: API/UI
    s.append(box(14, 466, 360, 62, "9 · FastAPI  /api", ["alerts · cases · graph · priority · detect · assistant"], lsize=12))
    s.append(box(400, 466, 446, 62, "10 · React investigation workspace", ["Overview · Data sources · Cases · Network · Ask FinShield"], lsize=12))
    s.append(arrow(374, 497, 398, 497)); s.append(arrow(630, 432, 630, 464, MID))

    # advisory column
    s.append(box(892, 34, 262, 138, "ML shadow score", ["logistic model re-weighs the", "same rule evidence; shown next", "to the rule score, labelled", "comparison-only. Trained offline."], fill="#fff", stroke=AMBER))
    s.append(box(892, 190, 262, 210, "Three agents  (LLM boundary)", ["Pattern Scout: finds what no rule", "alerted on, proposes a rule", "Ask FinShield: answers about the", "current screen, citations checked", "Reviewer memory: earlier decisions", "and notes on shared entities", "LLM off → templates + evidence"], fill="#fff", stroke=AMBER))
    s.append(box(892, 418, 262, 110, "Offline evaluation", ["seeded generator · golden 34", "held-out seeds · ML training", "reports in evals/reports"], fill="#fff", stroke=AMBER, dash=True))
    s.append(arrow(846, 250, 890, 110, AMBER, dash=True)); s.append(arrow(846, 372, 890, 292, AMBER, dash=True))
    s.append(label(872, 412, "read-only", 10.5, AMBER, "end"))
    s.append("</svg>")
    return "".join(s)


def multipliers_svg() -> str:
    rows = {m["rule"]: m for m in STABILITY["multipliers"]}
    picks = ["MT-KNOWN", "MT-TENURE", "TX-01", "TX-03", "MT-RECUR", "MT-PAYEE", "AP-04", "TX-06", "TX-04", "NW-01"]
    x0, x1, lo, hi = 215, 650, 0.4, 1.7
    sx = lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)
    s = ['<svg viewBox="0 0 700 372" width="700" height="372" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI, Arial, sans-serif">']
    for t in (0.5, 0.75, 1.0, 1.25, 1.5):
        c = INK if t == 1.0 else LINE
        s.append(f'<line x1="{sx(t)}" y1="26" x2="{sx(t)}" y2="338" stroke="{c}" stroke-width="{1.6 if t == 1.0 else 1}" {"" if t == 1.0 else "stroke-dasharray=\"3 4\""}/>')
        s.append(label(sx(t), 356, f"{t:g}×", 11.5, GREY, "middle"))
    s.append(label(sx(1.0), 16, "1.0× = hand weight confirmed", 11.5, INK, "middle", 600))
    for i, r in enumerate(picks):
        m = rows[r]
        y = 42 + i * 30.5
        up = m["multiplier"] >= 1
        col = GREEN if up else RED
        kind = "mitigation" if r.startswith("MT") else "risk"
        s.append(label(8, y + 4, r, 13, INK, weight=700))
        s.append(label(112, y + 4, "(" + kind + ")", 10.5, GREY))
        s.append(f'<line x1="{sx(m["p5"])}" y1="{y}" x2="{sx(m["p95"])}" y2="{y}" stroke="{col}" stroke-width="3.2" stroke-linecap="round"/>')
        s.append(f'<circle cx="{sx(m["multiplier"])}" cy="{y}" r="6.5" fill="{col}" stroke="#fff" stroke-width="1.5"/>')
        s.append(label(sx(m["multiplier"]) + (12 if up else -12), y - 9, f'{m["multiplier"]:.2f}', 11.5, col, "start" if up else "end", 700))
    s.append("</svg>")
    return "".join(s)


# D3 held-out (seed 3): scenario -> (incidents, at Medium+, at High). From evals/reports/d3_heldout.md.
D3_FRAUD = [("account_takeover", 4, 4, 4), ("circular_flow", 4, 4, 4), ("device_ring", 4, 4, 4), ("dormant_awakening", 4, 4, 4),
            ("identity_reuse", 4, 4, 0), ("loan_to_mule", 4, 4, 2), ("mule_dispersal", 8, 8, 6), ("payout_swarm", 4, 4, 0),
            ("recipient_convergence", 4, 4, 4), ("scam_payment", 4, 4, 0), ("slow_drain", 4, 0, 0), ("structuring", 4, 4, 0),
            ("takeover_attempt", 4, 4, 4)]


def scenario_svg() -> str:
    s = ['<svg viewBox="0 0 560 366" width="560" height="366" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI, Arial, sans-serif">']
    x0, w = 162, 330
    s.append(label(x0, 12, "light bar = Medium or High · dark bar = High", 11, GREY))
    for i, (name, n, med, high) in enumerate(D3_FRAUD):
        y = 24 + i * 26.5
        s.append(label(0, y + 12, name.replace("_", " "), 12.5, RED if med == 0 else INK, weight=600 if med == 0 else 400))
        s.append(f'<rect x="{x0}" y="{y}" width="{w}" height="16" rx="3" fill="{LINE}" opacity=".6"/>')
        s.append(f'<rect x="{x0}" y="{y}" width="{w * med / n:.1f}" height="16" rx="3" fill="{MID}"/>')
        s.append(f'<rect x="{x0}" y="{y}" width="{w * high / n:.1f}" height="16" rx="3" fill="{GREEN}"/>')
        s.append(label(x0 + w + 10, y + 12.5, f"{med}/{n} · {high} High", 11.5, RED if med == 0 else GREY))
    s.append("</svg>")
    return "".join(s)


# ---------------------------------------------------------------- page chrome
PAGES: list[str] = []


def page(eyebrow: str, title: str, body: str, tag: str = "", cls: str = "") -> None:
    n = len(PAGES) + 1
    tag_html = f'<span class="tag">{tag}</span>' if tag else ""
    PAGES.append(f'''<section class="s {cls}"><div class="eyebrow">{eyebrow}</div>{tag_html}<h1>{title}</h1>{body}
<div class="foot"><span>FinShield · Digital Fraud Investigation System · Submission brief</span><span>{n}</span></div></section>''')


def src(text: str) -> str:
    return f'<div class="src">Source: {text}</div>'


# ---------------------------------------------------------------- pages
PAGES.append(f'''<section class="s cover"><div class="cover-inner">
<div class="eyebrow light">AZENTIO HACKATHON · DIGITAL FRAUD INVESTIGATION SYSTEM</div>
<h0>FinShield</h0>
<p class="lead">Fraud investigation you can defend: deterministic rules decide, a learned model advises, three AI agents explain and suggest, and the analyst owns every decision.</p>
<div class="kpis">
<div><b>93%</b><span>of 56 planted fraud incidents caught at Medium or High on held-out data</span></div>
<div><b>0%</b><span>of 48 legitimate lookalikes raised to High</span></div>
<div><b>0.78 → 0.95</b><span>ranking quality after learning rule weights (3 unseen datasets)</span></div>
<div><b>399</b><span>automated tests passing on the submitted code</span></div>
</div>
<div class="cover-foot">Level 1 · detect, score, explain, case queue &nbsp;|&nbsp; Level 2 · correlate, network, consolidate, investigate, audit &nbsp;|&nbsp; All data is synthetic</div>
</div></section>''')

page("EXECUTIVE SUMMARY", "A system an auditor can read, not a model they have to trust", f'''
<div class="stance">
<div class="st a"><h3>Rules decide</h3><p>23 active risk indicators and 6 mitigations, weighted in one versioned file, produce every score and band. Same data and same rules always give the same alerts.</p></div>
<div class="st b"><h3>ML advises</h3><p>A sign-constrained model learned from labelled scenarios re-weighs the rule evidence. It is shown beside the score and never sets a band or a case.</p></div>
<div class="st c"><h3>Agents explain</h3><p>Pattern Scout, Ask FinShield and Reviewer memory suggest and explain. Every ID they cite is checked against the data. They work with the LLM off.</p></div>
<div class="st d"><h3>Humans decide</h3><p>Eight analyst actions, each with a reviewer and a reason. Holds are recommendations. Alerts are immutable; every correction is appended.</p></div>
</div>
<div class="cols2">
<div><h3>What it covers</h3>
<ul><li><b>Level 1.</b> Ingest CSV/Excel/JSON with validation; detect 13 fraud scenarios, including the four required; score 0–100 with named contributions; dashboard, filters, case queue.</li>
<li><b>Level 2.</b> Cross-system correlation (loan → payout → mule → insurance claim), relationship network, consolidated investigations with split, analyst workspace, audit trail, report, prioritisation.</li></ul></div>
<div><h3>Why it reads as production-minded</h3>
<ul><li>One evidence chain from file row to case report; every number traces to record IDs.</li>
<li>Failure modes designed in: LLM outage, hallucinated IDs, double counting, rule drift, hub false links.</li>
<li>Honest evaluation on seeds we never tuned on, including what we miss.</li></ul></div>
</div>
<div class="chain"><span>Ingest</span><i>›</i><span>Link</span><i>›</i><span>Detect</span><i>›</i><span>Score + explain</span><i>›</i><span>Correlate</span><i>›</i><span>Investigate</span><i>›</i><span>Decide</span><i>›</i><span>Audit + report</span></div>
{src("one evidence chain: every step keeps the record IDs behind it")}''')

page("SYSTEM ARCHITECTURE", "One deterministic path, with advisory layers kept outside it", f'''
<div class="svgwrap">{architecture_svg()}</div>
{src("backend/app (ingest, features, detect, score, graph, api, ai), evals/")}''', tag="Architecture")

page("TRUST MODEL", "Who may decide what", f'''
<p class="lead2">The central design rule: every component has a clearly bounded power. Anything probabilistic or generative sits on the advisory side of the line.</p>
<table class="matrix"><thead><tr><th>Capability</th><th>Rules engine</th><th>ML shadow</th><th>AI agents</th><th>Analyst</th></tr></thead><tbody>
<tr><td>Set the risk score and band</td><td class="y">Decides</td><td class="n">Shown beside it</td><td class="n">No</td><td class="s2">Reclassify only; original band kept</td></tr>
<tr><td>Open a case from an alert</td><td class="y">Decides (Medium/High)</td><td class="n">No</td><td class="n">No</td><td class="n">No</td></tr>
<tr><td>Group alerts into one investigation</td><td class="y">Proposes, with the reason</td><td class="n">No</td><td class="n">No</td><td class="s2">Can split; split is pinned</td></tr>
<tr><td>Change case status, record a decision</td><td class="n">No</td><td class="n">No</td><td class="n">No</td><td class="y">Decides, with reviewer + note</td></tr>
<tr><td>Touch an account or payment</td><td class="n">No</td><td class="n">No</td><td class="n">No</td><td class="s2">Recommends only; nothing executed</td></tr>
<tr><td>Write to the audit trail</td><td class="s2">System events</td><td class="n">No</td><td class="s2">AI assessment, only when saved by the analyst, labelled</td><td class="y">Decisions, actions, corrections</td></tr>
<tr><td>Propose a new rule</td><td class="n">No</td><td class="n">No</td><td class="s2">Pattern Scout suggests</td><td class="s2">Approve / dismiss recorded; rules unchanged</td></tr>
</tbody></table>
<div class="callout"><b>Proof, not promise.</b> A test runs the full golden set with and without the ML model installed and asserts that rule scores, bands and categories are identical. The golden scorecard (34/34) is byte-identical after the ML step.</div>
{src("backend/app/api/cases.py (ACTIONS), backend/tests/test_ml_shadow.py, evals/reports/golden_scorecard.md")}''', tag="Explainable first")

page("DETERMINISTIC CORE", "Same engine, opposite verdicts, and it shows why", f'''
<div class="cols3">
<div class="shot"><img src="assets/ato.jpg"/><div class="cap"><b>Account takeover · High 85</b><br/>6 failed logins, success from a never-seen device, a large transfer. Corroborated, so mitigations are suspended.</div></div>
<div class="shot"><img src="assets/household.jpg"/><div class="cap"><b>Family tablet · Low 18</b><br/>Three customers share one device (+45) but share surname and address, so the household mitigation applies (−27).</div></div>
<div class="rules">
<h3>How a score is built</h3>
<ol><li><b>Signals.</b> Each indicator fires with a weight and a strength, and lists its record IDs.</li>
<li><b>No double counting.</b> Rules that measure the same fact form a family; only the strongest counts.</li>
<li><b>Noisy-OR.</b> risk = 1 − ∏(1 − w·s). No weight reaches 0.70, so no single indicator is High alone.</li>
<li><b>Mitigations.</b> Known payee, tenure, recurrence, household, own-account lower risk, and switch off when a login attack is active.</li>
<li><b>Chain floors.</b> Ordered attack patterns lift the score: takeover 85 / 70 / 55 (capped below High), loan-to-mule 80.</li>
<li><b>Bands.</b> Medium ≥ 40, High ≥ 70. Contributions add up exactly to the score.</li></ol>
</div></div>
{src("backend/app/score/scoring.py, backend/app/detect/rules.yaml, evals/reports/golden_scorecard.md")}''', tag="Level 1")

page("ONE CASE, END TO END", "From four loose records to one defensible investigation", f'''
<div class="flow">
<div class="fl"><div class="num">1</div><h4>Records</h4><p>3 loan applications on device <b>DEV-RING</b> with one phone; payout to <b>A-C011</b>; outflows to MULE-0/1/2; claims <b>CLM-1</b>, <b>CLM-2</b> paid into A-C011.</p></div>
<div class="ar">›</div>
<div class="fl"><div class="num">2</div><h4>Indicators</h4><p>Shared-device applications, phone reuse, loan-to-mule cash-out. Four alerts, each with named contributions and record IDs.</p></div>
<div class="ar">›</div>
<div class="fl"><div class="num">3</div><h4>Linked group</h4><p>Customers joined only by device, phone, email or payout account. Reason stored: <i>device DEV-RING and phone 9000000001 shared by C010–C013</i>.</p></div>
<div class="ar">›</div>
<div class="fl"><div class="num">4</div><h4>One case</h4><p><b>CASE-7085d89848</b>, High, priority 87, evidence strong. Why grouped is shown; any alert can be split out.</p></div>
<div class="ar">›</div>
<div class="fl"><div class="num">5</div><h4>Decision + record</h4><p>Reviewer + note for each action. Hold is a recommendation. AI assessments are labelled and rejectable. Report downloads as JSON or Markdown.</p></div>
</div>
<div class="cols2 tight">
<div class="shot2"><img src="assets/network.jpg"/><div class="cap">Network around C011: every edge is a shared identifier, and hovering shows the record IDs that prove it.</div></div>
<div class="shot2"><img src="assets/workspace2.jpg"/><div class="cap">Case workspace: why these alerts are grouped, split, eight analyst actions with a reviewer and note, report download.</div></div>
</div>
{src("live demo dataset, case CASE-7085d89848; backend/app/graph, backend/app/api/cases.py")}''', tag="Level 2")

page("LEARNED WEIGHTS", "Trained models calibrate the weights; they do not replace the rules", f'''
<div class="cols-ml">
<div>
<h3>What was trained, and on what</h3>
<ul>
<li><b>Features.</b> Per scoring unit: each rule's evidence (weight × strength) plus whether an attack-chain floor applied. <b>Primary parameters</b> are the risk indicators; <b>derived parameters</b> are the mitigations and the chain floor.</li>
<li><b>Labels.</b> Planted incidents in a seeded synthetic generator, with labelled lookalikes.</li>
<li><b>Model A (selected).</b> Logistic regression with sign bounds (risk ≥ 0, mitigation ≤ 0) and a pull toward the hand weights. Output: a multiplier per rule.</li>
<li><b>Model B (rejected).</b> Gradient-boosted trees with monotonic constraints, explained by permutation importance. Higher recall but lookalike false positives rose to 25% at Medium+ (8% at High).</li>
<li><b>Protocol.</b> Train on pooled seeds 2, 6, 7 (3,097 units, 512 fraud); test on unseen seeds 4, 5, 8 at matched alert volume; 50 bootstrap resamples by incident for 90% intervals.</li>
</ul>
<table class="mini"><thead><tr><th>Unseen datasets, mean of 3</th><th>Hand</th><th>Learned</th></tr></thead><tbody>
<tr><td>Ranking quality (average precision)</td><td>0.78</td><td><b>0.95</b></td></tr>
<tr><td>Precision of Medium+ alerts</td><td>76%</td><td><b>88%</b></td></tr>
<tr><td>Background false alarms</td><td>35</td><td><b>17</b></td></tr>
<tr><td>Lookalikes wrongly at Medium+</td><td>10%</td><td><b>8%</b></td></tr>
<tr><td>Fraud caught at Medium+ (unchanged)</td><td>89%</td><td>89%</td></tr>
</tbody></table>
</div>
<div>
<h3>What the model says about our hand weights</h3>
<div class="chart">{multipliers_svg()}</div>
<p class="note">Dot = learned multiplier on the hand weight; whisker = 90% bootstrap interval. Known-payee, tenure, new-payee and amount rules deserve more weight; network convergence (NW-01) deserves much less. The rare rules stay near 1.0: not enough evidence to move them.</p>
</div></div>
<div class="callout amber"><b>Shadow first, promote on evidence.</b> The learned score runs on every alert and is labelled comparison-only. It earns promotion to the official score only after analyst feedback confirms it on real data.</div>
{src("evals/reports/ml_stability.md, learned_weights.md; backend/app/detect/ml.py, ml_model.json (rules version d88c05508daf). Unit-level metrics on synthetic data.")}''', tag="Trained models")

page("THREE AGENTS", "AI that assists the system and the analyst, and never decides", f'''
<div class="agents">
<div class="ag"><div class="ah">Assists the <b>system</b></div><h3>Pattern Scout</h3>
<p class="what">Finds linked behaviour that no rule alerted on: customers sharing a device, phone or payout account with no Medium/High alert; several customers starting to pay the same new account.</p>
<ul><li>Deterministic mining finds candidates and their record IDs.</li><li>The LLM only words a hypothesis (with an innocent explanation) and a suggested rule.</li><li>Approve / dismiss needs a note; approving never changes a rule or score. Decisions survive re-scans.</li></ul></div>
<div class="ag"><div class="ah">Assists the <b>analyst and evaluator</b></div><h3>Ask FinShield</h3>
<p class="what">Answers questions about what is on screen: why a case is High, what links these customers, what to verify first.</p>
<ul><li>The browser sends only the route and IDs; the backend loads the data from the store.</li><li>Every cited ID must exist in that data, otherwise it is dropped and shown as dropped.</li><li>Record text is data, never instructions. Context is bounded in size.</li><li>An answer can be saved to the case as a labelled AI assessment, and rejected later.</li></ul></div>
<div class="ag"><div class="ah">Assists <b>continuity</b></div><h3>Reviewer memory</h3>
<p class="what">Brings earlier reviewers' decisions, actions and notes on this case, and on cases sharing its customer or account, into the investigation.</p>
<ul><li>Reads the append-only case history; nothing is rewritten.</li><li>Shown as "What earlier reviewers found" and passed to Ask FinShield as context.</li><li>System events are excluded; only human and AI-labelled entries count.</li></ul></div>
</div>
<div class="contract"><div><b>1 · Screen</b>Browser sends the route and IDs only</div><i>›</i><div><b>2 · Load</b>Backend reads the data from the store</div><i>›</i><div><b>3 · LLM</b>Words an answer or hypothesis; no tools, no writes</div><i>›</i><div><b>4 · Check</b>Every cited ID must exist; others are dropped</div><i>›</i><div><b>5 · Label</b>Marked AI-generated; saved only by the analyst</div><i>›</i><div><b>6 · Review</b>Analyst accepts, rejects or ignores; rules and scores untouched</div></div>
<div class="guards" style="margin-top:16px"><b>Shared guardrails</b><span>Never decide</span><span>Real IDs only</span><span>Data, not orders</span><span>Labelled and rejectable</span><span>Works with AI off</span></div>
<p class="note">Model: openai/gpt-oss-120b on Groq (GROQ_MODEL). The ML shadow score is a classifier, not an agent.</p>
{src("backend/app/graph/scout.py, backend/app/ai/assistant.py, backend/app/graph/store.py")}''', tag="Agents")

page("SCALABILITY", "Built and measured today, and the production path we would take", f'''
<div class="cols2 two">
<div class="box built"><h3>Built and measured</h3>
<ul>
<li><b>6× faster detection</b> with identical output: 123 s → 19 s on 17k transactions and 11k logins, by removing quadratic hot spots (binary-search windows, sorted per-customer history).</li>
<li><b>Idempotent runs.</b> Run ID is derived from data and rules; re-running the same inputs reuses the stored run with no new rows.</li>
<li><b>Stable incident keys.</b> A case follows the same incident across runs; pinned splits are never undone.</li>
<li><b>Rules as versioned config.</b> One file, hashed to a version; a change creates a new version and old alerts stay as history.</li>
<li><b>Separable stages.</b> Signal collection and scoring are separate functions, so variants can be re-scored without recomputation.</li>
<li><b>State in the database.</b> Pagination on lists; storage chosen by DATABASE_URL (SQLite or Postgres); alerts and audit events locked by database triggers.</li>
<li><b>Bounded graph and AI cost.</b> Hub nodes capped; assistant context capped; LLM calls time-limited with a deterministic fallback.</li>
</ul></div>
<div class="box path"><h3>Production path (designed, not built)</h3>
<ul>
<li><b>Storage.</b> Postgres URLs and immutability triggers are already supported; next: validate at volume and add indexes on entity and time.</li>
<li><b>Workers.</b> Run detection as background jobs per tenant and per window instead of in the request.</li>
<li><b>Streaming.</b> Incremental ingestion with windowed re-scoring for real-time alerts.</li>
<li><b>Identity.</b> Login, roles and four-eyes approval before any account-affecting action is allowed.</li>
<li><b>Feedback loop.</b> Analyst outcomes retrain the shadow model; approved Pattern Scout suggestions become tested rules through a rule editor.</li>
<li><b>Observability.</b> Per-stage timings, alert-volume and drift dashboards.</li>
</ul>
<p class="note">Not yet tested: Postgres under load, multi-user concurrency, or volumes beyond the synthetic sets.</p></div>
</div>
{src("git history (perf commit d666d6a), backend/app/api/alert_store.py, backend/app/config.py, backend/app/detect/config.py")}''', tag="Design patterns")

RISKS = [
    ("LLM invents an entity or ID", "Citations checked against the loaded data; unverifiable IDs dropped and shown", "ai/assistant.py"),
    ("Instructions hidden in record text", "Record text passed as data; model has no tools and no write path", "ai/assistant.py"),
    ("LLM is down or slow", "Time-limited calls; templates and quoted evidence take over", "graph/scout.py"),
    ("Model overreach", "ML shadow only; test asserts identical rule output with and without it", "tests/test_ml_shadow.py"),
    ("Double counting one fact", "Indicator families: only the strongest counts", "score/scoring.py"),
    ("False links from popular IDs", "Hub cap; only device, phone, email, payout account group customers", "graph/builder.py"),
    ("Rule drift hides history", "Rules hashed to a version; old alerts stay as snapshots", "detect/config.py"),
    ("Wrongful account action", "Hold and verification are recorded recommendations, not executed", "api/cases.py"),
    ("Re-run undoes an analyst split", "Split incidents are pinned across runs", "api/cases.py"),
    ("Mixed currencies summed", "Exposure kept per currency, never added across", "graph/priority.py"),
    ("Weak evidence ranked first", "Single-fact cases capped below top and labelled needs review", "graph/priority.py"),
    ("Tuning on the data we report", "Reported on seeds never used for tuning", "evals/"),
]
rows = "".join(f"<tr><td>{a}</td><td>{b}</td><td class='code'>{c}</td></tr>" for a, b, c in RISKS)
page("RISKS AND MITIGATIONS", "Failure modes we designed for, and where to check each one", f'''
<table class="risk"><thead><tr><th>Risk</th><th>Mitigation</th><th>Where</th></tr></thead><tbody>{rows}</tbody></table>
{src("backend/app (paths shown), evals/reports")}''', tag="Enterprise controls")

page("EVALUATION", "Measured on held-out synthetic data we did not tune on", f'''
<div class="cols-eval">
<div>
<div class="kp"><div><b>93%</b><span>of 56 fraud incidents caught at Medium+</span></div><div><b>57%</b><span>caught at High</span></div><div><b>0%</b><span>of 48 lookalikes at High (8% at Medium)</span></div><div><b>100%</b><span>recall on 16 brand-new customers</span></div></div>
<div class="chart sm">{scenario_svg()}</div>
</div>
<div>
<h3>Read these numbers honestly</h3>
<ul>
<li>Synthetic data with planted, labelled scenarios. It measures the rules against what we can simulate, not real-world fraud rates.</li>
<li><b>Open gap:</b> slow drain (small amounts over a long time) stays below Medium: 0 of 4.</li>
<li>All 4 lookalike false positives are one scenario, loan_paid_to_supplier: 4 of 4 reach Medium, none reach High.</li>
<li>Held-out workload: 9.5 Medium/High alerts per 1,000 events; 36 background false alarms.</li>
<li>Precision of Medium/High alerts is 50% on this held-out set, counted per alert. The learned-weights table counts per scoring unit on three other seeds (76% to 88%), so the two are not directly comparable.</li>
<li>34 of 34 hand-built calibration scenarios behave as designed; 399 backend tests pass.</li>
</ul>
</div></div>
{src("evals/reports/d3_heldout.md (seed 3), golden_scorecard.md, ml_stability.md. Rules version d88c05508daf.")}''', tag="Evaluation")

page("LIMITS AND NEXT STEPS", "What we did not claim, and what comes next", f'''
<div class="cols2 two">
<div class="box"><h3>Limits today</h3><ul>
<li>Synthetic data only; metrics are on simulated scenarios, not production fraud rates.</li>
<li>Reviewer identity is a typed name; no login or role-based approval yet.</li>
<li>Slow-drain fraud is not caught at Medium.</li>
<li>Hold and verification are recommendations; no payment system is connected.</li>
<li>AI wording depends on the LLM service; when off, the app falls back to quoted evidence.</li>
<li>Learned weights are calibrated on synthetic scenarios and shown only as a shadow score.</li>
</ul></div>
<div class="box"><h3>Next steps</h3><ul>
<li>Analyst feedback (confirmed fraud / false positive) retrains the shadow model; promote it only on real-data evidence.</li>
<li>Login, roles and four-eyes approval for account-affecting actions.</li>
<li>Streaming ingestion and windowed re-scoring.</li>
<li>Approved Pattern Scout suggestions become tested rules through the rule editor.</li>
<li>Long-window indicators for slow-drain and collusion patterns.</li>
</ul></div>
</div>''', tag="Honest limits")

page("VERIFY IT YOURSELF", "Run it, click it, check the numbers", f'''
<div class="cols2 two">
<div class="box"><h3>Run</h3>
<pre>python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt
./run.ps1                      # backend on :8000
cd frontend &amp;&amp; npm run dev    # UI on :5173
# UI: Data sources → Load demo dataset → Run detection

cd backend &amp;&amp; ../.venv/Scripts/python -m pytest -q    # 399 tests</pre>
<h3>Demo click path</h3>
<ol><li><b>Overview.</b> Filter, open <i>T-C002-ATO</i> (High 85); include Low and open <i>DEV-HOME</i> (Low 18).</li>
<li><b>Cases.</b> Open <i>CASE-7085d89848</i>: why grouped, priority factors, split, actions, report download.</li>
<li><b>Network.</b> View network, click <i>DEV-RING</i> and <i>A-C011</i>; Run Pattern Scout; approve one with a note.</li>
<li><b>Ask FinShield.</b> "What links these customers?"; save to the case as an AI assessment.</li></ol></div>
<div class="box"><h3>Where each claim is evidenced</h3>
<table class="mini ev"><tbody>
<tr><td>Held-out detection results</td><td class="code">evals/reports/d3_heldout.md</td></tr>
<tr><td>34 calibration scenarios</td><td class="code">evals/reports/golden_scorecard.md</td></tr>
<tr><td>Learned weights, intervals</td><td class="code">evals/reports/ml_stability.md</td></tr>
<tr><td>Rule weights and floors</td><td class="code">backend/app/detect/rules.yaml</td></tr>
<tr><td>Scoring logic</td><td class="code">backend/app/score/scoring.py</td></tr>
<tr><td>Relationship graph</td><td class="code">backend/app/graph/builder.py</td></tr>
<tr><td>Case actions, split, report</td><td class="code">backend/app/api/cases.py</td></tr>
<tr><td>Agents</td><td class="code">graph/scout.py · ai/assistant.py</td></tr>
<tr><td>Trust boundary test</td><td class="code">backend/tests/test_ml_shadow.py</td></tr>
</tbody></table>
<p class="note">Demo data is synthetic and shipped with the repo. Reviewer names are typed text until login exists.</p></div>
</div>''', tag="Reproducible")

CSS = f'''
@page {{ size: 1280px 720px; margin: 0 }}
* {{ box-sizing: border-box }}
html, body {{ margin: 0; padding: 0; background: #fff }}
body {{ font-family: "Segoe UI", Arial, sans-serif; color: {INK}; -webkit-print-color-adjust: exact; print-color-adjust: exact }}
.s {{ width: 1280px; height: 720px; position: relative; overflow: hidden; padding: 34px 56px 44px; background: #fbfaf6; break-after: page; page-break-after: always }}
.s:last-child {{ break-after: auto; page-break-after: auto }}
.eyebrow {{ font-size: 12px; letter-spacing: .09em; color: {GREY}; font-weight: 600 }}
.eyebrow.light {{ color: #b8d3c9 }}
h1 {{ font-size: 31px; line-height: 1.15; margin: 5px 0 14px; color: {INK}; font-weight: 700; max-width: 1060px }}
h0 {{ display: block; font-size: 92px; font-weight: 800; letter-spacing: -.02em; margin: 14px 0 6px }}
h3 {{ font-size: 16px; margin: 0 0 8px; color: {GREEN} }}
h4 {{ font-size: 15px; margin: 4px 0 4px }}
p {{ margin: 0 }}
ul, ol {{ margin: 0; padding-left: 20px; font-size: 15.2px; line-height: 1.45 }}
li {{ margin: 0 0 8px }}
.tag {{ position: absolute; top: 30px; right: 56px; background: {SOFT_AMBER}; color: {AMBER}; border-radius: 6px; padding: 4px 10px; font-size: 12px; font-weight: 700 }}
.foot {{ position: absolute; left: 56px; right: 56px; bottom: 16px; display: flex; justify-content: space-between; font-size: 10.5px; color: #8a9893 }}
.src {{ position: absolute; left: 56px; right: 56px; bottom: 36px; font-size: 10.2px; color: #7c8b86 }}
.cover {{ background: linear-gradient(135deg, #14302a 0%, #1f5e50 100%); color: #fff; padding: 0 }}
.cover-inner {{ padding: 64px 72px; height: 100% }}
.cover .lead {{ font-size: 24px; line-height: 1.38; max-width: 900px; color: #e9f3ef }}
.kpis {{ display: flex; gap: 18px; margin-top: 46px }}
.kpis div {{ flex: 1; background: rgba(255,255,255,.09); border: 1px solid rgba(255,255,255,.22); border-radius: 12px; padding: 18px 18px 16px }}
.kpis b {{ display: block; font-size: 38px; line-height: 1.1; color: #fff; margin-bottom: 8px }}
.kpis span {{ font-size: 13.2px; line-height: 1.35; color: #cfe3db }}
.cover-foot {{ position: absolute; left: 72px; bottom: 34px; font-size: 13px; color: #b8d3c9 }}
.stance {{ display: flex; gap: 14px; margin: 4px 0 20px }}
.st {{ flex: 1; border-radius: 12px; padding: 18px 18px 16px; border: 1.5px solid {LINE}; background: #fff; border-top: 5px solid {GREEN} }}
.st.b {{ border-top-color: {AMBER} }} .st.c {{ border-top-color: {MID} }} .st.d {{ border-top-color: {INK} }}
.st h3 {{ font-size: 21px; color: {INK}; margin-bottom: 6px }}
.st p {{ font-size: 15px; line-height: 1.45; color: #3b4d47 }}
.cols2 {{ display: flex; gap: 36px }} .cols2 > div {{ flex: 1 }}
.cols2.two > div {{ flex: 1 }}
.cols3 {{ display: flex; gap: 24px; align-items: flex-start }}
.svgwrap {{ margin-top: 2px }}
.lead2 {{ font-size: 16.5px; color: #3b4d47; margin: -2px 0 12px; max-width: 1050px; line-height: 1.4 }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px }}
th, td {{ border-bottom: 1px solid {LINE}; padding: 8px 10px; text-align: left; vertical-align: top }}
th {{ background: {SOFT}; color: {INK}; font-size: 13.4px }}
.matrix td {{ padding: 10px 12px }} .matrix td:first-child {{ font-weight: 600 }}
.matrix td.y {{ background: #e3f1ea; color: {GREEN}; font-weight: 700 }}
.matrix td.n {{ color: #9aa7a2 }}
.matrix td.s2 {{ background: {SOFT_AMBER}; color: #6b4a10 }}
.callout {{ margin-top: 14px; background: {SOFT}; border-left: 5px solid {GREEN}; padding: 13px 18px; font-size: 14.6px; line-height: 1.4; border-radius: 6px }}
.chain {{ display: flex; align-items: center; gap: 8px; margin-top: 22px }}
.chain span {{ flex: 1; text-align: center; background: {GREEN}; color: #fff; border-radius: 8px; padding: 12px 6px; font-size: 14px; font-weight: 600 }}
.chain i {{ color: {GREEN}; font-style: normal; font-size: 22px; font-weight: 700 }}
.contract {{ display: flex; align-items: stretch; gap: 8px; margin-top: 18px }}
.contract div {{ flex: 1; background: #fff; border: 1.5px solid {LINE}; border-radius: 9px; padding: 10px 11px; font-size: 13px; line-height: 1.38 }}
.contract b {{ display: block; color: {GREEN}; font-size: 13.5px; margin-bottom: 3px }}
.contract i {{ align-self: center; color: {GREEN}; font-style: normal; font-size: 20px; font-weight: 700 }}
.callout.amber {{ background: {SOFT_AMBER}; border-left-color: {AMBER} }}
.shot {{ flex: 0 0 322px; background: #fff; border: 1px solid {LINE}; border-radius: 10px; padding: 8px }}
.shot img {{ width: 100%; height: auto; border-radius: 6px; display: block }}
.cap {{ font-size: 13px; line-height: 1.4; color: #3b4d47; padding: 8px 4px 2px }}
.rules {{ flex: 1 }} .rules ol li {{ font-size: 15px; margin-bottom: 11px }}
.flow {{ display: flex; align-items: stretch; gap: 6px; margin-bottom: 14px }}
.fl {{ flex: 1; background: #fff; border: 1.5px solid {LINE}; border-radius: 10px; padding: 14px 13px 12px; position: relative }}
.fl p {{ font-size: 13px; line-height: 1.4; color: #3b4d47 }}
.num {{ width: 22px; height: 22px; border-radius: 50%; background: {GREEN}; color: #fff; font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; position: absolute; top: -9px; left: 10px }}
.ar {{ align-self: center; color: {GREEN}; font-size: 22px; font-weight: 700 }}
.tight {{ gap: 20px; margin-top: 8px }}
.shot2 {{ background: #fff; border: 1px solid {LINE}; border-radius: 10px; padding: 7px }}
.shot2 img {{ width: 100%; height: 262px; object-fit: cover; object-position: top; border-radius: 6px; display: block }}
.cols-ml {{ display: flex; gap: 34px }} .cols-ml > div:first-child {{ flex: 0 0 540px }} .cols-ml > div:last-child {{ flex: 1 }}
.cols-ml ul li {{ font-size: 12.6px; line-height: 1.36; margin-bottom: 4px }}
.mini {{ font-size: 12.5px; margin-top: 8px }} .mini th, .mini td {{ padding: 5px 9px }}
.chart {{ background: #fff; border: 1px solid {LINE}; border-radius: 10px; padding: 8px 8px 2px }}
.chart svg {{ display: block; width: 100%; height: auto }}
.note {{ font-size: 12px; color: {GREY}; line-height: 1.4; margin-top: 8px }}
.agents {{ display: flex; gap: 16px }}
.ag {{ flex: 1; background: #fff; border: 1.5px solid {LINE}; border-radius: 12px; padding: 14px 16px; border-top: 5px solid {GREEN} }}
.ag:nth-child(2) {{ border-top-color: {AMBER} }} .ag:nth-child(3) {{ border-top-color: {MID} }}
.ah {{ font-size: 11.5px; color: {GREY}; margin-bottom: 3px }}
.ag h3 {{ font-size: 21px; color: {INK}; margin-bottom: 6px }}
.what {{ font-size: 14.6px; line-height: 1.42; margin-bottom: 10px; color: #2f423c }}
.ag ul li {{ font-size: 14px; line-height: 1.4; margin-bottom: 6px }}
.guards {{ margin-top: 14px; display: flex; gap: 10px; align-items: center; font-size: 13px }}
.guards span {{ background: {SOFT}; color: {GREEN}; font-weight: 600; border-radius: 20px; padding: 5px 13px }}
.box {{ background: #fff; border: 1.5px solid {LINE}; border-radius: 12px; padding: 16px 18px }}
.box.built {{ border-top: 5px solid {GREEN} }} .box.path {{ border-top: 5px solid {AMBER}; background: #fffdf8 }}
.box ul li {{ font-size: 14.6px; line-height: 1.42; margin-bottom: 9px }}
.risk td {{ font-size: 14.2px; padding: 9px 12px }} .risk td:first-child {{ font-weight: 600; width: 27% }}
.code {{ font-family: Consolas, "Courier New", monospace; font-size: 11.8px !important; color: {GREEN} }}
.cols-eval {{ display: flex; gap: 34px }} .cols-eval > div:first-child {{ flex: 0 0 620px }} .cols-eval > div:last-child {{ flex: 1 }}
.kp {{ display: flex; gap: 10px; margin-bottom: 8px }}
.kp div {{ flex: 1; background: #fff; border: 1.5px solid {LINE}; border-radius: 10px; padding: 8px 10px }}
.kp b {{ display: block; font-size: 27px; color: {GREEN} }} .kp span {{ font-size: 11.5px; line-height: 1.3; color: {GREY} }}
.chart.sm svg {{ height: 330px }}
pre {{ background: #14302a; color: #d9eee5; border-radius: 8px; padding: 11px 13px; font-size: 11.6px; line-height: 1.45; font-family: Consolas, "Courier New", monospace; white-space: pre-wrap; margin: 0 0 12px }}
.ev td {{ padding: 5.5px 9px }}
'''


def main() -> int:
    html = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>FinShield Submission Brief</title><style>{CSS}</style></head><body>{"".join(PAGES)}</body></html>'
    OUT_HTML.write_text(html, encoding="utf-8")
    if not CHROME:
        print("Chrome/Edge not found; wrote HTML only")
        return 1
    OUT_PDF.parent.mkdir(exist_ok=True)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={OUT_PDF}",
                    OUT_HTML.as_uri()], check=True, capture_output=True, timeout=180)
    print(f"{len(PAGES)} pages -> {OUT_PDF}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
