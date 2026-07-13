---
title: Ponteo CI/CD Documentation
description: Setup, pipeline reference, and troubleshooting for the Ponteo Project
order: 1
---

# Ponteo CI/CD Documentation

Welcome to the Ponteo Project documentation. Use this hub to set up the platform, run the pipeline, and troubleshoot common issues.

## Who is this for?

- **Developers** — day-to-day PR workflow and local testing
- **DevOps / Platform engineers** — AWS, GitHub, SonarCloud, ECR, GitOps setup
- **Reviewers** — deploy approval (Stage 5) and manifest promotion (Stage 6)

## Documentation map

| Document | Description |
|----------|-------------|
| [Quick Start](quick-start.md) | Minimum steps to go from zero to first green pipeline |
| [KT Setup Guide](KT-SETUP-GUIDE.md) | **Full knowledge transfer** — complete setup, architecture, handover checklist |
| [Pipeline Stages](pipeline-stages.md) | What each of the 6 stages does and when it blocks |
| [Troubleshooting](troubleshooting.md) | Common failures and fixes |

## Pipeline at a glance

```
PR opened
  → Stage 1: SonarQube Scan
  → Stage 2: AI Code Review (Bedrock)
  → Stage 3: AI-Assisted Tests
  → Stage 4: Docker build + Trivy scan + push to ECR
  → Stage 5: Manual approval needed to deploy
  → Stage 6: ArgoCD image tag update
```

**Merge to `main`** requires Stages 1–4 + SonarCloud.  
**Deploy promotion** requires Stage 5 approval + Stage 6 manifest update.

## Quick links

| Resource | Link |
|----------|------|
| Repository | `https://github.com/YOUR_ORG/ponteo-project` |
| GitHub Actions | `https://github.com/YOUR_ORG/ponteo-project/actions` |
| Workflow | `.github/workflows/pr-pipeline.yml` |
| Application README | [../README.md](../README.md) |

## Repository branches

| Branch | Purpose |
|--------|---------|
| `main` | Application code + CI workflows |
| `feature/*` | Developer work — open PRs here |
| `argo-manifest` | Kubernetes manifests only — updated by Stage 6 |

---

*Start with [Quick Start](quick-start.md) for a fast setup, or [KT Setup Guide](KT-SETUP-GUIDE.md) for full handover documentation.*
