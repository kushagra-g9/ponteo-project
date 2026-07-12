"""Build short Google Chat summaries from Sonar, Trivy, and AI report artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from trivy_gate import filter_findings, load_vulnerabilities, parse_severities


def html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def truncate(text: str, max_chars: int = 1200) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def sonar_quality_gate(host: str, token: str, project_key: str, organization: str = "") -> dict:
    params = {"projectKey": project_key}
    if organization:
        params["organization"] = organization
    url = f"{host.rstrip('/')}/api/qualitygates/project_status?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def sonar_measures(host: str, token: str, project_key: str, organization: str = "") -> dict[str, str]:
    metric_keys = "coverage,bugs,vulnerabilities,code_smells,duplicated_lines_density"
    params = {
        "component": project_key,
        "metricKeys": metric_keys,
    }
    if organization:
        params["organization"] = organization
    url = f"{host.rstrip('/')}/api/measures/component?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    measures: dict[str, str] = {}
    for item in payload.get("component", {}).get("measures", []):
        metric = item.get("metric")
        value = item.get("value")
        if metric and value is not None:
            measures[metric] = value
    return measures


def coverage_from_jest_summary(coverage_dir: Path) -> str | None:
    summary_path = coverage_dir / "coverage-summary.json"
    if not summary_path.exists():
        return None
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    total = payload.get("total", {})
    lines = total.get("lines", {})
    pct = lines.get("pct")
    if pct is None:
        return None
    return f"{pct}%"


def sonar_summary_lines(
    *,
    host: str,
    token: str,
    project_key: str,
    organization: str = "",
    coverage_dir: Path | None = None,
) -> list[str]:
    lines = ["<b>SonarQube Report</b>"]
    try:
        gate = sonar_quality_gate(host, token, project_key, organization)
        status = gate.get("projectStatus", {}).get("status", "UNKNOWN")
        lines.append(f"<b>Quality Gate:</b> {status}")

        conditions = gate.get("projectStatus", {}).get("conditions", [])
        failed = [c for c in conditions if c.get("status") not in ("OK", None)]
        if failed:
            lines.append("<b>Failed conditions:</b>")
            for cond in failed[:5]:
                metric = cond.get("metricKey", "metric")
                actual = cond.get("actualValue", "?")
                threshold = cond.get("errorThreshold", "?")
                lines.append(f"• {metric}: {actual} (threshold {threshold})")
    except urllib.error.HTTPError as exc:
        lines.append(f"Quality gate API unavailable (HTTP {exc.code}).")
    except Exception as exc:
        lines.append(f"Quality gate lookup failed: {exc}")

    try:
        measures = sonar_measures(host, token, project_key, organization)
        if measures:
            lines.append("<b>Metrics:</b>")
            labels = {
                "coverage": "Coverage",
                "bugs": "Bugs",
                "vulnerabilities": "Vulnerabilities",
                "code_smells": "Code smells",
                "duplicated_lines_density": "Duplication",
            }
            for key, label in labels.items():
                if key in measures:
                    suffix = "%" if key in {"coverage", "duplicated_lines_density"} else ""
                    lines.append(f"• {label}: {measures[key]}{suffix}")
    except Exception:
        pass

    if coverage_dir:
        local_cov = coverage_from_jest_summary(coverage_dir)
        if local_cov:
            lines.append(f"<b>Jest line coverage:</b> {local_cov}")

    return lines


def trivy_summary_lines(
    report_path: Path,
    *,
    image: str,
    severities: str = "HIGH,CRITICAL",
    block_class: str = "lang-pkgs",
) -> list[str]:
    lines = ["<b>Trivy Scan Report</b>", f"<b>Image:</b> {html_escape(image)}"]
    if not report_path.exists():
        lines.append("Report file not found.")
        return lines

    sev_set = parse_severities(severities)
    all_findings = load_vulnerabilities(report_path)
    blocking = filter_findings(all_findings, sev_set, block_class)
    informational = filter_findings(all_findings, sev_set, "os-pkgs") if block_class != "os-pkgs" else []

    by_severity: dict[str, int] = {}
    for item in all_findings:
        sev = item["severity"]
        by_severity[sev] = by_severity.get(sev, 0) + 1

    lines.append(f"<b>Total findings:</b> {len(all_findings)}")
    if by_severity:
        parts = [f"{sev}: {count}" for sev, count in sorted(by_severity.items())]
        lines.append(f"<b>By severity:</b> {', '.join(parts)}")

    lines.append(f"<b>Blocking ({block_class}):</b> {len(blocking)}")
    if blocking:
        lines.append("<b>Top blocking CVEs:</b>")
        for item in blocking[:5]:
            lines.append(
                f"• [{item['severity']}] {item['id']} — {item['package']} "
                f"({item['installed']})"
            )
    else:
        lines.append("No blocking application/library CVEs.")

    if informational:
        lines.append(
            f"<b>OS-layer (informational):</b> {len(informational)} HIGH/CRITICAL (not blocking)"
        )

    return lines


def markdown_section(text: str, heading: str) -> str:
    pattern = rf"##\s*{re.escape(heading)}\s*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def ai_review_summary_lines(report_path: Path) -> list[str]:
    lines = ["<b>AI Code Review Summary</b>"]
    if not report_path.exists():
        lines.append("Report not available.")
        return lines

    text = report_path.read_text(encoding="utf-8", errors="replace")
    score = re.search(r"Overall Score\s*\(?(\d+/10)\)?", text, re.IGNORECASE)
    verdict = re.search(r"\*\*(PASS|FAIL)\*\*", text)
    if score:
        lines.append(f"<b>Score:</b> {score.group(1)}")
    if verdict:
        lines.append(f"<b>Verdict:</b> {verdict.group(1)}")

    for section in ("Security", "Performance", "Maintainability", "Regression Risk"):
        body = markdown_section(text, section)
        if not body:
            continue
        first_line = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
        if first_line:
            risk = re.search(r"\((Low|Medium|High)\)", first_line, re.IGNORECASE)
            risk_label = f" ({risk.group(1)})" if risk else ""
            lines.append(f"• {section}{risk_label}")

    excerpt = truncate(re.sub(r"[#*`]", "", markdown_section(text, "Summary") or text), 400)
    if excerpt:
        lines.append(f"<b>Summary:</b> {html_escape(excerpt)}")
    return lines


def test_validation_summary_lines(report_path: Path) -> list[str]:
    lines = ["<b>Test Validation Report</b>"]
    if not report_path.exists():
        lines.append("Report not available.")
        return lines

    text = report_path.read_text(encoding="utf-8", errors="replace")
    verdict = re.search(r"\*\*(PASS|FAIL)\*\*", text)
    if verdict:
        lines.append(f"<b>Verdict:</b> {verdict.group(1)}")

    for section in (
        "Test Execution Summary",
        "Regression Risks",
        "Coverage Gaps",
        "Recommended Additional Tests",
    ):
        body = markdown_section(text, section)
        if not body:
            continue
        bullets = [ln.strip("- ").strip() for ln in body.splitlines() if ln.strip().startswith("-")]
        if bullets:
            lines.append(f"<b>{section}:</b>")
            for bullet in bullets[:3]:
                lines.append(f"• {html_escape(bullet[:200])}")

    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Print Google Chat summary lines for reports.")
    parser.add_argument(
        "--type",
        required=True,
        choices=["sonar", "trivy", "ai-review", "test-validation"],
    )
    parser.add_argument("--sonar-host", default="")
    parser.add_argument("--sonar-token", default="")
    parser.add_argument("--sonar-project-key", default="")
    parser.add_argument("--sonar-organization", default="")
    parser.add_argument("--coverage-dir", default="coverage")
    parser.add_argument("--trivy-report", default="trivy-image-results.json")
    parser.add_argument("--image", default="")
    parser.add_argument("--severities", default="HIGH,CRITICAL")
    parser.add_argument("--block-class", default="lang-pkgs")
    parser.add_argument("--report-path", default="")
    args = parser.parse_args()

    if args.type == "sonar":
        summary = sonar_summary_lines(
            host=args.sonar_host,
            token=args.sonar_token,
            project_key=args.sonar_project_key,
            organization=args.sonar_organization,
            coverage_dir=Path(args.coverage_dir),
        )
    elif args.type == "trivy":
        summary = trivy_summary_lines(
            Path(args.trivy_report),
            image=args.image,
            severities=args.severities,
            block_class=args.block_class,
        )
    elif args.type == "ai-review":
        summary = ai_review_summary_lines(Path(args.report_path or "artifacts/ai-review.md"))
    else:
        summary = test_validation_summary_lines(
            Path(args.report_path or "artifacts/test-validation.md")
        )

    for line in summary:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
