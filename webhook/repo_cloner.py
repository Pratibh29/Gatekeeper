from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def cloned_repo(clone_url: str, head_sha: str, github_token: str) -> Iterator[str]:
    """Clone a PR commit into a temporary directory and always remove it."""
    tmp_dir = tempfile.mkdtemp(prefix="security-triage-")
    auth_url = clone_url.replace("https://", f"https://{github_token}@", 1)
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", auth_url, tmp_dir],
            check=True,
            capture_output=True,
            timeout=60,
        )
        subprocess.run(
            ["git", "fetch", "--depth", "1", "origin", head_sha],
            cwd=tmp_dir,
            check=True,
            capture_output=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "checkout", head_sha],
            cwd=tmp_dir,
            check=True,
            capture_output=True,
            timeout=10,
        )
        yield tmp_dir
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)