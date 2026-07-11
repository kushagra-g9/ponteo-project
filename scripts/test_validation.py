"""AI-assisted test validation — token-optimized (Stage 3)."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from bedrock_client import converse
from generate_prompt import compose_compact_test_prompt
from utils import env_bool, env_int, summarize_test_output


def extract_verdict(markdown: str) -> str:
    match = re.search(r"\*\*(PASS|FAIL)\*\*\s*$", markdown.strip(), re.MULTILINE | re.IGNORECASE)
    if match:
        return match.group(1).upper()

    for line in reversed(markdown.strip().splitlines()):
        cleaned = line.strip().upper()
        if cleaned in ("PASS", "FAIL", "**PASS**", "**FAIL**"):
            return cleaned.replace("*", "")
    return "FAIL"


def main() -> int:
    context_dir = Path(os.environ.get("CONTEXT_DIR", "context"))
    output_path = Path(os.environ.get("OUTPUT_PATH", "artifacts/test-validation.md"))
    verdict_path = Path("artifacts/test-validation-verdict.txt")
    prompts_dir = Path(os.environ.get("PROMPTS_DIR", "prompts"))
    test_output_path = Path(os.environ.get("TEST_OUTPUT_PATH", "test-output.log"))
    test_exit_code = os.environ.get("TEST_EXIT_CODE", "1")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    changed_files: list[str] = []
    changed_file_path = context_dir / "changed-files.txt"
    if changed_file_path.exists():
        changed_files = [
            line.strip()
            for line in changed_file_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    # Tests failed — fail immediately, no Bedrock call
    if test_exit_code != "0":
        test_log = test_output_path.read_text(encoding="utf-8", errors="replace") if test_output_path.exists() else ""
        failures = summarize_test_output(test_log, max_chars=1500)
        report = (
            "# Test Validation Report\n\n"
            "## Summary\n"
            f"- Test exit code: {test_exit_code}\n"
            "- Unit/integration tests failed — pipeline blocked.\n\n"
            f"```\n{failures}\n```\n\n"
            "## Pipeline Verdict\n\n**FAIL**\n"
        )
        output_path.write_text(report, encoding="utf-8")
        verdict_path.write_text("FAIL", encoding="utf-8")
        print("Tests failed; auto-FAIL without Bedrock call.")
        return 1

    # Tests passed — skip Bedrock by default to save tokens
    if env_bool("BEDROCK_SKIP_TEST_AI_ON_PASS", default=True):
        report = (
            "# Test Validation Report\n\n"
            "## Summary\n"
            "- All tests passed.\n"
            "- AI validation skipped (BEDROCK_SKIP_TEST_AI_ON_PASS=true) to reduce token usage.\n\n"
            "## Pipeline Verdict\n\n**PASS**\n"
        )
        output_path.write_text(report, encoding="utf-8")
        verdict_path.write_text("PASS", encoding="utf-8")
        print("Tests passed; auto-PASS without Bedrock call.")
        return 0

    test_output = ""
    if test_output_path.exists():
        test_output = summarize_test_output(
            test_output_path.read_text(encoding="utf-8", errors="replace"),
        )

    prompt = compose_compact_test_prompt(
        prompts_dir,
        test_exit_code=test_exit_code,
        test_summary=test_output,
        changed_files=changed_files,
    )

    max_output = env_int("BEDROCK_TEST_MAX_OUTPUT_TOKENS", 512)
    print(f"Bedrock test validation: ~{len(prompt)} input chars, max {max_output} output tokens")

    report = converse(prompt, max_tokens=max_output)
    verdict = extract_verdict(report)

    output_path.write_text(report, encoding="utf-8")
    verdict_path.write_text(verdict, encoding="utf-8")

    print(f"Test validation verdict: {verdict}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
