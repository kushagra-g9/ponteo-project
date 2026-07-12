"""Post Ponteo pipeline / PR notifications to Google Chat (incoming webhook)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Event types and which notify modes include them
EVENTS_BY_MODE: dict[str, set[str]] = {
    "off": set(),
    "minimal": {"stage_failed", "approval_required", "deploy_complete"},
    "recommended": {
        "pr_started",
        "stage_passed",
        "stage_failed",
        "approval_required",
        "deploy_complete",
    },
    "full": {
        "pr_started",
        "stage_passed",
        "stage_failed",
        "merge_ready",
        "approval_required",
        "deploy_complete",
    },
}

STATUS_ICON = {
    "success": "✅",
    "failure": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "action": "🔔",
}


def mode_allows(event_type: str) -> bool:
    mode = os.environ.get("GOOGLE_CHAT_NOTIFY_MODE", "recommended").strip().lower()
    allowed = EVENTS_BY_MODE.get(mode, EVENTS_BY_MODE["recommended"])
    return event_type in allowed


def build_card(
    *,
    title: str,
    subtitle: str,
    status: str,
    lines: list[str],
    button_label: str | None = None,
    button_url: str | None = None,
) -> dict:
    icon = STATUS_ICON.get(status, "ℹ️")
    widgets: list[dict] = [
        {
            "textParagraph": {
                "text": "<br>".join(lines),
            }
        }
    ]
    if button_label and button_url:
        widgets.append(
            {
                "buttonList": {
                    "buttons": [
                        {
                            "text": button_label,
                            "onClick": {"openLink": {"url": button_url}},
                        }
                    ]
                }
            }
        )

    return {
        "cardsV2": [
            {
                "cardId": "ponteo-pipeline",
                "card": {
                    "header": {
                        "title": f"{icon} {title}",
                        "subtitle": subtitle,
                    },
                    "sections": [{"widgets": widgets}],
                },
            }
        ]
    }


def post_webhook(webhook_url: str, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json; charset=UTF-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"Google Chat webhook returned HTTP {resp.status}")


def load_summary_lines(path: str | None) -> list[str]:
    if not path:
        return []
    summary_path = Path(path)
    if not summary_path.exists():
        return []
    return [line.rstrip("\n") for line in summary_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def compose_payload(args: argparse.Namespace) -> dict:
    repo = args.repository or "unknown/repo"
    pr = args.pr_number or "?"
    branch = args.head_ref or "unknown"
    base = args.base_ref or "main"
    actor = args.actor or "github-actions"
    run_url = args.run_url or ""
    pr_url = args.pr_url or ""

    if args.event_type == "pr_started":
        return build_card(
            title="PR pipeline started",
            subtitle=f"{repo} · PR #{pr}",
            status="info",
            lines=[
                f"<b>PR:</b> #{pr} — {args.pr_title or 'Untitled'}",
                f"<b>Branch:</b> {branch} → {base}",
                f"<b>Author:</b> {actor}",
                "Stages 1–6 will run sequentially.",
            ],
            button_label="View PR",
            button_url=pr_url,
        )

    if args.event_type == "stage_passed":
        summary = load_summary_lines(args.summary_lines_file)
        lines = [
            f"<b>Stage:</b> {args.stage or 'Unknown'}",
            f"<b>Status:</b> PASSED ✅",
            f"<b>PR:</b> #{pr} — {args.pr_title or 'Untitled'}",
            f"<b>Branch:</b> {branch} → {base}",
        ]
        if args.image_uri:
            lines.append(f"<b>Image:</b> {args.image_uri}")
        if summary:
            lines.append("")
            lines.extend(summary)
        return build_card(
            title=f"Stage passed — {args.stage or 'Pipeline stage'}",
            subtitle=f"{repo} · PR #{pr}",
            status="success",
            lines=lines,
            button_label="View workflow run",
            button_url=run_url,
        )

    if args.event_type == "stage_failed":
        return build_card(
            title=f"Pipeline failed — {args.stage or 'Unknown stage'}",
            subtitle=f"{repo} · PR #{pr}",
            status="failure",
            lines=[
                f"<b>Stage:</b> {args.stage or 'Unknown'}",
                f"<b>Reason:</b> {args.reason or 'See GitHub Actions logs.'}",
                f"<b>Branch:</b> {branch} → {base}",
                f"<b>Triggered by:</b> {actor}",
            ],
            button_label="View workflow run",
            button_url=run_url,
        )

    if args.event_type == "merge_ready":
        return build_card(
            title="Merge gates passed (Stages 1–4)",
            subtitle=f"{repo} · PR #{pr}",
            status="success",
            lines=[
                "SonarQube, AI review, tests, and Trivy/ECR all passed.",
                "This PR can be merged once branch protection checks are green.",
                f"<b>Image:</b> {args.image_uri or 'see Stage 4 logs'}",
            ],
            button_label="View PR",
            button_url=pr_url,
        )

    if args.event_type == "approval_required":
        env_name = args.environment or "production"
        return build_card(
            title="Deploy approval required (Stage 5)",
            subtitle=f"{repo} · PR #{pr} · {env_name}",
            status="action",
            lines=[
                "Stages 1–4 completed successfully.",
                f"<b>Action:</b> Approve <b>{env_name}</b> in GitHub Actions to promote the image.",
                f"<b>Image:</b> {args.image_uri or 'see Stage 4 logs'}",
                f"<b>Approver:</b> configured in GitHub Environment reviewers",
            ],
            button_label="Approve deployment",
            button_url=run_url,
        )

    if args.event_type == "deploy_complete":
        return build_card(
            title="Deploy manifest updated (Stage 6)",
            subtitle=f"{repo} · PR #{pr}",
            status="success",
            lines=[
                "ArgoCD manifest branch updated with the new image tag.",
                f"<b>Image:</b> {args.image_uri or 'unknown'}",
                f"<b>Manifest:</b> {args.manifest_path or 'argo-manifest/deployment.yaml'}",
                f"<b>Approved by:</b> {actor}",
            ],
            button_label="View workflow run",
            button_url=run_url,
        )

    raise ValueError(f"Unknown event type: {args.event_type}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Send Ponteo pipeline notification to Google Chat.")
    parser.add_argument("--event-type", required=True, choices=sorted(EVENTS_BY_MODE["full"]))
    parser.add_argument("--webhook-url", default=os.environ.get("GOOGLE_CHAT_WEBHOOK_URL", ""))
    parser.add_argument("--repository")
    parser.add_argument("--pr-number")
    parser.add_argument("--pr-title")
    parser.add_argument("--pr-url")
    parser.add_argument("--run-url")
    parser.add_argument("--head-ref")
    parser.add_argument("--base-ref")
    parser.add_argument("--actor")
    parser.add_argument("--stage")
    parser.add_argument("--reason")
    parser.add_argument("--image-uri")
    parser.add_argument("--manifest-path")
    parser.add_argument("--environment")
    parser.add_argument("--summary-lines-file", help="File with HTML summary lines (one per line)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not mode_allows(args.event_type):
        print(f"Google Chat skipped: event '{args.event_type}' not enabled for mode "
              f"'{os.environ.get('GOOGLE_CHAT_NOTIFY_MODE', 'recommended')}'")
        return 0

    webhook = (args.webhook_url or "").strip()
    if not webhook:
        print("Google Chat skipped: GOOGLE_CHAT_WEBHOOK_URL not configured.")
        return 0

    payload = compose_payload(args)
    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return 0

    try:
        post_webhook(webhook, payload)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"Google Chat webhook failed: HTTP {exc.code} {body}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Google Chat webhook failed: {exc}", file=sys.stderr)
        return 1

    print(f"Google Chat notification sent: {args.event_type}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
