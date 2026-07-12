---
title: Quick Start
description: Get the Ponteo CI/CD pipeline running in under an hour
order: 2
---

# Quick Start

Follow these steps in order. For full detail, see the [KT Setup Guide](KT-SETUP-GUIDE.md).

## 1. Local check

```bash
cd Ponteo-project
npm ci
npm test
```

## 2. Push to GitHub

```bash
git remote add origin https://github.com/YOUR_USER/ponteo-project.git
git push -u origin main
```

Use a **public** repo if you need Stage 5 manual approval on GitHub Free.

## 3. AWS (one-time)

| Task | Action |
|------|--------|
| Bedrock | Enable Claude Sonnet 4.5 in `us-east-1` |
| OIDC | Add provider `https://token.actions.githubusercontent.com` |
| IAM role | Web identity role for `repo:YOUR_USER/ponteo-project:*` |
| Permissions | ECR push + `bedrock:InvokeModel` |
| ECR | `aws ecr create-repository --repository-name ponteo/ponteo-project --region us-east-1` |

## 4. SonarCloud (one-time)

1. Import repo at [sonarcloud.io](https://sonarcloud.io)
2. Save project key, organization key, and token

## 5. GitHub Variables

```
AWS_REGION=us-east-1
ECR_REGISTRY=ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
ECR_REPOSITORY=ponteo/ponteo-project
SERVICE_NAME=ponteo-project
SONAR_PROJECT_KEY=<your-key>
SONAR_ORGANIZATION=<your-org>
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
BEDROCK_COST_MODE=smart
```

## 6. GitHub Secrets

```
AWS_ROLE_ARN=arn:aws:iam::ACCOUNT:role/github-actions-ponteo-project-ci
SONAR_TOKEN=<token>
SONAR_HOST_URL=https://sonarcloud.io
```

## 7. GitHub Environments

Create `production` and `staging` with yourself as required reviewer.

## 8. Branch protection on `main`

Required status checks (exact names):

- `Stage 1 - SonarQube Scan`
- `Stage 2 - AI Code Review`
- `Stage 3 - AI-Assisted Tests`
- `Stage 4 - Docker build + Trivy scan + push to ECR`
- `SonarCloud Code Analysis`

Or run: `python3 scripts/setup_branch_protection.py`

## 9. Create `argo-manifest` branch

```bash
git checkout --orphan argo-manifest
git rm -rf . 2>/dev/null || true
mkdir -p argo-manifest
# add deployment.yaml + service.yaml
git add argo-manifest/
git commit -m "chore: initialize manifest-only branch"
git push -u origin argo-manifest
git checkout main
```

## 10. First pipeline test

```bash
git checkout -b feature/first-test
git commit --allow-empty -m "chore: trigger pipeline"
git push -u origin feature/first-test
```

Open PR → wait for Stages 1–4 → approve Stage 5 → verify Stage 6 updates `argo-manifest`.

## Success checklist

- [ ] Stages 1–4 green on PR
- [ ] AI comments on PR (Stage 2 + 3)
- [ ] Image in ECR after Stage 4
- [ ] Stage 5 approved
- [ ] `argo-manifest/deployment.yaml` image tag updated
- [ ] PR merged to `main`

---

Next: [Pipeline Stages](pipeline-stages.md) | [Troubleshooting](troubleshooting.md)
