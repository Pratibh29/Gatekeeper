from __future__ import annotations

import os

from github import Github


def get_github_client() -> Github:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not configured")
    return Github(token)


def post_pr_comment(repo_full_name: str, pr_number: int, comment: str) -> None:
    repo = get_github_client().get_repo(repo_full_name)
    repo.get_pull(pr_number).create_issue_comment(comment)


def create_check_run(
    repo_full_name: str,
    head_sha: str,
    conclusion: str,
    title: str,
    summary: str,
) -> None:
    if conclusion not in {"success", "failure", "neutral"}:
        raise ValueError(f"Unsupported check conclusion: {conclusion}")
    repo = get_github_client().get_repo(repo_full_name)
    repo.create_check_run(
        name="Security Triage Agent",
        head_sha=head_sha,
        status="completed",
        conclusion=conclusion,
        output={"title": title, "summary": summary},
    )


def create_commit_status(
    repo_full_name: str,
    head_sha: str,
    conclusion: str,
    title: str,
    summary: str,
) -> None:
    """Publish the result using the commit-status API when Checks is unavailable."""
    if conclusion not in {"success", "failure", "neutral"}:
        raise ValueError(f"Unsupported status conclusion: {conclusion}")
    state = {"success": "success", "failure": "error", "neutral": "pending"}[conclusion]
    repo = get_github_client().get_repo(repo_full_name)
    repo.get_commit(head_sha).create_status(
        state=state,
        context="Security Triage Agent",
        description=f"{title}: {summary[:140]}",
    )