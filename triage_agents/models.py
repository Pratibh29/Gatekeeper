from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from mcp_server.tools.reachability_tool import ReachabilityResult


class EnrichedFinding(BaseModel):
    source: Literal["sast", "secret", "cve"]
    title: str
    file_path: str
    line: int | None = None
    severity: str
    message: str
    fingerprint: str
    cwe: str | None = None
    cve_id: str | None = None
    cvss: float | None = None
    category: str
    reachability: ReachabilityResult
    priority: Literal["P1", "P2", "P3"]


class CorrelationReport(BaseModel):
    p1_findings: list[EnrichedFinding] = Field(default_factory=list)
    p2_findings: list[EnrichedFinding] = Field(default_factory=list)
    p3_findings: list[EnrichedFinding] = Field(default_factory=list)
    total_suppressed: int = 0
    changed_files: list[str] = Field(default_factory=list)
    scan_failures: list[str] = Field(default_factory=list)


class ScanTiming(BaseModel):
    agent: str
    duration_ms: int
    status: Literal["ok", "failed", "skipped"]
    detail: str = ""


class OrchestratorResult(BaseModel):
    pr_comment_markdown: str
    should_block_merge: bool
    correlation_report: CorrelationReport
    total_scan_time_ms: int
    scan_failures: list[str] = Field(default_factory=list)
    timings: list[ScanTiming] = Field(default_factory=list)
