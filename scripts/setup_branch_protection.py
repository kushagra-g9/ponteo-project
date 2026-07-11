#!/usr/bin/env python3
"""Apply GitHub branch protection for main (merge gates Stages 1–4 + SonarCloud).

Usage:
  export GITHUB_TOKEN=ghp_...   # repo admin scope
  python3 scripts/setup_branch_protection.py

Or rely on git credential helper (same token used for git push):
  python3 scripts/setup_branch_protection.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

OWNER = os.environ.get("GITHUB_OWNER", "kushagra-g9")
REPO = os.environ.get("GITHUB_REPO", "ponteo-project")
BRANCH = os.environ.get("PROTECTED_BRANCH", "main")

# Merge gates only — deploy approval (Stages 5–6) stays separate from merge.
REQUIRED_CHECKS = [
    "Stage 1 - SonarQube Scan",
    "Stage 2 - AI Code Review",
    "Stage 3 - AI-Assisted Tests",
    "Stage 4 - Docker Build + ECR + Trivy",
    "SonarCloud Code Analysis",
]


def get_token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True,
        text=True,
        check=True,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise SystemExit("Set GITHUB_TOKEN or configure git credentials for github.com")


def apply_protection(token: str) -> dict:
    payload = {
        "required_status_checks": {
            "strict": True,
            "contexts": REQUIRED_CHECKS,
        },
        "enforce_admins": True,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": False,
            "required_approving_review_count": 0,
        },
        "restrictions": None,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/branches/{BRANCH}/protection"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "ponteo-setup-branch-protection",
        },
        method="PUT",
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def main() -> int:
    print(f"Applying branch protection: {OWNER}/{REPO} → {BRANCH}")
    print("Required checks (merge gates):")
    for check in REQUIRED_CHECKS:
        print(f"  - {check}")
    print("Not required for merge: Stage 5 (deploy approval), Stage 6 (manifest update)")
    print()

    try:
        result = apply_protection(get_token())
    except urllib.error.HTTPError as exc:
        print(f"Failed: HTTP {exc.code} {exc.reason}", file=sys.stderr)
        print(exc.read().decode(), file=sys.stderr)
        print(
            "\nManual setup: GitHub → Settings → Branches → Add rule for 'main'",
            file=sys.stderr,
        )
        return 1

    contexts = result.get("required_status_checks", {}).get("contexts", [])
    print("Success. Active required checks:")
    for ctx in contexts:
        print(f"  ✓ {ctx}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
