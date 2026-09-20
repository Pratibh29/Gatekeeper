from __future__ import annotations

import asyncio
import time
from pathlib import Path

from mcp_server.tools.gitleaks_tool import run_gitleaks
from mcp_server.tools.osv_tool import check_dependencies_for_cves
from mcp_server.tools.semgrep_tool import run_semgrep
from observability.tracing import pipeline_observation, record_pipeline_result
from triage_agents.correlator import findings_from_scan_results
from triage_agents.models import OrchestratorResult, ScanTiming
from triage_agents.reporter_agent import render_report


def _dependency_file(repo_path: str) -> str | None:
    root = Path(repo_path)
    for name in ("requirements.txt", "pyproject.toml"):
        candidate = root / name
        if candidate.is_file():
            return str(candidate)
    return None


async def _run_scan(name: str, scan, *args) -> tuple[str, object, ScanTiming]:
    started = time.perf_counter()
    try:
        result = await asyncio.to_thread(scan, *args)
        return name, result, ScanTiming(
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
    """Run the three scanners concurrently, then correlate and report findings."""
    started = time.perf_counter()
    dependency_file = _dependency_file(repo_path)
    cve_args = (dependency_file,) if dependency_file else ()
    tasks = [
        _run_scan("SAST", run_semgrep, repo_path),
        _run_scan("Secrets", run_gitleaks, repo_path),
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
        tasks.append(_run_scan("CVE", check_dependencies_for_cves, *cve_args))

    results = await asyncio.gather(*tasks)
    by_name = {name: (value, timing) for name, value, timing in results}
    report = findings_from_scan_results(
        by_name["SAST"][0],
        by_name["Secrets"][0],
        by_name["CVE"][0],
        changed_files,
    )
    if dependency_file is None:
        report.scan_failures.append("CVE SKIPPED: no requirements.txt or pyproject.toml found")
    return OrchestratorResult(
        pr_comment_markdown=render_report(report),
        should_block_merge=bool(report.p1_findings or report.scan_failures),
        correlation_report=report,
        total_scan_time_ms=int((time.perf_counter() - started) * 1000),
        scan_failures=report.scan_failures,
        timings=[by_name[name][1] for name in ("SAST", "Secrets", "CVE")],
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