"""Worker: polls for pending jobs, runs the review, posts comments, updates status.

Step 4 of the build plan. Start with simple DB polling; swap in Redis/SQS later
if you want a push-based queue instead of poll-based.
"""
import time

from app.worker.review import process_pending_job

POLL_INTERVAL_SECONDS = 5


def run_forever():
    print("Worker started, polling for jobs...")
    while True:
        processed = process_pending_job()
        if not processed:
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_forever()
