# AI Code Reviewer

Automated PR review bot: GitHub webhook -> job queue -> LLM review -> inline PR comments,
with results persisted to PostgreSQL. Containerized and deployed to Kubernetes with
GitHub Actions CI/CD.

## Architecture

    GitHub PR event -> receiver (FastAPI) -> jobs table (Postgres)
                                                    |
                                              worker (poller)
                                                    |
                                        LLM API (diff -> findings)
                                                    |
                                  GitHub API (inline review comments)
                                                    |
                                          Postgres (review_runs, findings)

## Local development

    cp .env.example .env   # fill in secrets
    docker compose up --build

## Build order (see project plan)

1. Webhook receiver + GitHub API plumbing (no LLM)
2. LLM review logic, structured findings, inline comments
3. PostgreSQL persistence
4. Queue/worker split
5. Docker
6. Kubernetes (local: kind/minikube)
7. GitHub Actions CI/CD
8. (optional) AWS: EKS + RDS + ECR
