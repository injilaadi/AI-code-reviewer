# AI Code Reviewer

Automated PR review bot: GitHub webhook -> job queue (Postgres) -> worker ->
LLM review -> inline PR comments, with results persisted to PostgreSQL.
Containerized and (next) deployed to Kubernetes with GitHub Actions CI/CD.

## Status

Working end-to-end against real GitHub PRs: webhook receiver verifies
signatures, queues a job, a worker picks it up, calls the LLM (OpenAI or
Gemini), and posts real inline review comments back on the PR. Findings and
per-comment post status are persisted to Postgres.

## Architecture

    GitHub PR event -> receiver (FastAPI) -> review_runs row, status=pending
                                                    |
                                              worker (poller)
                                                    |
                                        LLM API (diff -> findings)
                                                    |
                                  GitHub API (inline review comments)
                                                    |
                        Postgres (review_runs, findings; per-finding posted/post_error)

review_runs.status: pending -> running -> done | partial | failed
  - done:    review succeeded, every finding posted
  - partial: review succeeded, but one or more comments failed to post
             (see review_runs.error and findings.post_error)
  - failed:  the review itself failed (diff fetch or LLM call)

## Local development

    cp .env.example .env   # fill in GITHUB_TOKEN, GITHUB_WEBHOOK_SECRET, LLM_API_KEY
    docker compose up --build

Tunnel a public URL to your receiver for GitHub to reach (e.g. `ngrok http 8000`),
register it as a webhook on a test repo (content type application/json, secret
matching GITHUB_WEBHOOK_SECRET, "Pull requests" event only), then open a PR.

Useful checks while developing:

    docker compose logs worker      # now logs every stage, not silent
    docker compose exec db psql -U postgres -d codereview \
      -c "select id, status, error from review_runs order by id desc limit 5;"

## Known simplifications (by design, for project scope)

- Schema managed via `Base.metadata.create_all()`, not Alembic migrations --
  fine for a from-scratch dev DB, but adding a column to an existing table
  needs a manual ALTER TABLE or `docker compose down -v` to reset.
- Job queue is DB polling (5s interval), not a push-based queue like
  Redis/SQS -- simple and sufficient at this scale, swappable later.
- GitHub auth is a personal access token, not a GitHub App -- simpler for a
  single-repo demo; a real multi-repo deployment would use a GitHub App with
  installation tokens instead.

## Build order

1. Webhook receiver + GitHub API plumbing (no LLM)               -- done
2. LLM review logic, structured findings, inline comments        -- done
3. PostgreSQL persistence                                        -- done
4. Queue/worker split                                            -- done
5. Docker (compose)                                               -- done
6. Kubernetes (local: kind/minikube)                              -- next
7. GitHub Actions CI/CD (build + deploy, test job already exists) -- next
8. (optional) AWS: EKS + RDS + ECR
