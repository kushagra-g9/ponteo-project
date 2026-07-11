"""Evaluate Trivy JSON report and fail with an actionable summary."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "UNKNOWN": 4}


def parse_severities(raw: str) -> set[str]:
    return {part.strip().upper() for part in raw.split(",") if part.strip()}


def load_vulnerabilities(report_path: Path) -> list[dict]:
    if not report_path.exists():
        return []

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    findings: list[dict] = []

    for result in payload.get("Results") or []:
        target = result.get("Target", "unknown")
        result_class = result.get("Class", "unknown")
        result_type = result.get("Type", "unknown")
        for vuln in result.get("Vulnerabilities") or []:
            findings.append(
                {
                    "target": target,
                    "class": result_class,
                    "type": result_type,
                    "id": vuln.get("VulnerabilityID", "UNKNOWN"),
                    "severity": (vuln.get("Severity") or "UNKNOWN").upper(),
                    "package": vuln.get("PkgName", "-"),
                    "installed": vuln.get("InstalledVersion", "-"),
                    "fixed": vuln.get("FixedVersion") or "-",
                    "title": (vuln.get("Title") or "").strip(),
                }
            )

    return findings


def filter_findings(findings: list[dict], severities: set[str], vuln_class: str | None) -> list[dict]:
    filtered = [
        item
        for item in findings
        if item["severity"] in severities and (vuln_class is None or item["class"] == vuln_class)
    ]
    return sorted(filtered, key=lambda item: (SEVERITY_ORDER.get(item["severity"], 99), item["id"]))


def write_summary(
    *,
    stage: str,
    image: str,
    severities: set[str],
    blocking: list[dict],
    informational: list[dict],
    passed: bool,
) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    lines = [
        f"## {stage} — Trivy gate",
        "",
        f"**Image:** `{image}`",
        f"**Blocking severities:** `{', '.join(sorted(severities))}`",
        "",
    ]

    if blocking:
        lines.extend(
            [
                "### Blocking findings",
                "",
                "| Severity | CVE | Package | Installed | Fixed | Layer |",
                "|----------|-----|---------|-----------|-------|-------|",
            ]
        )
        for item in blocking:
            lines.append(
                f"| {item['severity']} | {item['id']} | {item['package']} | "
                f"{item['installed']} | {item['fixed']} | {item['class']} |"
            )
        lines.append("")

    if informational:
        lines.extend(
            [
                "### Informational OS findings (not blocking)",
                "",
                f"{len(informational)} HIGH/CRITICAL OS package issue(s) detected in the base image.",
                "Update the base image digest or track in `.trivyignore` with justification.",
                "",
            ]
        )

    lines.append("**Result:** PASS" if passed else "**Result:** FAIL — see job log for remediation steps.")
    summary = "\n".join(lines) + "\n"

    print(summary)
    if summary_path:
        Path(summary_path).open("a", encoding="utf-8").write(summary)


def print_failure(stage: str, reason: str, blocking: list[dict]) -> None:
    print(f"::error title={stage} FAILED::{reason}")
    print()
    print("=" * 72)
    print(f"{stage} FAILED")
    print("=" * 72)
    print(f"Reason: {reason}")
    print()
    if blocking:
        print("Blocking vulnerabilities:")
        for item in blocking:
            title = f" — {item['title']}" if item["title"] else ""
            print(
                f"  - [{item['severity']}] {item['id']} in {item['package']} "
                f"({item['installed']}) fixed in {item['fixed']} [{item['class']}]{title}"
            )
        print()
    print("How to fix:")
    print("  1. Application/library CVEs: run npm audit / update dependencies and rebuild.")
    print("  2. OS/base-image CVEs: pin a newer distroless digest or document in .trivyignore.")
    print("  3. Download artifact 'trivy-image-report' for the full JSON report.")
    print("=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Trivy JSON and fail with clear output.")
    parser.add_argument("--report", default="trivy-image-results.json")
    parser.add_argument("--severities", default="HIGH,CRITICAL")
    parser.add_argument("--image", default="unknown")
    parser.add_argument("--stage", default="Stage 4")
    parser.add_argument(
        "--block-class",
        default=os.environ.get("TRIVY_BLOCK_CLASS", "lang-pkgs"),
        help="Trivy result Class to block on (default: lang-pkgs / application packages).",
    )
    args = parser.parse_args()

    severities = parse_severities(args.severities)
    report_path = Path(args.report)
    all_findings = load_vulnerabilities(report_path)

    if not report_path.exists():
        print_failure(args.stage, f"Trivy report not found at {report_path}", [])
        return 1

    blocking = filter_findings(all_findings, severities, args.block_class)
    informational = filter_findings(all_findings, severities, "os-pkgs") if args.block_class != "os-pkgs" else []

    passed = not blocking
    reason = (
        "No blocking vulnerabilities found."
        if passed
        else (
            f"Trivy found {len(blocking)} {', '.join(sorted(severities))} "
            f"vulnerabilit{'y' if len(blocking) == 1 else 'ies'} in {args.block_class}."
        )
    )

    write_summary(
        stage=args.stage,
        image=args.image,
        severities=severities,
        blocking=blocking,
        informational=informational,
        passed=passed,
    )

    if passed:
        print(f"{args.stage} PASSED: {reason}")
        if informational:
            print(
                f"Note: {len(informational)} OS-layer HIGH/CRITICAL finding(s) logged as informational only."
            )
        return 0

    print_failure(args.stage, reason, blocking)
    return 1


if __name__ == "__main__":
    sys.exit(main())
