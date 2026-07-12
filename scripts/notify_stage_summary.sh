#!/usr/bin/env bash
# Build report summary lines for Google Chat (stdout). Never fails the pipeline.
set -uo pipefail

TYPE="${1:?usage: notify_stage_summary.sh sonar|trivy|ai-review|test-validation}"
shift || true

case "${TYPE}" in
  sonar)
    python3 scripts/report_summary.py --type sonar \
      --sonar-host "${SONAR_HOST_URL:-}" \
      --sonar-project-key "${SONAR_PROJECT_KEY:-}" \
      --sonar-organization "${SONAR_ORGANIZATION:-}" \
      --coverage-dir "${COVERAGE_DIR:-coverage}" \
      2>/dev/null || echo "<b>SonarQube Report</b>"
    ;;
  trivy)
    python3 scripts/report_summary.py --type trivy \
      --trivy-report "${TRIVY_REPORT:-trivy-image-results.json}" \
      --image "${IMAGE_URI:-unknown}" \
      --severities "${TRIVY_SEVERITIES:-HIGH,CRITICAL}" \
      --block-class "${TRIVY_BLOCK_CLASS:-lang-pkgs}" \
      2>/dev/null || echo "<b>Trivy Scan Report</b>"
    ;;
  ai-review)
    python3 scripts/report_summary.py --type ai-review \
      --report-path "${REPORT_PATH:-artifacts/ai-review.md}" \
      2>/dev/null || echo "<b>AI Code Review Summary</b>"
    ;;
  test-validation)
    python3 scripts/report_summary.py --type test-validation \
      --report-path "${REPORT_PATH:-artifacts/test-validation.md}" \
      2>/dev/null || echo "<b>Test Validation Report</b>"
    ;;
  *)
    echo "Unknown summary type: ${TYPE}" >&2
    exit 1
    ;;
esac
