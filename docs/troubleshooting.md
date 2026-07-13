---
title: Troubleshooting
description: Common Ponteo pipeline failures and how to fix them
order: 4
---

# Troubleshooting Guide

## Merge blocked — check stuck on "Expected"

**Symptom:** Orange pending check like `Stage 4 - Docker Build + ECR + Trivy — Expected, waiting...` while a similarly named check already passed.

**Cause:** Branch protection requires an **old job name** that no longer matches the workflow.

**Fix:**
1. **Settings → Branches →** edit rule for `main`
2. Remove the old check name
3. Add the exact name from Actions sidebar, e.g. `Stage 4 - Docker build + Trivy scan + push to ECR`
4. Save and refresh the PR

Or run: `python3 scripts/setup_branch_protection.py`

---

## Stage 1 — SonarQube failed

| Error | Fix |
|-------|-----|
| Quality gate failed | Open SonarCloud dashboard; fix coverage, bugs, or smells |
| Authentication failed | Verify `SONAR_TOKEN`, `SONAR_HOST_URL`, `SONAR_PROJECT_KEY`, `SONAR_ORGANIZATION` |
| No coverage | Ensure `npm run test:coverage` produces `coverage/lcov.info` |

---

## Stage 2 — AI Code Review failed

| Error | Fix |
|-------|-----|
| `AccessDeniedException` (Bedrock) | Enable Claude Sonnet 4.5 in Bedrock; add `bedrock:InvokeModel` to IAM role |
| OIDC / assume role failed | Check `AWS_ROLE_ARN` secret and IAM trust policy `sub` for `pull_request` |
| Exit code 141 | Git diff truncation — ensure latest workflow is on the branch |
| AI verdict FAIL | Read PR comment; address security or quality findings |

---

## Stage 3 — AI-Assisted Tests failed

| Error | Fix |
|-------|-----|
| npm test failed | Run `npm test` locally; fix failing tests |
| No verdict file | Check Bedrock connectivity and `scripts/test_validation.py` logs |
| AI FAIL with passing tests | Should auto-downgrade unless critical — check latest `test_validation.py` on branch |

---

## Stage 4 — Docker / Trivy / ECR failed

| Error | Fix |
|-------|-----|
| Docker build failed | Check Dockerfile and build logs |
| Trivy gate failed | Download `trivy-image-report` artifact; update npm dependencies |
| OS CVEs only | Expected with distroless — blocked only on `lang-pkgs` by default |
| ECR push failed | Verify `ECR_REGISTRY`, `ECR_REPOSITORY`, IAM ECR permissions |
| Image not in ECR after "success" | Trivy blocks push — scan must pass first |

---

## Stage 5 — Cannot approve deployment

| Error | Fix |
|-------|-----|
| No "Review deployments" button | Public repo (Free tier) or GitHub Team; add reviewers to `production` environment |
| Stage 5 skipped | PR must target `main` for `production` environment |

---

## Stage 6 — ArgoCD image tag update failed

| Error | Fix |
|-------|-----|
| Manifest branch not found | Create `argo-manifest` branch (see [Quick Start](quick-start.md)) |
| Permission denied on push | Stage 6 needs `contents: write` on `GITHUB_TOKEN` |
| No commit (already up to date) | Image tag unchanged — normal on re-run |

---

## Node.js 20 deprecation warnings

**Symptom:** Yellow annotations: "Node.js 20 is deprecated... forced to run on Node.js 24"

**Impact:** Informational only — pipeline still works.

**Long-term fix:** Upgrade GitHub Actions to v5+ (e.g. `actions/checkout@v5`).

---

## Bedrock cost too high

Set GitHub variable:

```
BEDROCK_COST_MODE=smart
```

| Mode | Behavior |
|------|----------|
| `smart` | Skip AI on docs/CI-only PRs; Stage 3 AI mostly on failures |
| `economy` | Stage 3 Bedrock only when tests fail |
| `full` | Always call Bedrock |

---

## Useful commands

```bash
# List recent ECR images
aws ecr describe-images \
  --repository-name ponteo/ponteo-project \
  --region us-east-1 \
  --query 'sort_by(imageDetails,& imagePushedAt)[-5:].imageTags'

# Local tests
npm ci && npm test

# Apply branch protection
export GITHUB_OWNER=your_github_user
export GITHUB_TOKEN=<your-admin-token>
python3 scripts/setup_branch_protection.py
```

---

Back to: [Documentation index](index.md) | [KT Setup Guide](KT-SETUP-GUIDE.md)
