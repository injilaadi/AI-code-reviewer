"""Worker: polls for pending jobs, runs the review, posts comments, updates status.

Start with simple DB polling; swap in Redis/SQS later if you want a push-based
queue instead of poll-based.
"""
import logging
import time

from app.worker.review import process_pending_job

POLL_INTERVAL_SECONDS = 5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("worker.main")


def run_forever():
    logger.info("Worker started, polling for jobs every %ds...", POLL_INTERVAL_SECONDS)
    while True:
        processed = process_pending_job()
        if not processed:
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_forever()
