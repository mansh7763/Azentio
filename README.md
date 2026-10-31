# Azentio

Digital Fraud Investigation System. Plan: `Docs/STAGE1_PLAN.md` (section 0 controls). Owners: `Docs/OWNERSHIP.md`.

## Run

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt
git config core.hooksPath .githooks
./run.sh                        # Windows PowerShell: ./run.ps1
```

Backend runs on port 8000. Run tests from `backend/` with `../.venv/Scripts/python -m pytest -q`. On macOS or Linux, use `.venv/bin/python`.
