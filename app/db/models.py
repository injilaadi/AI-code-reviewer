"""SQLAlchemy models: repos, pull_requests, review_runs, findings.

review_runs.status doubles as the job queue state: 'pending' -> worker picks it up ->
'running' -> 'done' | 'failed'.
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, func
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
    status = Column(String, default="pending", nullable=False)  # pending|running|done|failed
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

    review_run = relationship("ReviewRun", back_populates="findings")
