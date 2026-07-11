"""AI-assisted test validation — QA summary, regression risks, coverage (Stage 3)."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from bedrock_client import converse
from generate_prompt import compose_compact_test_prompt
from utils import env_bool, env_int, read_text, summarize_test_output


def extract_verdict(markdown: str) -> str:
    match = re.search(r"\*\*(PASS|FAIL)\*\*\s*$", markdown.strip(), re.MULTILINE | re.IGNORECASE)
    if match:
        return match.group(1).upper()

    for line in reversed(markdown.strip().splitlines()):
        cleaned = line.strip().upper()
        if cleaned in ("PASS", "FAIL", "**PASS**", "**FAIL**"):
            return cleaned.replace("*", "")
    return "FAIL"


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
) -> str:
    prompt = compose_compact_test_prompt(
        prompts_dir,
        test_exit_code=test_exit_code,
        test_summary=test_summary,
        changed_files=changed_files,
        git_diff=git_diff,
    )
    max_output = env_int("BEDROCK_TEST_MAX_OUTPUT_TOKENS", 1024)
    print(f"Bedrock test validation: ~{len(prompt)} input chars, max {max_output} output tokens")
    return converse(prompt, max_tokens=max_output)


def main() -> int:
    context_dir = Path(os.environ.get("CONTEXT_DIR", "context"))
    output_path = Path(os.environ.get("OUTPUT_PATH", "artifacts/test-validation.md"))
    verdict_path = Path("artifacts/test-validation-verdict.txt")
    prompts_dir = Path(os.environ.get("PROMPTS_DIR", "prompts"))
    test_output_path = Path(os.environ.get("TEST_OUTPUT_PATH", "test-output.log"))
    test_exit_code = os.environ.get("TEST_EXIT_CODE", "1")
    skip_ai_on_pass = env_bool("BEDROCK_SKIP_TEST_AI_ON_PASS", default=False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    changed_files = load_changed_files(context_dir)
    git_diff = read_text(context_dir / "git-diff.patch", max_bytes=12_500)

    test_log = test_output_path.read_text(encoding="utf-8", errors="replace") if test_output_path.exists() else ""
    test_summary = summarize_test_output(test_log)

    # Tests failed — AI summary when possible, otherwise structured auto report
    if test_exit_code != "0":
        failures = summarize_test_output(test_log, max_chars=2000)
        try:
            report = run_bedrock_validation(
                prompts_dir,
                test_exit_code=test_exit_code,
                test_summary=test_summary,
                changed_files=changed_files,
                git_diff=git_diff,
            )
        except Exception as exc:
            print(f"Bedrock unavailable for failure summary: {exc}")
            report = auto_fail_report(test_exit_code, failures)

        verdict = extract_verdict(report)
        if verdict not in {"PASS", "FAIL"}:
            verdict = "FAIL"
        output_path.write_text(report, encoding="utf-8")
        verdict_path.write_text(verdict, encoding="utf-8")
        print(f"Test validation verdict (failures): {verdict}")
        return 0 if verdict == "PASS" else 1

    # Tests passed — optional skip for token savings
    if skip_ai_on_pass:
        report = (
            "# Test Validation Report\n\n"
            "## Test Execution Summary\n"
            "- All tests passed.\n"
            "- AI validation skipped (`BEDROCK_SKIP_TEST_AI_ON_PASS=true`).\n\n"
            "## Failure Summary\nNone\n\n"
            "## Regression Risks\nNot assessed (AI skipped).\n\n"
            "## Coverage Gaps\nNot assessed (AI skipped).\n\n"
            "## Recommended Additional Tests\nNot assessed (AI skipped).\n\n"
            "## Pipeline Verdict\n\n**PASS**\n"
        )
        output_path.write_text(report, encoding="utf-8")
        verdict_path.write_text("PASS", encoding="utf-8")
        print("Tests passed; auto-PASS without Bedrock call.")
        return 0

    report = run_bedrock_validation(
        prompts_dir,
        test_exit_code=test_exit_code,
        test_summary=test_summary,
        changed_files=changed_files,
        git_diff=git_diff,
    )
    verdict = extract_verdict(report)
    output_path.write_text(report, encoding="utf-8")
    verdict_path.write_text(verdict, encoding="utf-8")

    print(f"Test validation verdict: {verdict}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
