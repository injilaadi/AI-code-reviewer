"""SQLAlchemy models: repos, pull_requests, review_runs, findings.

review_runs.status doubles as the job queue state: 'pending' -> worker picks it up ->
'running' -> 'done' | 'partial' | 'failed'.
  - 'done'    : LLM review succeeded and every finding was posted to GitHub.
  - 'partial' : LLM review succeeded but one or more findings failed to post
                (see error for details) -- distinct from 'done' so a silently
                incomplete review is visible instead of looking identical to a
                fully successful one.
  - 'failed'  : the review itself failed (LLM call, diff fetch, etc).
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Repo(Base):
    __tablename__ = "repos"
    id = Column(Integer, primary_key=True)
    full_name = Column(String, unique=True, nullable=False)  # e.g. "owner/repo"


class PullRequest(Base):
    __tablename__ = "pull_requests"
    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repos.id"), nullable=False)
    number = Column(Integer, nullable=False)
    title = Column(String)
    head_sha = Column(String, nullable=False)  # commit_id needed to post inline comments

    repo = relationship("Repo")
    review_runs = relationship("ReviewRun", back_populates="pull_request")


class ReviewRun(Base):
    __tablename__ = "review_runs"
    id = Column(Integer, primary_key=True)
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=False)
    status = Column(String, default="pending", nullable=False)  # pending|running|done|partial|failed
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)

    pull_request = relationship("PullRequest", back_populates="review_runs")
    findings = relationship("Finding", back_populates="review_run")


class Finding(Base):
    __tablename__ = "findings"
    id = Column(Integer, primary_key=True)
    review_run_id = Column(Integer, ForeignKey("review_runs.id"), nullable=False)
    file = Column(String, nullable=False)
    line = Column(Integer, nullable=False)
    severity = Column(String, nullable=False)
    comment = Column(Text, nullable=False)
    posted = Column(Boolean, default=False, nullable=False)  # did it actually reach GitHub?
    post_error = Column(Text, nullable=True)  # why not, if posted=False

    review_run = relationship("ReviewRun", back_populates="findings")
