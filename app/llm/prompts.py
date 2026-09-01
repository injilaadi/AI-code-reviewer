"""Prompt templates for diff review."""

REVIEW_SYSTEM_PROMPT = """You are an automated code reviewer. Given a unified diff,
identify real issues: bugs, security problems, and clear correctness concerns.
Respond ONLY with a JSON array of findings, each shaped like:
{"file": "path/to/file", "line": 42, "severity": "high|medium|low", "comment": "..."}
If there are no issues, respond with an empty array []."""


def build_review_prompt(diff: str) -> str:
    return f"Review this diff:\n\n{diff}"
