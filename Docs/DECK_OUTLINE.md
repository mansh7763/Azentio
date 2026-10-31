# Deck Outline

Submission deadline: 6:00 PM on HackCulture (target 5:45). Final jury (top 10): about 5 minutes of pitch plus Q&A. Owner: C.

Fill the `[ ]` placeholders as milestones clear. Keep each slide to one idea, one visual and at most 3 lines of text.

## 1. Title

- Product name: `[ ]`. One line: "AI that finds fraud, explains it, and writes the case for the investigator."
- Team names, Azentio.ai Build Labs, 31 Oct 2026

## 2. Problem

- Digital fraud (mule accounts, account takeover, card testing, structuring) moves faster than manual investigation.
- Investigators drown in alerts, most of them false positives; each case means hours of stitching together transactions, devices and accounts.
- Visual: alert pile → one investigator → slow, inconsistent case reports.

## 3. Solution

- One line plus a screenshot of the case view.
- Three verbs: **Detect** (risk score with reasons) → **Investigate** (timeline + link graph) → **Explain & report** (AI summary with cited evidence, drafted case report).

## 4. Architecture

- Ingest → Detect (rules + anomaly model) → Alert queue → Case view (timeline, link graph) → AI case intelligence (Groq LLM) → Case management + dashboard.
- Stack line: FastAPI, SQLite, scikit-learn, NetworkX, Groq, React.

## 5. Detection

- Rules that fired plus the anomaly score → a 0–100 risk score with reasons.
- Example alert: `[ ]` (real one from our demo data).
- Fraud patterns covered: `[ ]` (mule ring, account takeover, structuring, card testing).

## 6. AI case intelligence

- Input: case evidence (transactions, devices, linked accounts). Output: summary, likely fraud type, evidence cited by transaction ID, next steps, drafted report.
- Guardrail: the AI only cites evidence it was given; every claim links back to a record.
- Screenshot of the AI panel.

## 7. Results and milestones

- Milestones cleared: `[ ]` of `[ ]`.
- Numbers from the demo data: alerts raised `[ ]`, true frauds caught `[ ]`, rings found `[ ]`, time to a drafted report `[ ]` seconds.

## 8. What's next

- Real-time streaming detection; investigator feedback retrains the model.
- Explainability and audit trail for regulators; data privacy (mask PII before the LLM).
- Fits Azentio's banking and insurance platforms.

## Demo script (3 minutes, driven by B)

1. Load the data → alerts appear ranked by risk.
2. Open the top alert → the risk reasons are listed.
3. Link graph → the mule ring lights up.
4. AI panel → summary with cited transactions, then the drafted report.
5. Close the case → the dashboard updates.

Backup: 2-minute screen recording made by 5:30 PM, on two laptops.

## Likely jury questions

| Question | Our answer |
| --- | --- |
| How do you handle false positives? | Reasons shown per alert; investigator marks true/false; that feedback tunes rule weights |
| Can a regulator trust the AI? | AI drafts, human decides; every claim cites a record; full audit trail |
| Is customer data safe with an LLM? | Mask PII before sending; self-hosted model option in production |
| Does it scale? | Detection is batch/stream-friendly; scoring is stateless; graph built per case |
| Why Groq? | Low latency for interactive investigation; provider is swappable behind one function |
