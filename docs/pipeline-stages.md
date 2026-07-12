---
title: Pipeline Stages
description: Reference for all six PR pipeline stages
order: 3
---

# Pipeline Stages Reference

Workflow file: `.github/workflows/pr-pipeline.yml`

## Overview

| Stage | Job name | Blocks merge? | Blocks deploy? |
|-------|----------|---------------|----------------|
| 1 | Stage 1 - SonarQube Scan | Yes | — |
| 2 | Stage 2 - AI Code Review | Yes | — |
| 3 | Stage 3 - AI-Assisted Tests | Yes | — |
| 4 | Stage 4 - Docker build + Trivy scan + push to ECR | Yes | — |
| 5 | Stage 5 - Manual approval needed to deploy | No | Yes |
| 6 | Stage 6 - ArgoCD image tag update | No | Yes |

Stages run **sequentially** — each stage waits for the previous one via `needs:`.

---

## Stage 1 — SonarQube Scan

**Purpose:** Code quality gate with test coverage.

**Steps:**
1. Checkout code
2. Install Node.js dependencies
3. Run tests with coverage
4. SonarCloud scan + quality gate wait

**Artifacts:** `sonar-report`, `coverage-report`

**Fails when:** Quality gate fails, tests fail, Sonar token invalid.

---

## Stage 2 — AI Code Review

**Purpose:** AWS Bedrock reviews the PR diff for security and quality issues.

**Steps:**
1. Build git diff context
2. Call Bedrock with `prompts/code_review.md`
3. Post report as PR comment
4. Block if AI verdict is FAIL

**Cost control:** `BEDROCK_COST_MODE=smart` skips docs-only and CI-only PRs.

**Artifacts:** `ai-review-report`

---

## Stage 3 — AI-Assisted Tests

**Purpose:** Run unit tests; Bedrock validates test coverage vs code changes.

**Hard gate:** `npm test` must pass.

**AI behavior:**
- Tests **fail** → AI summary + block
- Tests **pass** → AI is advisory; non-critical AI FAIL is downgraded to PASS

**Artifacts:** `test-validation-report`, test log

---

## Stage 4 — Docker build + Trivy scan + push to ECR

**Purpose:** Build container, scan for vulnerabilities, push only if safe.

**Order (critical):**

```
Build locally (no push)
    ↓
Trivy vulnerability scan
    ↓
Trivy gate (lang-pkgs HIGH/CRITICAL)
    ↓
Push to ECR (only if gate passes)
```

**Image tag:** `pr-{PR_NUMBER}-{12_CHAR_SHA}`

**Trivy policy:** Default `TRIVY_BLOCK_CLASS=lang-pkgs` (app dependencies). OS CVEs on distroless base are informational.

**Artifacts:** `trivy-image-report`

---

## Stage 5 — Manual approval needed to deploy

**Purpose:** Human gate before promoting image to GitOps manifest.

**Environment:** `production` (PRs to `main`) or `staging` (other target branches)

**How to approve:**
1. Open the Actions run
2. Click **Stage 5 - Manual approval needed to deploy**
3. **Review deployments** → Approve `production`

---

## Stage 6 — ArgoCD image tag update

**Purpose:** Update Kubernetes deployment image on `argo-manifest` branch.

**What changes:** Only the `image:` field in `argo-manifest/deployment.yaml`

**Requires:** Stage 4 image URI + Stage 5 approval

**Commit author:** `github-actions[bot]`

---

## Merge vs deploy

| Action | Required checks |
|--------|-----------------|
| Merge PR | Stages 1–4 + SonarCloud |
| Deploy manifest update | Stages 1–6 (including Stage 5 approval) |

---

See also: [Troubleshooting](troubleshooting.md) | [KT Setup Guide](KT-SETUP-GUIDE.md)
