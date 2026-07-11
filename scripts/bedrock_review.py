"""Amazon Bedrock PR review — token-optimized, blocking verdict."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from bedrock_client import converse
from generate_prompt import compose_compact_review_prompt
from utils import (
    build_pr_comment_header,
    env_int,
    extract_score,
    is_trivial_diff,
    load_context,
)


def parse_sections(markdown: str) -> dict[str, str]:
    return {
        "overall_score": extract_score(markdown, "Overall Score"),
        "security": extract_score(markdown, "Security"),
        "performance": extract_score(markdown, "Performance"),
        "maintainability": extract_score(markdown, "Maintainability"),
        "regression_risk": extract_score(markdown, "Regression Risk"),
    }


def extract_verdict(markdown: str) -> str:
    match = re.search(r"\*\*(PASS|FAIL)\*\*\s*$", markdown.strip(), re.MULTILINE | re.IGNORECASE)
    if match:
        return match.group(1).upper()

    for line in reversed(markdown.strip().splitlines()):
        cleaned = line.strip().upper()
        if cleaned in ("PASS", "FAIL", "**PASS**", "**FAIL**"):
            return cleaned.replace("*", "")
    return "FAIL"


def ensure_summary_header(markdown: str) -> str:
    if markdown.strip().startswith("# AI Review Summary"):
        return markdown
    return build_pr_comment_header(parse_sections(markdown)) + markdown


def is_blocking() -> bool:
    return os.environ.get("BLOCKING_MODE", "false").lower() == "true"


def write_auto_pass(output_path: Path, verdict_path: Path, reason: str) -> None:
    report = f"# AI Review Summary\n\n{reason}\n\n## Pipeline Verdict\n\n**PASS**\n"
    output_path.write_text(report, encoding="utf-8")
    verdict_path.write_text("PASS", encoding="utf-8")


def main() -> int:
    context_dir = Path(os.environ.get("CONTEXT_DIR", "context"))
    output_path = Path(os.environ.get("OUTPUT_PATH", "artifacts/ai-review.md"))
    verdict_path = Path("artifacts/ai-review-verdict.txt")
    prompts_dir = Path(os.environ.get("PROMPTS_DIR", "prompts"))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    context = load_context(context_dir)
    changed_files = context["changed_files"]

    if is_trivial_diff(context["git_diff"], changed_files):
        write_auto_pass(output_path, verdict_path, "Trivial/no changes — AI review skipped to save tokens.")
        print("Trivial diff; auto-PASS without Bedrock call.")
        return 0

    prompt = compose_compact_review_prompt(prompts_dir, context)
    max_output = env_int("BEDROCK_MAX_OUTPUT_TOKENS", 2048)

    print(f"Bedrock review: ~{len(prompt)} input chars, max {max_output} output tokens")
    review_markdown = converse(prompt, max_tokens=max_output)
    review_markdown = ensure_summary_header(review_markdown)

    verdict = extract_verdict(review_markdown)
    output_path.write_text(review_markdown, encoding="utf-8")
    verdict_path.write_text(verdict, encoding="utf-8")

    print(f"AI review verdict: {verdict}")

    if is_blocking() and verdict != "PASS":
        print("BLOCKING: AI code review failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        output_path = Path(os.environ.get("OUTPUT_PATH", "artifacts/ai-review.md"))
        verdict_path = Path("artifacts/ai-review-verdict.txt")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            f"# AI Review Summary\n\nAI review error:\n\n```\n{exc}\n```\n\n## Pipeline Verdict\n\n**FAIL**\n",
            encoding="utf-8",
        )
        verdict_path.write_text("FAIL", encoding="utf-8")
        sys.exit(1 if is_blocking() else 0)
