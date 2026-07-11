# Ponteo Project — CI/CD Pipeline

Self-contained **Ponteo Project** repository for the 6-stage PR pipeline on your
personal GitHub + AWS account, then replicated on the client account for production.

```
PR opened
  -> Stage 1: SonarQube quality gate   (blocking)
  -> Stage 2: AI Code Review (Bedrock)  (blocking)
  -> Stage 3: Tests + AI QA (coverage, regression, failures)  (blocking)
  -> Stage 4: Docker build -> Trivy scan -> ECR push (blocking)
  -> Stage 5: Manual approval gate       (blocking)
  -> Stage 6: Update image tag on `argo-manifest` branch (manifest-only)
```

## Stage 4 — Trivy integration

Stage 4 runs in this order:

1. **Docker build** (local — not pushed yet)
2. **Trivy image scan** on the local image (vuln scanner)
3. **Pipeline fails** on HIGH or CRITICAL findings — **image is not pushed to ECR**
4. **Push to Amazon ECR** only after Trivy gate passes

---

## Repository layout

| Path | Purpose |
|------|---------|
| `src/`, `test/` | Node.js 22 microservice (Express) |
| `Dockerfile` | Multi-stage, non-root image |
| `.github/workflows/pr-pipeline.yml` | 6-stage pipeline |
| `.github/actions/` | Sonar, Bedrock, Docker+Trivy composite actions |
| `scripts/`, `prompts/` | Bedrock AI review (token-optimized) |
| `argo-manifest` branch | Manifest-only branch (`argo-manifest/`); Stage 6 updates image tag there |

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
| `ponteo-project` | App + CI (manifests live on `argo-manifest` branch) |

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
BEDROCK_COST_MODE=smart

# Cost modes: smart (default) | economy | full
# legacy: BEDROCK_SKIP_TEST_AI_ON_PASS=true forces economy for Stage 3

# Manifest branch (default: argo-manifest — contains only argo-manifest/ folder):
# MANIFEST_BRANCH=argo-manifest
# GITOPS_MANIFEST_PATH=argo-manifest/deployment.yaml

# Optional — external GitOps repo instead of in-repo manifest branch:
# GITOPS_REPO=YOUR_GITHUB_USER/ponteo-project-gitops
```

---

## Step 8 — GitHub Secrets

```
AWS_ROLE_ARN=arn:aws:iam::YOUR_ACCOUNT_ID:role/github-actions-ponteo-project-ci
SONAR_TOKEN=<token>
SONAR_HOST_URL=https://sonarcloud.io
```

---

## Step 9 — GitHub Environments

Create `staging` and `production` with yourself as required reviewer.

Stage 2 and Stage 3 post **PR comments only** (no merge permissions).

### Bedrock token / cost control (`BEDROCK_COST_MODE`)

| Mode | Stage 2 AI review | Stage 3 AI QA |
|------|-------------------|---------------|
| **`smart`** (default) | Only when `src/`, `test/`, Dockerfile, or `package.json` change | On test **failure**; on pass only for app changes (especially `src/` without `test/`) |
| **`economy`** | Same as smart | Bedrock **only when tests fail** |
| **`full`** | Always (except trivial diffs) | Always when tests pass |

Also skipped automatically: trivial diffs, CI/docs-only PRs (`.github/`, `prompts/`, README).

Set `BEDROCK_SKIP_TEST_AI_ON_PASS=true` to force economy behavior (legacy).

---

## Step 10 — Branch protection on `main`

Merge is blocked until PR validation passes (Stages **1–4** + SonarCloud).
Deploy approval (Stages **5–6**) is **not** required to merge — that gates manifest promotion only.

### Option A — Script (recommended)

```bash
python3 scripts/setup_branch_protection.py
```

Requires a GitHub token with **admin** access to the repo (or `git credential` with same scope).

### Option B — GitHub UI

**Settings → Branches → Edit rule** for `main`:

| Setting | Value |
|---------|--------|
| Require a pull request before merging | Yes |
| Required approving reviews | 0 (solo demo) or 1+ (team/client) |
| Require status checks to pass | Yes |
| Require branches to be up to date | Yes |
| Include administrators | Yes |

**Required status checks** (exact names):

- `Stage 1 - SonarQube Scan`
- `Stage 2 - AI Code Review`
- `Stage 3 - AI-Assisted Tests`
- `Stage 4 - Docker Build + ECR + Trivy`
- `SonarCloud Code Analysis`

Do **not** require Stage 5 or Stage 6 for merge — those are deploy gates.

---

## Step 11 — Run the pipeline

```bash
git checkout -b feature/test-pipeline
# make a small code change
git commit -am "feat: trigger pipeline"
git push -u origin feature/test-pipeline
```

Open a PR to `main` and watch all 6 stages.

After Stage 5 approval, Stage 6 commits the new image tag to the **`argo-manifest`**
branch (manifest-only — no app code on that branch).

### Manifest branch setup (one time)

```bash
# From repo root, create an orphan branch with only argo-manifest/
git checkout --orphan argo-manifest
git rm -rf . 2>/dev/null || true
mkdir -p argo-manifest
# Add deployment.yaml and service.yaml under argo-manifest/
git add argo-manifest/
git commit -m "chore: initialize manifest-only branch"
git push -u origin argo-manifest
git checkout main
```

Edit manifests on `argo-manifest` directly (or via Stage 6 after approval). App PRs
target `main` and do not include manifest files.

---

## Verify Stage 4 (Trivy)

After Stage 4 completes:

- **Artifacts:** `trivy-image-report`
- **Job summary:** Trivy scan details
- **ECR:** `aws ecr list-images --repository-name ponteo/ponteo-project`

If HIGH/CRITICAL vulnerabilities are found, Stage 4 **fails** and the image **is not pushed** to ECR.

---

## Migrate to client production

| Setting | Personal | Client |
|---------|----------|--------|
| `runs-on` | `ubuntu-latest` | `[self-hosted, linux, x64]` |
| GitHub repo | `ponteo-project` | client service repo |
| ECR | `ponteo/ponteo-project` | client ECR path |
| IAM OIDC `sub` | your user/repo | client org/repo |
| GitOps | optional | client GitOps repo |
