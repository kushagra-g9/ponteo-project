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
4. **Pipeline fails** on HIGH or CRITICAL findings

---

## Repository layout

| Path | Purpose |
|------|---------|
| `src/`, `test/` | Node.js 22 microservice (Express) |
| `Dockerfile` | Multi-stage, non-root image |
| `.github/workflows/pr-pipeline.yml` | 6-stage pipeline |
| `.github/actions/` | Sonar, Bedrock, Docker+Trivy composite actions |
| `scripts/`, `prompts/` | Bedrock AI review (token-optimized) |
| `argo-manifest/` | Deployment + Service for GitOps repo (Stage 6 updates image tag only) |

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
| `ponteo-project-gitops` | Copy `argo-manifest/` folder for Stage 6 |

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

AWS Console -> Bedrock -> Model catalog -> **Claude Sonnet 4.5** in `us-east-1`.
Submit the Anthropic use case form (first time only), then test in the playground.
The pipeline invokes it via the US cross-region inference profile
`us.anthropic.claude-sonnet-4-5-20250929-v1:0`.

---

## Step 4 — AWS OIDC + IAM role (AWS Console)

Configure IAM manually in the AWS Console (no policy files in this repo).

1. **OIDC identity provider** (IAM → Identity providers → Add provider)
   - Provider URL: `https://token.actions.githubusercontent.com`
   - Audience: `sts.amazonaws.com`

2. **IAM role** (IAM → Roles → Create role → Web identity)
   - Identity provider: `token.actions.githubusercontent.com`
   - Audience: `sts.amazonaws.com`
   - Trust condition (example `sub` values for repo `kushagra-g9/ponteo-project`):
     - `repo:kushagra-g9/ponteo-project:ref:refs/heads/main`
     - `repo:kushagra-g9/ponteo-project:ref:refs/heads/staging`
     - `repo:kushagra-g9/ponteo-project:ref:refs/heads/develop`
     - `repo:kushagra-g9/ponteo-project:pull_request`

3. **Permissions policy** (attach inline or managed policy on that role)
   - **ECR:** `ecr:GetAuthorizationToken` (resource `*`)
   - **ECR repo:** push/pull on `arn:aws:ecr:REGION:ACCOUNT_ID:repository/ponteo/ponteo-project`
   - **Bedrock:** `bedrock:InvokeModel` on the Claude Sonnet 4.5 foundation model (all US regions) and the `us.` inference profile in your account

4. Copy the role ARN for GitHub secret `AWS_ROLE_ARN` (Step 8).

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
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
BEDROCK_SKIP_TEST_AI_ON_PASS=true

# Optional Stage 6:
# GITOPS_REPO=YOUR_GITHUB_USER/ponteo-project-gitops
# GITOPS_MANIFEST_PATH=argo-manifest/deployment.yaml
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

- **Artifacts:** `trivy-image-report`
- **Job summary:** Trivy scan details
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
