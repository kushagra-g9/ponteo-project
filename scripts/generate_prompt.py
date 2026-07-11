"""Compact prompt composer — minimal tokens per PR."""

from __future__ import annotations

from pathlib import Path

from utils import select_review_focus, get_cost_mode


PROMPT_FILES = {
    "code_review": "code_review.md",
    "security_review": "security_review.md",
    "performance_review": "performance_review.md",
    "regression_analysis": "regression_analysis.md",
    "test_generation": "test_generation.md",
    "test_validation": "test_validation.md",
    "release_notes": "release_notes.md",
}


def load_prompt(prompts_dir: Path, prompt_key: str) -> str:
    filename = PROMPT_FILES[prompt_key]
    path = prompts_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def _condensed_instruction(prompts_dir: Path, key: str) -> str:
    """First 3 non-empty lines of each prompt file — enough context, fewer tokens."""
    full = load_prompt(prompts_dir, key)
    lines = [ln.strip() for ln in full.splitlines() if ln.strip() and not ln.startswith("#")]
    return " ".join(lines[:3])


def compose_compact_review_prompt(prompts_dir: Path, context: dict) -> str:
    metadata = context["metadata"]
    changed_files = context["changed_files"]
    git_diff = context["git_diff"]
    sonar = context["sonar_report"]

    focus_keys = select_review_focus(changed_files)
    instructions = "\n".join(
        f"- {key}: {_condensed_instruction(prompts_dir, key)}"
        for key in focus_keys
    )

    files_list = ", ".join(changed_files[:20])
    if len(changed_files) > 20:
        files_list += f" (+{len(changed_files) - 20} more)"

    word_limit = 350 if get_cost_mode() != "full" else 600

    return f"""Senior DevSecOps PR reviewer. Review ONLY changed files. Be concise (max {word_limit} words).

PR #{metadata.get('pr_number')}: {metadata.get('title', '')}
Files: {files_list}
Sonar: {sonar}

Focus:
{instructions}

Diff:
```diff
{git_diff}
```

Output Markdown with ONLY these sections (brief bullets):

# AI Review Summary
## Overall Score (x/10)
## Security (Low/Medium/High + top 3 findings)
## Performance (Low/Medium/High + top 2 findings)
## Maintainability (Low/Medium/High)
## Regression Risk (Low/Medium/High + top 2 risks)
## Critical Issues (or "None")
## Suggested Improvements (max 3, optional)

## Pipeline Verdict
End with exactly one line: **PASS** or **FAIL**
FAIL only for critical/security/regression High issues.
"""


def compose_compact_test_prompt(
    prompts_dir: Path,
    *,
    test_exit_code: str,
    test_summary: str,
    changed_files: list[str],
    git_diff: str = "",
    compact: bool = False,
) -> str:
    files_list = ", ".join(changed_files[:15]) or "unknown"
    diff_block = git_diff.strip() or "(no diff)"
    diff_limit = 4_000 if compact else 6_000
    if len(diff_block) > diff_limit:
        diff_block = diff_block[: diff_limit - 40] + "\n...[diff truncated]...\n"

    if compact:
        return f"""QA check (concise, max 150 words). Tests passed.

Changed: {files_list}
Test output:
```
{test_summary}
```

Diff:
```diff
{diff_block}
```

Output:
# Test Validation Report
## Test Execution Summary
## Regression Risks (max 2)
## Coverage Gaps (max 3, or None)
## Recommended Additional Tests (max 2, or None)
## Pipeline Verdict
End with **PASS** when automated tests passed (exit code 0).
End with **FAIL** only if tests failed, did not run, or there is a critical untested production path.
Advisory coverage suggestions alone must still be **PASS**.
"""

    qa_focus = _condensed_instruction(prompts_dir, "test_validation")
    regression_focus = _condensed_instruction(prompts_dir, "regression_analysis")

    return f"""AI QA engineer for a Node.js microservice PR. Be concise (max 250 words).

Tasks: summarize tests/failures, regression risks, coverage gaps.

QA: {qa_focus}
Regression: {regression_focus}

Exit code: {test_exit_code}
Files: {files_list}

Tests:
```
{test_summary}
```

Diff:
```diff
{diff_block}
```

Output sections:
# Test Validation Report
## Test Execution Summary
## Failure Summary
## Regression Risks
## Coverage Gaps
## Recommended Additional Tests
## Pipeline Verdict
End with **PASS** or **FAIL**
"""


# Legacy alias used by bedrock_review
def compose_master_prompt(prompts_dir: Path, context: dict) -> str:
    return compose_compact_review_prompt(prompts_dir, context)
