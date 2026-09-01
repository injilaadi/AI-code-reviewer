"""FastAPI webhook receiver.

Verifies the signature, upserts the repo/PR, and enqueues a review job
(a review_runs row with status='pending') -- it does NOT call the LLM or
GitHub review APIs itself. That happens in the worker (app/worker/review.py),
decoupled via the database so the receiver stays fast and GitHub's webhook
timeout is never a concern.
"""
import os
from fastapi import FastAPI, Request, HTTPException

from app.receiver.webhook_verify import verify_signature
from app.db.session import SessionLocal, init_db
from app.db.models import Repo, PullRequest, ReviewRun

app = FastAPI(title="AI Code Reviewer - Webhook Receiver")

WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/webhook")
async def handle_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_signature(body, signature, WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="invalid signature")

    event = request.headers.get("X-GitHub-Event", "")
    payload = await request.json()

    if event == "pull_request" and payload.get("action") in ("opened", "synchronize"):
        pr = payload["pull_request"]
        repo_full_name = payload["repository"]["full_name"]

        db = SessionLocal()
        try:
            repo = db.query(Repo).filter_by(full_name=repo_full_name).one_or_none()
            if repo is None:
                repo = Repo(full_name=repo_full_name)
                db.add(repo)
                db.flush()  # assigns repo.id without committing yet

            # Upsert by (repo_id, number) so re-pushes to the same PR update
            # head_sha instead of creating duplicate PullRequest rows.
            pull_request = (
                db.query(PullRequest)
                .filter_by(repo_id=repo.id, number=pr["number"])
                .one_or_none()
            )
            if pull_request is None:
                pull_request = PullRequest(repo_id=repo.id, number=pr["number"])
                db.add(pull_request)
            pull_request.title = pr.get("title", "")
            pull_request.head_sha = pr["head"]["sha"]
            db.flush()

            review_run = ReviewRun(pull_request_id=pull_request.id, status="pending")
            db.add(review_run)
            db.commit()
            print(f"Queued review_run {review_run.id} for PR #{pr['number']} in {repo_full_name}")
        finally:
            db.close()

    return {"status": "accepted"}
