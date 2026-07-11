# Ponteo Project — CI/CD Pipeline

Self-contained **Ponteo Project** repository for the 6-stage PR pipeline on your
personal GitHub + AWS account, then replicated on the client account for production.

```
PR opened
  -> Stage 1: SonarQube quality gate   (blocking)
  -> Stage 2: AI Code Review (Bedrock)  (blocking)
  -> Stage 3: Tests + AI validation     (blocking)
  -> Stage 4: Docker build -> ECR push -> Trivy scan (blocking)
  -> Stage 5: Manual approval gate       (blocking)
  -> Stage 6: GitOps manifest update    (optional)
```

## Stage 4 — Trivy integration

Stage 4 runs in this order:

1. **Docker build**
2. **Push to Amazon ECR**
3. **Trivy image scan** on the pushed image (vuln + secret scanners)
4. **SBOM** generation (CycloneDX)
5. **SARIF** upload to GitHub Security tab
6. **Pipeline fails** on HIGH or CRITICAL findings

---

## Repository layout

| Path | Purpose |
|------|---------|
| `src/`, `test/` | Node.js 22 microservice (Express) |
| `Dockerfile` | Multi-stage, non-root image |
| `.github/workflows/pr-pipeline.yml` | 6-stage pipeline |
| `.github/actions/` | Sonar, Bedrock, Docker+Trivy composite actions |
| `scripts/`, `prompts/` | Bedrock AI review (token-optimized) |
| `infra/iam/` | AWS OIDC trust + IAM policy |
| `gitops/` | Sample manifest for `ponteo-project-gitops` repo |

---

## Prerequisites

- Personal GitHub account
- Personal AWS account (Bedrock + ECR)
- AWS CLI configured locally
- Node.js 22 + npm

---

## Step 1 — Prepare locally

```bash
cd Ponteo-project
npm install
npm test
git add package-lock.json
git commit -m "chore: add lock file"
```

---

## Step 2 — Create GitHub repositories

| Repo | Contents |
|------|----------|
| `ponteo-project` | Push this folder |
| `ponteo-project-gitops` | (optional) Copy `gitops/` for Stage 6 |

```bash
git init
git add .
git commit -m "chore: initial Ponteo Project CI/CD"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USER/ponteo-project.git
git push -u origin main
```

Make the repo **public** if you need Stage 5 approval on a free GitHub account.

---

## Step 3 — Enable Amazon Bedrock

AWS Console -> Bedrock -> Model access -> enable **Claude Sonnet 4** in `us-east-1`.

---

## Step 4 — AWS OIDC + IAM role

1. Create OIDC provider: `token.actions.githubusercontent.com` (audience: `sts.amazonaws.com`)
2. Edit `infra/iam/github-oidc-trust-policy.json` — replace `YOUR_ACCOUNT_ID`, `YOUR_GITHUB_USER`
3. Edit `infra/iam/github-actions-policy.json` — replace `YOUR_ACCOUNT_ID`, `REGION`

```bash
aws iam create-role \
  --role-name github-actions-ponteo-project-ci \
  --assume-role-policy-document file://infra/iam/github-oidc-trust-policy.json

aws iam put-role-policy \
  --role-name github-actions-ponteo-project-ci \
  --policy-name ponteo-project-ci \
  --policy-document file://infra/iam/github-actions-policy.json
```

---

## Step 5 — Create ECR repository

```bash
aws ecr create-repository \
  --repository-name ponteo/ponteo-project \
  --region us-east-1
```

---

## Step 6 — SonarCloud

1. https://sonarcloud.io — import `ponteo-project`
2. Note project key and organization key
3. Generate token

---

## Step 7 — GitHub Variables

```
AWS_REGION=us-east-1
ECR_REGISTRY=YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
ECR_REPOSITORY=ponteo/ponteo-project
SERVICE_NAME=ponteo-project
SONAR_PROJECT_KEY=your-sonar-project-key
SONAR_ORGANIZATION=your-sonar-org-key
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514-v1:0
BEDROCK_SKIP_TEST_AI_ON_PASS=true

# Optional Stage 6:
# GITOPS_REPO=YOUR_GITHUB_USER/ponteo-project-gitops
# GITOPS_MANIFEST_PATH=apps/ponteo-project/deployment.yaml
```

---

## Step 8 — GitHub Secrets

```
AWS_ROLE_ARN=arn:aws:iam::YOUR_ACCOUNT_ID:role/github-actions-ponteo-project-ci
SONAR_TOKEN=<token>
SONAR_HOST_URL=https://sonarcloud.io
GITOPS_PAT=<only if Stage 6 enabled>
```

---

## Step 9 — GitHub Environments

Create `staging` and `production` with yourself as required reviewer.

---

## Step 10 — Run the pipeline

```bash
git checkout -b feature/test-pipeline
# make a small code change
git commit -am "feat: trigger pipeline"
git push -u origin feature/test-pipeline
```

Open a PR to `main` and watch all 6 stages.

---

## Verify Stage 4 (Trivy)

After Stage 4 completes:

- **Artifacts:** `trivy-image-report`, `sbom-cyclonedx`
- **Job summary:** Trivy scan details
- **GitHub Security:** SARIF from Trivy (if repo supports it)
- **ECR:** `aws ecr list-images --repository-name ponteo/ponteo-project`

If HIGH/CRITICAL vulnerabilities are found, Stage 4 **fails** (image remains in ECR; do not promote to production).

---

## Migrate to client production

| Setting | Personal | Client |
|---------|----------|--------|
| `runs-on` | `ubuntu-latest` | `[self-hosted, linux, x64]` |
| GitHub repo | `ponteo-project` | client service repo |
| ECR | `ponteo/ponteo-project` | client ECR path |
| IAM OIDC `sub` | your user/repo | client org/repo |
| GitOps | optional | client GitOps repo |
