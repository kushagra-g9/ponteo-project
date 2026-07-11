"""AI-assisted test validation — token-aware QA summary (Stage 3)."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from bedrock_client import converse
from generate_prompt import compose_compact_test_prompt
from utils import (
    read_text,
    should_run_test_bedrock,
    summarize_test_output,
    token_limits_for_mode,
    write_skip_report,
    env_int,
)


def extract_verdict(markdown: str, *, tests_failed: bool = False) -> str:
    match = re.search(r"\*\*(PASS|FAIL)\*\*\s*$", markdown.strip(), re.MULTILINE | re.IGNORECASE)
    if match:
        return match.group(1).upper()

    for line in reversed(markdown.strip().splitlines()):
        cleaned = line.strip().upper()
        if cleaned in ("PASS", "FAIL", "**PASS**", "**FAIL**"):
            return cleaned.replace("*", "")

    # Truncated Bedrock output often omits the final verdict line
    return "FAIL" if tests_failed else "PASS"


def finalize_verdict(test_exit_code: str, ai_verdict: str, report: str, changed_files: list[str]) -> tuple[str, str]:
    """Tests passing is the hard gate; AI FAIL is blocking only for critical cases."""
    if test_exit_code != "0":
        return "FAIL", report

    if ai_verdict == "PASS":
        return "PASS", report

    report_lower = report.lower()
    critical_markers = (
        "critical gap",
        "critical path untested",
        "no tests ran",
        "tests did not run",
        "tests failed",
        "must block merge",
    )
    if any(marker in report_lower for marker in critical_markers):
        return "FAIL", report

    note = (
        "\n\n---\n"
        "*Pipeline note: All automated tests passed. AI flagged advisory items above; "
        "they do not block the pipeline.*\n\n"
        "## Pipeline Verdict\n\n**PASS**\n"
    )
    print("Tests passed — AI FAIL downgraded to PASS (advisory QA only).")
    return "PASS", report.rstrip() + note


def load_changed_files(context_dir: Path) -> list[str]:
    changed_file_path = context_dir / "changed-files.txt"
    if not changed_file_path.exists():
        return []
    return [
        line.strip()
        for line in changed_file_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def auto_fail_report(test_exit_code: str, failures: str) -> str:
    return (
        "# Test Validation Report\n\n"
        "## Test Execution Summary\n"
        f"- Exit code: {test_exit_code}\n"
        "- Unit/integration tests failed.\n\n"
        "## Failure Summary\n"
        f"```\n{failures}\n```\n\n"
        "## Regression Risks\n"
        "Review failing tests and changed files before merge.\n\n"
        "## Coverage Gaps\n"
        "Unable to assess — fix failing tests first.\n\n"
        "## Recommended Additional Tests\n"
        "Add or fix tests covering the failing scenarios.\n\n"
        "## Pipeline Verdict\n\n**FAIL**\n"
    )


def run_bedrock_validation(
    prompts_dir: Path,
    *,
    test_exit_code: str,
    test_summary: str,
    changed_files: list[str],
    git_diff: str,
    compact: bool,
) -> str:
    limits = token_limits_for_mode()
    prompt = compose_compact_test_prompt(
        prompts_dir,
        test_exit_code=test_exit_code,
        test_summary=test_summary,
        changed_files=changed_files,
        git_diff=git_diff,
        compact=compact,
    )
    max_output = env_int("BEDROCK_TEST_MAX_OUTPUT_TOKENS", limits["test_out"])
    print(f"Bedrock test validation: ~{len(prompt)} input chars, max {max_output} output tokens")
    return converse(prompt, max_tokens=max_output)


def main() -> int:
    context_dir = Path(os.environ.get("CONTEXT_DIR", "context"))
    output_path = Path(os.environ.get("OUTPUT_PATH", "artifacts/test-validation.md"))
    verdict_path = Path("artifacts/test-validation-verdict.txt")
    prompts_dir = Path(os.environ.get("PROMPTS_DIR", "prompts"))
    test_output_path = Path(os.environ.get("TEST_OUTPUT_PATH", "test-output.log"))
    test_exit_code = os.environ.get("TEST_EXIT_CODE", "1")
    tests_failed = test_exit_code != "0"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    changed_files = load_changed_files(context_dir)
    limits = token_limits_for_mode()
    git_diff = read_text(context_dir / "git-diff.patch", max_bytes=limits["diff"] + 500)

    test_log = test_output_path.read_text(encoding="utf-8", errors="replace") if test_output_path.exists() else ""
    test_summary = summarize_test_output(test_log, max_chars=limits["test_log"])

    run_bedrock, skip_reason = should_run_test_bedrock(changed_files, tests_failed=tests_failed)
    compact_prompt = not tests_failed

    if not run_bedrock and not tests_failed:
        report = write_skip_report("Test Validation Report", skip_reason)
        output_path.write_text(report, encoding="utf-8")
        verdict_path.write_text("PASS", encoding="utf-8")
        print(f"Test AI skipped: {skip_reason}")
        return 0

    if tests_failed:
        failures = summarize_test_output(test_log, max_chars=limits["test_log"])
        try:
            report = run_bedrock_validation(
                prompts_dir,
                test_exit_code=test_exit_code,
                test_summary=test_summary,
                changed_files=changed_files,
                git_diff=git_diff,
                compact=False,
            )
        except Exception as exc:
            print(f"Bedrock unavailable for failure summary: {exc}")
            report = auto_fail_report(test_exit_code, failures)

        verdict = extract_verdict(report, tests_failed=True)
        if verdict not in {"PASS", "FAIL"}:
            verdict = "FAIL"
        output_path.write_text(report, encoding="utf-8")
        verdict_path.write_text(verdict, encoding="utf-8")
        print(f"Test validation verdict (failures): {verdict}")
        return 0 if verdict == "PASS" else 1

    report = run_bedrock_validation(
        prompts_dir,
        test_exit_code=test_exit_code,
        test_summary=test_summary,
        changed_files=changed_files,
        git_diff=git_diff,
        compact=compact_prompt,
    )
    ai_verdict = extract_verdict(report, tests_failed=False)
    verdict, report = finalize_verdict(test_exit_code, ai_verdict, report, changed_files)
    output_path.write_text(report, encoding="utf-8")
    verdict_path.write_text(verdict, encoding="utf-8")

    print(f"Test validation verdict: {verdict}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
