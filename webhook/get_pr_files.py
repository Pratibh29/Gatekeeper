from __future__ import annotations

import os

from github import Github


def get_pr_changed_files(repo_full_name: str, pr_number: int) -> list[str]:
    """Return every changed filename from a pull request."""
    github = Github(os.getenv("GITHUB_TOKEN"))
    pull_request = github.get_repo(repo_full_name).get_pull(pr_number)
    return [file.filename for file in pull_request.get_files()]