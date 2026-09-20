from __future__ import annotations

import hashlib
import hmac
import json
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest

from triage_agents.models import CorrelationReport, EnrichedFinding, OrchestratorResult
from webhook import app as webhook_module


def _pipeline_result() -> OrchestratorResult:
    finding = EnrichedFinding(
        source="secret",
        title="test-secret",
        file_path="config.py",
        line=1,
        severity="ERROR",
        message="Test secret detected",
        fingerprint="test-secret:config.py:1",
        category="Hardcoded Secret",
        reachability={
            "is_reachable": True,
            "confidence": "HIGH",
            "evidence": "Secret is present in the PR diff.",
            "method": "same_file",
        },
        priority="P1",
    )
    report = CorrelationReport(
        p1_findings=[finding],
        changed_files=["config.py"],
    )
    return OrchestratorResult(
        pr_comment_markdown="## Security Scan Summary\n\n**Status:** MERGE BLOCKED",
        should_block_merge=True,
        correlation_report=report,
        total_scan_time_ms=12,
    )


@pytest.mark.asyncio
async def test_signed_pull_request_webhook_runs_background_pipeline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    secret = "local-webhook-secret"
    payload = {
        "action": "opened",
        "number": 42,
        "repository": {"full_name": "example/security-demo"},
        "pull_request": {
            "head": {
                "sha": "abc123",
                "repo": {"clone_url": "https://github.com/example/security-demo.git"},
            }
        },
    }
    calls: dict[str, object] = {}

    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", secret)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(
        webhook_module,
        "get_pr_changed_files",
        lambda repo, number: ["config.py"],
    )

    @contextmanager
    def fake_cloned_repo(clone_url: str, head_sha: str, github_token: str):
        calls["clone"] = (clone_url, head_sha, github_token)
        yield str(tmp_path)

    async def fake_pipeline(repo_path: str, changed_files: list[str], metadata: dict):
        calls["pipeline"] = (repo_path, changed_files, metadata)
        return _pipeline_result()

    monkeypatch.setattr(webhook_module, "cloned_repo", fake_cloned_repo)
    monkeypatch.setattr(webhook_module, "run_security_pipeline", fake_pipeline)
    monkeypatch.setattr(
        webhook_module,
        "filter_new_findings",
        lambda findings, pr_number, repo: list(findings),
    )
    monkeypatch.setattr(
        webhook_module,
        "record_findings",
        lambda findings, pr_number, repo: calls.update(recorded=list(findings)),
    )
    monkeypatch.setattr(
        webhook_module,
        "post_pr_comment",
        lambda repo, number, comment: calls.update(comment=(repo, number, comment)),
    )
    monkeypatch.setattr(
        webhook_module,
        "create_check_run",
        lambda repo, sha, conclusion, title, summary: calls.update(
            check=(repo, sha, conclusion, title, summary)
        ),
    )

    body = json.dumps(payload).encode("utf-8")
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    transport = httpx.ASGITransport(app=webhook_module.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/webhook/github",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": signature,
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    assert calls["clone"] == (
        "https://github.com/example/security-demo.git",
        "abc123",
        "test-token",
    )
    assert calls["pipeline"] == (
        str(tmp_path),
        ["config.py"],
        {"repo": "example/security-demo", "pr_number": 42, "head_sha": "abc123"},
    )
    assert len(calls["recorded"]) == 1
    assert calls["comment"][:2] == ("example/security-demo", 42)
    assert calls["check"][:3] == ("example/security-demo", "abc123", "failure")
