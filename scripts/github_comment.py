"""Publish pipeline AI reports as GitHub PR comments (comments only — no merge)."""

from __future__ import annotations

import argparse
import os
import sys

import requests

DEFAULT_MARKER = "<!-- ponteo-ai-review-bot -->"


def find_existing_comment(
    session: requests.Session,
    repo: str,
    pr_number: int,
    marker: str,
) -> int | None:
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    response = session.get(url, params={"per_page": 100})
    response.raise_for_status()

    for comment in response.json():
        if marker in comment.get("body", ""):
            return comment["id"]
    return None


def truncate_body(body: str, max_chars: int = 65000) -> str:
    if len(body) <= max_chars:
        return body
    truncated = body[: max_chars - 500]
    return truncated + "\n\n---\n*Report truncated due to GitHub comment size limits.*\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Post pipeline report to GitHub PR")
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--report-path", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--marker", default=DEFAULT_MARKER, help="HTML comment marker to find/update")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN not set", file=sys.stderr)
        return 1

    if not os.path.isfile(args.report_path):
        print(f"Report not found: {args.report_path}", file=sys.stderr)
        return 1

    report_body = open(args.report_path, encoding="utf-8").read()
    body = f"{args.marker}\n{truncate_body(report_body)}"

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )

    existing_id = find_existing_comment(session, args.repository, args.pr_number, args.marker)

    if existing_id:
        url = f"https://api.github.com/repos/{args.repository}/issues/comments/{existing_id}"
        response = session.patch(url, json={"body": body})
    else:
        url = f"https://api.github.com/repos/{args.repository}/issues/{args.pr_number}/comments"
        response = session.post(url, json={"body": body})

    response.raise_for_status()
    print(f"PR comment {'updated' if existing_id else 'created'} successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
