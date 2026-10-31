# Ownership and Overlap Warnings

**Rule:** each workstream owns its folders. Touch someone else's folder or a shared file only after telling them, and pull before you push.

## Who owns what

The source of truth is `.github/workstreams.json`. **Each person adds their git email under their workstream's `members`** (find it with `git config user.email`).

| Workstream | Owner | Folders |
| --- | --- | --- |
| A — Data platform, cases and API | ____ | `backend/app/ingest/`, `backend/app/models.py`, `backend/app/api/`, `backend/app/datagen/` |
| B — Detection and risk intelligence | mansh7763 | `backend/app/features/`, `backend/app/detect/`, `backend/app/graph/`, `backend/app/score/`, `backend/tests/`, `evals/` |
| C — Investigation UI and AI | ____ | `frontend/`, `backend/app/ai/` |
| **Shared** — announce every change in chat | everyone | `backend/app/schemas.py`, `backend/app/main.py`, `requirements.txt`, `backend/requirements.txt`, `frontend/package.json`, `frontend/src/types.ts`, `.gitignore`, `.env.example` |

## How you get warned

| When | What happens | Setup |
| --- | --- | --- |
| **Before you push** | A pre-push hook fetches `origin`, then lists files you changed that a teammate also changed since your last pull, files outside your workstream, and shared files. It only warns; the push continues. | Once per clone: `git config core.hooksPath .githooks` |
| **After anyone pushes to `main`** | A GitHub Action compares the pushed commits with everyone else's commits from the last 6 hours. If they touched the same files, or someone edited another workstream's folder or a shared file, it **posts a comment on the commit**. GitHub emails the commit author and repo watchers. | Nothing. Teammates should click **Watch → All activity** on the repo to get the emails |
| **Any time** | Run the same check by hand. | `python scripts/overlap_check.py` |

## When you see a warning

1. `git pull` and look at the other person's change to that file.
2. If you both changed the same function or contract, agree on one version in chat before pushing again.
3. For shared files (`schemas.py`, `types.ts`): one person edits, everyone pulls. Never edit them in parallel.

## Habits that prevent overlaps

- Pull before you start each task, and push small commits at least every 45 minutes.
- New shared types go into `schemas.py` in their own small commit, announced in chat.
- If you need something in another workstream's folder, ask the owner, or leave a `# TODO(A): ...` comment instead of changing their code.
