"""Compact prompt composer — minimal tokens per PR."""

from __future__ import annotations

from pathlib import Path

from utils import select_review_focus


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

    return f"""Senior DevSecOps PR reviewer. Review ONLY changed files. Be concise (max 600 words).

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
) -> str:
    files_list = ", ".join(changed_files[:15]) or "unknown"

    return f"""QA validator. Be concise (max 200 words).

Tests exit code: {test_exit_code}
Changed files: {files_list}

Test output (failures/summary only):
```
{test_summary}
```

Check: tests ran, failures explained, critical paths covered.

Output:
# Test Validation Report
## Summary (2-3 bullets)
## Coverage Gaps (max 3, or "None")
## Pipeline Verdict
End with exactly: **PASS** or **FAIL**
"""


# Legacy alias used by bedrock_review
def compose_master_prompt(prompts_dir: Path, context: dict) -> str:
    return compose_compact_review_prompt(prompts_dir, context)
