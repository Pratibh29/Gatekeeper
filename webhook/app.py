from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from state.dedup_store import filter_new_findings, record_findings
from triage_agents.orchestrator import run_security_pipeline
from triage_agents.reporter_agent import render_report
from webhook.get_pr_files import get_pr_changed_files
from webhook.github_client import (
    create_check_run,
    create_commit_status,
    post_pr_comment,
)
from webhook.repo_cloner import cloned_repo

load_dotenv()
app = FastAPI(title="Security Triage Agent")
logger = logging.getLogger(__name__)


def validate_github_signature(payload: bytes, sig_header: str) -> bool:
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "").encode()
    if not secret or not sig_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_header)


async def process_pull_request(payload: dict[str, Any]) -> None:
    repository = payload["repository"]
    pull_request = payload["pull_request"]
    repo_full_name = repository["full_name"]
    pr_number = int(payload["number"])
    head_sha = pull_request["head"]["sha"]
    changed_files = get_pr_changed_files(repo_full_name, pr_number)

    with cloned_repo(
        pull_request["head"]["repo"]["clone_url"],
        head_sha,
        os.getenv("GITHUB_TOKEN", ""),
    ) as repo_path:
        result = await run_security_pipeline(
            repo_path,
            changed_files,
            {"repo": repo_full_name, "pr_number": pr_number, "head_sha": head_sha},
        )

    findings = (
        result.correlation_report.p1_findings
        + result.correlation_report.p2_findings
        + result.correlation_report.p3_findings
    )
    new_findings = filter_new_findings(findings, pr_number, repo_full_name)
    if new_findings:
        new_report = result.correlation_report.model_copy(
            update={
                "p1_findings": [f for f in result.correlation_report.p1_findings if f in new_findings],
                "p2_findings": [f for f in result.correlation_report.p2_findings if f in new_findings],
                "p3_findings": [f for f in result.correlation_report.p3_findings if f in new_findings],
            }
        )
        try:
            post_pr_comment(repo_full_name, pr_number, render_report(new_report))
        except Exception:
            logger.exception("Could not post PR comment")
        else:
            record_findings(new_findings, pr_number, repo_full_name)

    conclusion = "failure" if result.should_block_merge else "success"
    try:
        if os.getenv("GITHUB_CHECKS_ENABLED", "true").lower() in {"1", "true", "yes"}:
            create_check_run(
                repo_full_name,
                head_sha,
                conclusion,
                "Security triage completed",
                result.pr_comment_markdown,
            )
        else:
            create_commit_status(
                repo_full_name,
                head_sha,
                conclusion,
                "Security triage completed",
                result.pr_comment_markdown,
            )
    except Exception:
        logger.exception("Could not publish GitHub result")


@app.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks) -> dict[str, str]:
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not validate_github_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event = request.headers.get("X-GitHub-Event", "")
    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    if event == "pull_request" and payload.get("action") in {"opened", "synchronize"}:
        background_tasks.add_task(process_pull_request, payload)
    return {"status": "accepted"}