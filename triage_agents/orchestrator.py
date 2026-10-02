from __future__ import annotations

import asyncio
import json
import time
from collections import Counter
from pathlib import Path

from agents import Agent, Runner
from pydantic import BaseModel

from mcp_server.tools.gitleaks_tool import GitleaksResult
from mcp_server.tools.osv_tool import CVEResult
from mcp_server.tools.semgrep_tool import SemgrepResult
from observability.tracing import pipeline_observation, record_pipeline_result
from triage_agents.base import configure_groq_client
from triage_agents.correlator import CORRELATOR_AGENT, findings_from_scan_results
from triage_agents.cve_agent import CVE_AGENT
from triage_agents.models import OrchestratorResult, ScanTiming
from triage_agents.reporter_agent import render_report
from triage_agents.sast_agent import SAST_AGENT
from triage_agents.secrets_agent import SECRETS_AGENT


def _dependency_file(repo_path: str) -> str | None:
    root = Path(repo_path)
    for name in ("requirements.txt", "pyproject.toml"):
        candidate = root / name
        if candidate.is_file():
            return str(candidate)
    return None


async def _run_agent(
    name: str,
    agent: Agent,
    agent_input: str,
    output_type: type[BaseModel],
    required_tool: str | None,
    output_from_tool: bool = False,
) -> tuple[str, object, ScanTiming]:
    started = time.perf_counter()
    try:
        run_result = await Runner.run(agent, agent_input)
        matching_outputs = []
        if required_tool:
            calls = {
                item.call_id
                for item in run_result.new_items
                if getattr(item, "type", None) == "tool_call_item"
                and getattr(item, "tool_name", None) == required_tool
                and item.call_id is not None
            }
            outputs = {
                item.call_id: item
                for item in run_result.new_items
                if getattr(item, "type", None) == "tool_call_output_item"
                and item.call_id is not None
            }
            matching_outputs = [outputs[call_id] for call_id in calls.intersection(outputs)]
            if not matching_outputs:
                raise RuntimeError(f"{name} agent did not return output from {required_tool}")
            if output_from_tool and len(matching_outputs) != 1:
                raise RuntimeError(f"{name} agent returned multiple outputs from {required_tool}")
        output = matching_outputs[0].output if output_from_tool else run_result.final_output
        if isinstance(output, str):
            output = output_type.model_validate_json(output)
        elif not isinstance(output, output_type):
            output = output_type.model_validate(output)
        return name, output, ScanTiming(
            agent=name, duration_ms=int((time.perf_counter() - started) * 1000), status="ok"
        )
    except Exception as exc:  # noqa: BLE001 - every scanner failure is fail-closed
        return name, exc, ScanTiming(
            agent=name,
            duration_ms=int((time.perf_counter() - started) * 1000),
            status="failed",
            detail=str(exc),
        )


async def _run_security_pipeline(
    repo_path: str,
    changed_files: list[str],
    pr_metadata: dict | None = None,
) -> OrchestratorResult:
    """Run scanner agents concurrently, then correlate and report findings."""
    started = time.perf_counter()
    dependency_file = _dependency_file(repo_path)
    configuration_error = None
    try:
        configure_groq_client()
    except Exception as exc:  # noqa: BLE001 - configuration failures must fail closed
        configuration_error = exc

    async def run_or_fail(
        name: str,
        agent: Agent,
        agent_input: str,
        output_type: type[BaseModel],
        required_tool: str,
        output_from_tool: bool = False,
    ) -> tuple[str, object, ScanTiming]:
        if configuration_error is not None:
            return name, configuration_error, ScanTiming(
                agent=name,
                duration_ms=0,
                status="failed",
                detail=str(configuration_error),
            )
        return await _run_agent(
            name, agent, agent_input, output_type, required_tool, output_from_tool
        )

    tasks = [
        run_or_fail(
            "SAST",
            SAST_AGENT,
            f"Scan this repository: {repo_path}",
            SemgrepResult,
            "scan_with_semgrep",
            True,
        ),
        run_or_fail(
            "Secrets",
            SECRETS_AGENT,
            f"Scan this repository: {repo_path}",
            GitleaksResult,
            "scan_with_gitleaks",
            True,
        ),
    ]
    if dependency_file is None:
        tasks.append(
            asyncio.sleep(
                0,
                result=(
                    "CVE",
                    None,
                    ScanTiming(
                        agent="CVE",
                        duration_ms=0,
                        status="skipped",
                        detail="No dependency file found",
                    ),
                ),
            )
        )
    else:
        tasks.append(
            run_or_fail(
                "CVE",
                CVE_AGENT,
                f"Scan dependencies in: {dependency_file}",
                CVEResult,
                "scan_dependencies",
                True,
            )
        )

    results = await asyncio.gather(*tasks)
    by_name = {name: (value, timing) for name, value, timing in results}
    deterministic_report = findings_from_scan_results(
        by_name["SAST"][0],
        by_name["Secrets"][0],
        by_name["CVE"][0],
        changed_files,
        repo_path,
    )
    if dependency_file is None:
        deterministic_report.scan_failures.append(
            "CVE SKIPPED: no requirements.txt or pyproject.toml found"
        )

    correlation_started = time.perf_counter()
    correlation_timing: ScanTiming
    correlation_error = configuration_error
    if correlation_error is None:
        scan_payload = {
            "sast": by_name["SAST"][0].model_dump(mode="json")
            if isinstance(by_name["SAST"][0], SemgrepResult)
            else None,
            "secrets": by_name["Secrets"][0].model_dump(mode="json")
            if isinstance(by_name["Secrets"][0], GitleaksResult)
            else None,
            "cves": by_name["CVE"][0].model_dump(mode="json")
            if isinstance(by_name["CVE"][0], CVEResult)
            else None,
            "changed_files": changed_files,
            "repo_root": repo_path,
            "scan_failures": deterministic_report.scan_failures,
        }
        try:
            required_reachability_tool = (
                "check_finding_reachability"
                if isinstance(by_name["SAST"][0], SemgrepResult)
                and by_name["SAST"][0].findings
                else None
            )
            _, correlation_output, correlation_timing = await _run_agent(
                "Correlator",
                CORRELATOR_AGENT,
                json.dumps(scan_payload),
                type(deterministic_report),
                required_reachability_tool,
            )
            if isinstance(correlation_output, BaseException):
                raise correlation_output
            report = correlation_output
            expected_fingerprints = Counter(
                item.fingerprint
                for group in (
                    deterministic_report.p1_findings,
                    deterministic_report.p2_findings,
                    deterministic_report.p3_findings,
                )
                for item in group
            )
            actual_fingerprints = Counter(
                item.fingerprint
                for group in (report.p1_findings, report.p2_findings, report.p3_findings)
                for item in group
            )
            if actual_fingerprints != expected_fingerprints:
                raise ValueError("correlator output did not preserve every finding")
            priority_rank = {"P1": 1, "P2": 2, "P3": 3}
            expected_priorities = {
                item.fingerprint: item.priority
                for group in (
                    deterministic_report.p1_findings,
                    deterministic_report.p2_findings,
                    deterministic_report.p3_findings,
                )
                for item in group
            }
            if any(
                priority_rank[item.priority] > priority_rank[expected_priorities[item.fingerprint]]
                for group in (report.p1_findings, report.p2_findings, report.p3_findings)
                for item in group
            ):
                raise ValueError("correlator output downgraded a deterministic priority")
            report.scan_failures = list(deterministic_report.scan_failures)
            report.changed_files = list(changed_files)
        except Exception as exc:  # noqa: BLE001 - use deterministic fail-closed fallback
            correlation_error = exc

    if correlation_error is not None:
        detail = str(correlation_error)
        report = deterministic_report
        report.scan_failures.append(f"CORRELATOR FAILED: {detail}")
        correlation_timing = ScanTiming(
            agent="Correlator",
            duration_ms=int((time.perf_counter() - correlation_started) * 1000),
            status="failed",
            detail=detail,
        )

    return OrchestratorResult(
        pr_comment_markdown=render_report(report),
        should_block_merge=bool(report.p1_findings or report.scan_failures),
        correlation_report=report,
        total_scan_time_ms=int((time.perf_counter() - started) * 1000),
        scan_failures=report.scan_failures,
        timings=[by_name[name][1] for name in ("SAST", "Secrets", "CVE")] + [correlation_timing],
    )


async def run_security_pipeline(
    repo_path: str,
    changed_files: list[str],
    pr_metadata: dict | None = None,
) -> OrchestratorResult:
    """Run the pipeline and emit an optional Langfuse trace."""
    with pipeline_observation(
        {"repo_path": repo_path, "changed_files": changed_files, "pr_metadata": pr_metadata or {}}
    ) as observation:
        result = await _run_security_pipeline(repo_path, changed_files, pr_metadata)
        record_pipeline_result(
            observation,
            {
                "should_block_merge": result.should_block_merge,
                "p1_count": len(result.correlation_report.p1_findings),
                "p2_count": len(result.correlation_report.p2_findings),
                "p3_count": len(result.correlation_report.p3_findings),
            },
            {
                "total_scan_time_ms": result.total_scan_time_ms,
                "scan_failures": result.scan_failures,
                "timings": [timing.model_dump() for timing in result.timings],
            },
        )
        return result