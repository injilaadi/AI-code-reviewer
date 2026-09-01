"""Core review job processing: diff -> LLM findings -> persist -> post to GitHub.

Uses SELECT ... FOR UPDATE SKIP LOCKED so multiple worker replicas can poll
the same jobs table concurrently without double-processing a row.
"""
import os
import traceback

from app.db.session import SessionLocal
from app.db.models import ReviewRun, Finding
from app.llm.client import review_diff
from app.receiver.github_client import GitHubClient


def process_pending_job() -> bool:
    """Pick up one pending review_run, process it end-to-end.
    Returns True if a job was found and processed (regardless of outcome),
    False if there was nothing to do."""
    db = SessionLocal()
    try:
        review_run = (
            db.query(ReviewRun)
            .filter_by(status="pending")
            .order_by(ReviewRun.created_at.asc())
            .with_for_update(skip_locked=True)
            .first()
        )
        if review_run is None:
            return False

        review_run.status = "running"
        db.commit()

        try:
            _run_review(db, review_run)
            review_run.status = "done"
        except Exception as exc:  # noqa: BLE001 - a bad review shouldn't crash the worker
            review_run.status = "failed"
            review_run.error = f"{exc}\n{traceback.format_exc()}"
        finally:
            from sqlalchemy import func
            review_run.completed_at = func.now()
            db.commit()

        return True
    finally:
        db.close()


def _run_review(db, review_run: ReviewRun) -> None:
    pull_request = review_run.pull_request
    repo_full_name = pull_request.repo.full_name
    owner, repo_name = repo_full_name.split("/", 1)

    github_token = os.environ["GITHUB_TOKEN"]
    github = GitHubClient(github_token)

    diff = github.get_pr_diff(owner, repo_name, pull_request.number)
    result = review_diff(diff)

    review_run.prompt_tokens = result.prompt_tokens
    review_run.completion_tokens = result.completion_tokens

    for f in result.findings:
        db.add(Finding(
            review_run_id=review_run.id,
            file=f.file,
            line=f.line,
            severity=f.severity,
            comment=f.comment,
        ))
    db.commit()

    for f in result.findings:
        try:
            github.post_review_comment(
                owner, repo_name, pull_request.number,
                commit_id=pull_request.head_sha,
                path=f.file, line=f.line,
                body=f"**[{f.severity}]** {f.comment}",
            )
        except Exception:
            # A single bad comment (e.g. line not part of the diff) shouldn't
            # abort the rest of the review -- log and keep going.
            traceback.print_exc()
