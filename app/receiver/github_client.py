"""Thin wrapper around the GitHub REST API: fetch PR diffs, post review comments."""
import httpx

GITHUB_API = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str):
        self._client = httpx.Client(
            base_url=GITHUB_API,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
        )

    def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """Fetch the unified diff for a PR."""
        resp = self._client.get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
            headers={"Accept": "application/vnd.github.v3.diff"},
        )
        resp.raise_for_status()
        return resp.text

    def post_review_comment(self, owner: str, repo: str, pr_number: int, commit_id: str,
                             path: str, line: int, body: str) -> dict:
        """Post a single inline comment on a specific diff line."""
        resp = self._client.post(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/comments",
            json={"body": body, "commit_id": commit_id, "path": path, "line": line},
        )
        resp.raise_for_status()
        return resp.json()
