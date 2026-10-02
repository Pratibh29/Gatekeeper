from __future__ import annotations

import asyncio
import hashlib
import hmac
from pathlib import Path
from types import SimpleNamespace

from agents import Runner

from mcp_server.tools.gitleaks_tool import GitleaksFinding, GitleaksResult
from state.dedup_store import filter_new_findings, record_findings
from triage_agents.models import CorrelationReport, EnrichedFinding
from triage_agents.orchestrator import run_security_pipeline
from triage_agents.reporter_agent import render_report
from webhook.app import validate_github_signature


def test_dedup_store_filters_recorded_fingerprints(tmp_path: Path):
    database = tmp_path / "dedup.db"
    findings = [{"fingerprint": "one"}, {"fingerprint": "two"}]
    record_findings([findings[0]], 7, "org/repo", database)

    assert filter_new_findings(findings, 7, "org/repo", database) == [findings[1]]
    assert filter_new_findings(findings, 8, "org/repo", database) == findings


def test_reporter_includes_block_status_and_failures():
    report = CorrelationReport(
        p1_findings=[
            EnrichedFinding(
                source="sast",
                title="sql-injection",
                file_path="app.py",
                line=12,
                severity="ERROR",
                message="Unsanitized query",
                fingerprint="one",
                category="SQL Injection",
                reachability={
                    "is_reachable": True,
                    "confidence": "HIGH",
                    "evidence": "same file",
                    "method": "same_file",
                },
                priority="P1",
            )
        ],
        scan_failures=["CVE SKIPPED"],
    )
    output = render_report(report)
    assert "MERGE BLOCKED" in output
    assert "sql-injection" in output
    assert "CVE SKIPPED" in output


def test_github_signature_requires_exact_payload():
    secret = b"webhook-secret"
    payload = b'{"action":"opened"}'
    signature = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()

    import os

    os.environ["GITHUB_WEBHOOK_SECRET"] = secret.decode()
    assert validate_github_signature(payload, signature)
    assert not validate_github_signature(payload + b" ", signature)
    assert not validate_github_signature(payload, "sha256=invalid")


def test_pipeline_uses_agents_and_preserves_findings_on_agent_failure(monkeypatch, tmp_path: Path):
    invoked_agents: list[str] = []
    scanner_tools = {
        "SAST-Analyst": "scan_with_semgrep",
        "Secrets-Analyst": "scan_with_gitleaks",
    }

    async def fake_runner(agent, _agent_input: str):
        invoked_agents.append(agent.name)
        if agent.name == "SAST-Analyst":
            raise RuntimeError("Semgrep unavailable")
        outputs = {
            "Secrets-Analyst": GitleaksResult(
                findings=[
                    GitleaksFinding(
                        rule_id="generic-api-key",
                        match="redacted-secret",
                        file_path="config.py",
                        line=4,
                        description="API key",
                        tags=[],
                    )
                ],
                scan_time_ms=1,
            ),
            "Security-Correlator": CorrelationReport(),
        }
        tool_name = scanner_tools.get(agent.name)
        return SimpleNamespace(
            final_output=outputs[agent.name],
            new_items=[]
            if tool_name is None
            else [
                SimpleNamespace(type="tool_call_item", tool_name=tool_name, call_id="call-1"),
                SimpleNamespace(
                    type="tool_call_output_item",
                    call_id="call-1",
                    output=outputs[agent.name],
                ),
            ],
        )

    monkeypatch.setattr("triage_agents.orchestrator.configure_groq_client", lambda: None)
    monkeypatch.setattr(Runner, "run", fake_runner)

    result = asyncio.run(run_security_pipeline(str(tmp_path), ["README.md"]))

    assert result.should_block_merge is True
    assert any("SAST FAILED" in failure for failure in result.scan_failures)
    assert any("CORRELATOR FAILED" in failure for failure in result.scan_failures)
    assert result.correlation_report.p1_findings[0].title == "generic-api-key"
    assert "SAST-Analyst" in invoked_agents
    assert "Secrets-Analyst" in invoked_agents
    assert "Security-Correlator" in invoked_agents