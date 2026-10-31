# FinShield investigation workspace (workstream C)

React/TypeScript analyst workspace: navigation rail, live detection summary over stored records, timeline/category charts, the six dashboard filters, evidence drill-down (with the AP-03 loan-to-mule money flow), multi-file upload with validation and rejected-row reports, ingestion history, and case decisions/history. No LLM or external font request is needed, so it runs offline.

## Run

Start the backend from the repository root:

```powershell
python -m uvicorn app.main:app --app-dir backend --port 8000
```

In a second terminal:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open http://127.0.0.1:5173. A fresh database shows a "No records stored yet" panel. **Load demo dataset** stores the demo data and scores it in one step. Uploading on **Data sources** stores the files, and Overview then prompts a detection run. Vite proxies `/api` to port 8000. For separate hosting, set `VITE_API_URL` to the backend origin (without `/api`) and configure backend CORS. `vercel.json` supplies the SPA fallback. `npm.cmd run build` type-checks and produces `dist/`.

## Integration status (main at `0d7097c`: ingestion, AP-03, stored runs and cases)

| Area | Status |
| --- | --- |
| Upload, demo load, batches, rejected rows, `/records/{entity}` (A) | **Live.** Files are parsed, validated and stored. The UI sends files one at a time, auto-detects the entity unless one is chosen, keeps going when a file fails, and lists every failure. |
| `POST /detect/run` (B + A) | **Live.** Scores stored records, then saves the run, immutable alerts and cases (Medium/High) in one transaction. Same data and rules reuse the run. |
| Dashboard (`GET /dashboard/summary`, C) | Reads the **latest stored run** and never runs detection itself, so Overview, `/api/alerts` and Cases share one `run_id`. It uses A's `filter_alerts`, and adds `records_stored` and `run_stale` so the UI can prompt a rerun after new uploads. |
| Cases (A) | **Live.** Open linked case matches the exact `alert_id`. Each decision needs a reviewer and a rationale. The UI re-reads the case and confirms both the status and a matching audit event before it reports success. A failed save shows an error and keeps the rationale. Case detail shows the original alert first, then later snapshots, each labelled with its run. |

Verified across two processes on the same database: after a restart, status and full history persist, the original alert is unchanged and the run ID is the same. A rerun creates no duplicate cases and keeps existing decisions.

- `records_processed` is the input to the shown run. `records_stored` is what is stored now. Coverage counters cover the whole run. Risk/category/result counts are for the filtered results.
- The loan-to-mule flow uses only the IDs that AP-03 cites (application → disbursement → new recipients). Shares are of the disbursed amount.
- The action card is investigator guidance only: no payment or account action is executed.

## Checks

```powershell
python -m pytest frontend/tests -q          # projection, filters, provenance, upload -> dashboard
cd frontend
npm.cmd run build
npx.cmd playwright test                     # Edge headless; starts backend on a throwaway SQLite file
```

Browser tests cover:
- the first-run empty state and demo load
- the overview, filters, evidence panel, Escape to close, and 850px layout
- the AP-03 money flow
- a real High alert → linked case → two decisions → page reload → same status, history and original score
- a failed save that is reported while the rationale is kept
- a mixed CSV+JSON upload with a dirty row, the rejected-row view, reload, and the stale-run prompt → rescore.

## Five-minute walkthrough

1. Overview: open a High result, select a factor, and show its source rows.
2. Include Low and compare it with a regular payment.
3. Filter `AP-03`: walk the loan → disbursement → mule money flow.
4. Data sources: upload a mixed CSV/JSON batch with a dirty row, show its rejected rows, and point out that the history survives a reload.
5. Open the linked case, record Requires Investigation, then False Positive. Reload: the history and the original alert remain.
6. Show the coverage gaps honestly, and note that it runs offline with no LLM.
