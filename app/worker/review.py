"""Core review job processing: diff -> LLM findings -> persist -> post to GitHub.

Uses SELECT ... FOR UPDATE SKIP LOCKED so multiple worker replicas can poll
the same jobs table concurrently without double-processing a row.

Logs every stage at INFO so `docker compose logs worker` shows real activity
without needing to query the database to see what happened -- this file used
to be silent end-to-end, which made a real GitHub-permissions failure look
identical to "nothing happening" from the logs alone.
"""
import logging
import os
import traceback

from sqlalchemy import func

from app.db.session import SessionLocal
from app.db.models import ReviewRun, Finding
from app.llm.client import review_diff
from app.receiver.github_client import GitHubClient

logger = logging.getLogger("worker.review")


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

        logger.info("Claimed review_run %s (PR #%s)", review_run.id,
                    review_run.pull_request.number)
        review_run.status = "running"
        db.commit()

        try:
            _run_review(db, review_run)
        except Exception as exc:  # noqa: BLE001 - a bad review shouldn't crash the worker
            logger.exception("review_run %s failed", review_run.id)
            review_run.status = "failed"
            review_run.error = f"{exc}\n{traceback.format_exc()}"
        finally:
            review_run.completed_at = func.now()
            db.commit()

        logger.info("review_run %s finished with status=%s", review_run.id, review_run.status)
        return True
    finally:
        db.close()


def _run_review(db, review_run: ReviewRun) -> None:
    pull_request = review_run.pull_request
    repo_full_name = pull_request.repo.full_name
    owner, repo_name = repo_full_name.split("/", 1)

    github_token = os.environ["GITHUB_TOKEN"]
    github = GitHubClient(github_token)

    logger.info("Fetching diff for %s#%s", repo_full_name, pull_request.number)
    diff = github.get_pr_diff(owner, repo_name, pull_request.number)
    logger.info("Diff is %d chars, calling LLM", len(diff))

    result = review_diff(diff)
    logger.info("LLM returned %d finding(s) (prompt_tokens=%s, completion_tokens=%s)",
                len(result.findings), result.prompt_tokens, result.completion_tokens)

    review_run.prompt_tokens = result.prompt_tokens
    review_run.completion_tokens = result.completion_tokens

    finding_rows = []
    for f in result.findings:
        row = Finding(
            review_run_id=review_run.id,
            file=f.file,
            line=f.line,
            severity=f.severity,
            comment=f.comment,
        )
        db.add(row)
        finding_rows.append(row)
    db.commit()  # assigns each row.id

    posted_count = 0
    failed_count = 0
    for row in finding_rows:
        try:
            github.post_review_comment(
                owner, repo_name, pull_request.number,
                commit_id=pull_request.head_sha,
                path=row.file, line=row.line,
                body=f"**[{row.severity}]** {row.comment}",
            )
            row.posted = True
            posted_count += 1
        except Exception as exc:
            # A single bad comment (e.g. line not part of the diff, or a
            # permissions error) shouldn't abort the rest of the review --
            # log it, record it against the finding, and keep going.
            logger.warning("Failed to post comment on %s:%s -- %s", row.file, row.line, exc)
            row.posted = False
            row.post_error = str(exc)
            failed_count += 1

    db.commit()

    if failed_count == 0:
        review_run.status = "done"
    elif posted_count > 0:
        review_run.status = "partial"
        review_run.error = f"{failed_count}/{len(finding_rows)} comment(s) failed to post"
    else:
        review_run.status = "partial" if finding_rows else "done"
        if finding_rows:
            review_run.error = f"all {failed_count} comment(s) failed to post"

    logger.info("Posted %d/%d comment(s) for review_run %s",
                posted_count, len(finding_rows), review_run.id)
