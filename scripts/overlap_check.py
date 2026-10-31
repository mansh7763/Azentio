"""Warn when teammates' changes overlap.

Local (run by the pre-push hook, or by hand before pushing):
    python scripts/overlap_check.py
CI (run by .github/workflows/overlap.yml on every push to main):
    python scripts/overlap_check.py --ci <before_sha> <after_sha>

Checks:
  1. Same file changed by you and by a teammate (local: since your branch point;
     CI: by another author in the last `recent_hours`).
  2. Files outside your workstream (needs your email in .github/workstreams.json).
  3. Shared files (schemas, main.py, requirements, ...) - always worth a heads-up.

It only warns; it never blocks a push. Uses only the standard library.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / ".github" / "workstreams.json"
ZERO_SHA = "0" * 40


def git(*args):
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


def lines(text):
    return [line for line in text.splitlines() if line.strip()]


def load_config():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def workstream_of(path, config):
    for key, ws in config["workstreams"].items():
        if any(path == p.rstrip("/") or path.startswith(p) for p in ws["paths"]):
            return key
    return None


def workstream_of_email(email, config):
    for key, ws in config["workstreams"].items():
        if email.lower() in (m.lower() for m in ws["members"]):
            return key
    return None


def commits_with_files(rev_range, extra_args=()):
    """Return [(sha, author_name, author_email, subject, [files])] for a range."""
    out = git("log", "--no-merges", "--name-only", "--format=%x1e%H%x1f%an%x1f%ae%x1f%s", *extra_args, rev_range)
    commits = []
    for block in out.split("\x1e"):
        block = block.strip()
        if not block:
            continue
        header, *files = block.splitlines()
        sha, name, email, subject = header.split("\x1f")
        commits.append((sha, name, email, subject, [f for f in files if f.strip()]))
    return commits


def ownership_findings(files, my_email, config):
    findings = []
    mine = workstream_of_email(my_email, config)
    shared = set(config["shared"])
    for path in sorted(files):
        if path in shared:
            findings.append(f"`{path}` is a **shared file** - tell the team what you changed.")
            continue
        owner = workstream_of(path, config)
        if mine and owner and owner != mine:
            ws = config["workstreams"][owner]
            findings.append(f"`{path}` belongs to workstream **{owner} ({ws['name']})**, not yours ({mine}).")
    return findings


def run_local(config):
    my_email = git("config", "user.email")
    try:
        git("fetch", "-q", "origin")
    except RuntimeError as e:
        print(f"[overlap] could not fetch origin ({e}); checking against last known state.")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    upstream = f"origin/{branch}"
    try:
        base = git("merge-base", "HEAD", upstream)
    except RuntimeError:
        print(f"[overlap] no {upstream} yet; nothing to compare.")
        return 0

    my_files = set()
    for _, _, _, _, files in commits_with_files(f"{base}..HEAD"):
        my_files.update(files)
    my_files.update(lines(git("diff", "--name-only", "HEAD")))

    findings = []
    for sha, name, email, subject, files in commits_with_files(f"{base}..{upstream}"):
        if email.lower() == my_email.lower():
            continue
        for path in sorted(my_files.intersection(files)):
            findings.append(
                f"`{path}` was also changed by **{name}** in {sha[:7]} \"{subject}\" - pull and merge before pushing."
            )
    findings += ownership_findings(my_files, my_email, config)

    if not findings:
        print("[overlap] no overlaps found.")
        return 0
    print("\n[overlap] heads-up before you push:")
    for f in findings:
        print("  - " + f.replace("**", "").replace("`", ""))
    print("[overlap] this is a warning only; the push continues.\n")
    return 0


def run_ci(config, before, after):
    if before == ZERO_SHA:
        rev_range = after
        pushed = commits_with_files(rev_range, ("-n", "20"))
    else:
        pushed = commits_with_files(f"{before}..{after}")
    if not pushed:
        return 0

    hours = config.get("recent_hours", 6)
    pushed_shas = {c[0] for c in pushed}
    recent = [
        c for c in commits_with_files(after, ("--since", f"{hours} hours ago"))
        if c[0] not in pushed_shas
    ]

    findings = []
    for sha, name, email, subject, files in pushed:
        for path in files:
            others = sorted({(n, s[:7]) for s, n, e, _, fs in recent if path in fs and e.lower() != email.lower()})
            if others:
                who = ", ".join(f"{n} ({s})" for n, s in others)
                findings.append(
                    f"{sha[:7]} by **{name}** changed `{path}`, which {who} also changed in the last {hours} h."
                )
        findings += [f"{sha[:7]} by **{name}**: {f}" for f in ownership_findings(files, email, config)]

    findings = list(dict.fromkeys(findings))
    report = "### Overlap check\n\n"
    if findings:
        report += "Teammates' work may be overlapping. Pull, check these files, and talk before the next push:\n\n"
        report += "\n".join(f"- {f}" for f in findings) + "\n"
    else:
        report += "No overlapping changes in this push.\n"
    print(report)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"found={'true' if findings else 'false'}\n")
        (ROOT / "overlap_report.md").write_text(report, encoding="utf-8")
    return 0


def main():
    config = load_config()
    if len(sys.argv) >= 4 and sys.argv[1] == "--ci":
        return run_ci(config, sys.argv[2], sys.argv[3])
    return run_local(config)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # never block a push because the checker broke
        print(f"[overlap] check skipped: {e}")
        sys.exit(0)
