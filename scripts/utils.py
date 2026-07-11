"""Shared utilities for CI/CD Bedrock review scripts."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


# Token budget defaults (override via GitHub vars / workflow env)
DEFAULT_MAX_DIFF_CHARS = 8_000
DEFAULT_MAX_TEST_LOG_CHARS = 2_000
DEFAULT_MAX_PR_BODY_CHARS = 300
DEFAULT_MAX_SONAR_CHARS = 600

CODE_PATH_PREFIXES = ("src/", "test/")
CODE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
INFRA_FILENAMES = {"Dockerfile", "package.json", "package-lock.json", "sonar-project.properties"}


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def get_env(name: str, default: str = "") -> str:
    value = os.environ.get(name, default)
    if not value:
        raise ValueError(f"Required environment variable not set: {name}")
    return value


def read_text(path: Path, max_bytes: int = 64_000) -> str:
    if not path.exists():
        return ""
    data = path.read_bytes()[:max_bytes]
    return data.decode("utf-8", errors="replace")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_changed_files(context_dir: Path) -> list[str]:
    changed_path = context_dir / "changed-files.txt"
    if not changed_path.exists():
        return []
    return [
        line.strip()
        for line in changed_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def get_cost_mode() -> str:
    """smart (default): Bedrock only when useful. economy: minimal. full: always call."""
    legacy_skip = os.environ.get("BEDROCK_SKIP_TEST_AI_ON_PASS", "").strip().lower()
    if legacy_skip in {"1", "true", "yes", "on"}:
        return "economy"
    mode = os.environ.get("BEDROCK_COST_MODE", "smart").strip().lower()
    if mode in {"smart", "economy", "full"}:
        return mode
    return "smart"


def token_limits_for_mode() -> dict[str, int]:
    mode = get_cost_mode()
    if mode == "full":
        return {"diff": 12_000, "review_out": 2048, "test_out": 1024, "test_log": 3_000}
    if mode == "economy":
        return {"diff": 6_000, "review_out": 768, "test_out": 384, "test_log": 1_500}
    return {"diff": 8_000, "review_out": 1024, "test_out": 512, "test_log": 2_000}


def is_application_change(changed_files: list[str]) -> bool:
    for path in changed_files:
        normalized = path.replace("\\", "/")
        if any(normalized.startswith(prefix) for prefix in CODE_PATH_PREFIXES):
            return True
        if Path(normalized).suffix.lower() in CODE_EXTENSIONS:
            return True
        if Path(normalized).name in INFRA_FILENAMES:
            return True
    return False


def has_src_without_test_changes(changed_files: list[str]) -> bool:
    src_changed = any(f.replace("\\", "/").startswith("src/") for f in changed_files)
    test_changed = any(f.replace("\\", "/").startswith("test/") for f in changed_files)
    return src_changed and not test_changed


def should_run_review_bedrock(changed_files: list[str], git_diff: str) -> tuple[bool, str]:
    if is_trivial_diff(git_diff, changed_files):
        return False, "trivial diff"
    mode = get_cost_mode()
    if mode == "full":
        return True, "full cost mode"
    if not is_application_change(changed_files):
        return False, "no application code changes (CI/docs only)"
    return True, f"{mode} mode — application files changed"


def should_run_test_bedrock(
    changed_files: list[str],
    *,
    tests_failed: bool,
) -> tuple[bool, str]:
    if tests_failed:
        return True, "tests failed — summarize failures"
    mode = get_cost_mode()
    if mode == "economy":
        return False, "economy mode — skip AI QA when tests pass"
    if mode == "full":
        return True, "full cost mode"
    if not is_application_change(changed_files):
        return False, "no application code changes"
    if has_src_without_test_changes(changed_files):
        return True, "src changed without test updates — check coverage gaps"
    if any(f.replace("\\", "/").startswith("test/") for f in changed_files):
        return True, "test files changed — validate coverage"
    if any(f.replace("\\", "/").startswith("src/") for f in changed_files):
        return True, "src changed — lightweight QA check"
    return False, "no QA trigger for changed files"


def write_skip_report(title: str, reason: str) -> str:
    return (
        f"# {title}\n\n"
        f"**Bedrock skipped (token savings):** {reason}\n\n"
        "## Pipeline Verdict\n\n**PASS**\n"
    )


def truncate_for_model(text: str, max_chars: int | None = None) -> str:
    limits = token_limits_for_mode()
    limit = max_chars or env_int("BEDROCK_MAX_DIFF_CHARS", limits["diff"])
    if len(text) <= limit:
        return text
    return text[: limit - 120] + "\n...[truncated to save tokens]...\n"


def summarize_sonar_report(sonar_text: str) -> str:
    if not sonar_text.strip():
        return "SonarQube: passed (no report file)."

    lines = [ln.strip() for ln in sonar_text.splitlines() if ln.strip()]
    keep = lines[:8]
    return "SonarQube summary:\n" + "\n".join(keep)


def summarize_test_output(test_log: str, max_chars: int | None = None) -> str:
    limit = max_chars or env_int("BEDROCK_MAX_TEST_LOG_CHARS", DEFAULT_MAX_TEST_LOG_CHARS)
    if not test_log.strip():
        return "No test output."

    # Prefer failures and summary lines
    interesting: list[str] = []
    for line in test_log.splitlines():
        lower = line.lower()
        if any(k in lower for k in ("fail", "error", "passed", "tests", "suite", "✓", "✗", "×")):
            interesting.append(line)

    compact = "\n".join(interesting) if interesting else test_log
    if len(compact) > limit:
        compact = compact[-limit:]
    return compact


def select_review_focus(changed_files: list[str]) -> list[str]:
    """Return minimal prompt keys based on what changed."""
    focus = ["code_review", "security_review"]
    extensions = {Path(f).suffix.lower() for f in changed_files}

    if extensions & {".ts", ".js", ".tsx", ".jsx"}:
        focus.append("performance_review")

    focus.append("regression_analysis")
    return list(dict.fromkeys(focus))


def is_trivial_diff(git_diff: str, changed_files: list[str]) -> bool:
    if not changed_files:
        return True
    if len(git_diff.strip()) < 10:
        return True
    # Single-file comment/whitespace-only changes
    if len(changed_files) == 1 and len(git_diff) < 200:
        added = sum(1 for ln in git_diff.splitlines() if ln.startswith("+") and not ln.startswith("+++"))
        removed = sum(1 for ln in git_diff.splitlines() if ln.startswith("-") and not ln.startswith("---"))
        if added + removed <= 3:
            return True
    return False


def load_context(context_dir: Path) -> dict[str, Any]:
    metadata = read_json(context_dir / "pr-metadata.json")

    body = metadata.get("body", "") or ""
    max_body = env_int("BEDROCK_MAX_PR_BODY_CHARS", DEFAULT_MAX_PR_BODY_CHARS)
    if len(body) > max_body:
        metadata = {**metadata, "body": body[:max_body] + "..."}

    max_diff = env_int("BEDROCK_MAX_DIFF_CHARS", DEFAULT_MAX_DIFF_CHARS)
    git_diff = read_text(context_dir / "git-diff.patch", max_bytes=max_diff + 500)
    git_diff = truncate_for_model(git_diff, max_diff)

    changed_files = load_changed_files(context_dir)

    sonar_report = ""
    for candidate in context_dir.glob("*sonar*"):
        sonar_report += read_text(candidate, max_bytes=DEFAULT_MAX_SONAR_CHARS)

    return {
        "metadata": metadata,
        "git_diff": git_diff,
        "changed_files": changed_files,
        "sonar_report": summarize_sonar_report(sonar_report),
        "trivy_report": "",
    }


def extract_score(markdown: str, label: str) -> str:
    pattern = rf"{re.escape(label)}\s*[:|]\s*([0-9]+(?:\.[0-9]+)?/10|[0-9]+(?:\.[0-9]+)?%|Low|Medium|High|Critical|N/A)"
    match = re.search(pattern, markdown, re.IGNORECASE)
    return match.group(1) if match else "N/A"


def build_pr_comment_header(sections: dict[str, str]) -> str:
    overall = sections.get("overall_score", "N/A")
    security = sections.get("security", "N/A")
    performance = sections.get("performance", "N/A")
    maintainability = sections.get("maintainability", "N/A")
    regression = sections.get("regression_risk", "N/A")

    return f"""# AI Review Summary

| Metric | Score |
|--------|-------|
| **Overall Score** | {overall} |
| **Security** | {security} |
| **Performance** | {performance} |
| **Maintainability** | {maintainability} |
| **Regression Risk** | {regression} |

---
"""
