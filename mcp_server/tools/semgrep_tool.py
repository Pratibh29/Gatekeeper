"""
Tool: run_semgrep
Input: repo_path (str), rules (str = "p/security-audit")
Output: SemgrepResult (findings, scan_time_ms, rule_count)

Runs: semgrep --config={rules} --json {repo_path}
Exit code 1 means findings exist (not an error). Timeout: 120 seconds.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator


def _resolve_executable(binary_name: str) -> str:
    resolved = shutil.which(binary_name)
    if resolved:
        return resolved

    search_dirs = [
        Path(sys.executable).resolve().parent,
        Path(__file__).resolve().parents[2] / "tools" / "bin",
    ]
    for directory in search_dirs:
        for candidate in (directory / f"{binary_name}.exe", directory / binary_name):
            if candidate.exists():
                return str(candidate)
    return binary_name


class SemgrepFinding(BaseModel):
    check_id: str
    path: str
    line: int
    severity: Literal["ERROR", "WARNING", "INFO"]
    message: str
    cwe: str | None = None
    fingerprint: str

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, value: object) -> str:
        raw = str(value or "WARNING").upper()
        if raw in {"ERROR", "CRITICAL", "HIGH"}:
            return "ERROR"
        if raw in {"WARNING", "MEDIUM"}:
            return "WARNING"
        return "INFO"


class SemgrepResult(BaseModel):
    findings: list[SemgrepFinding]
    scan_time_ms: int
    rule_count: int


def run_semgrep(repo_path: str, rules: str = "p/security-audit") -> SemgrepResult:
    start = time.time()
    completed = subprocess.run(
        [_resolve_executable("semgrep"), "--config", rules, "--json", repo_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=120,
    )
    if completed.returncode not in (0, 1):
        raise RuntimeError(f"Semgrep failed: {(completed.stderr or completed.stdout)[:500]}")

    data = json.loads(completed.stdout or "{}")
    findings: list[SemgrepFinding] = []
    for item in data.get("results", []):
        extra = item.get("extra", {})
        metadata = extra.get("metadata", {})
        cwe = metadata.get("cwe")
        if isinstance(cwe, list):
            cwe = cwe[0] if cwe else None
        fingerprint = extra.get("fingerprint") or (
            f"{item.get('check_id')}:{item.get('path')}:{item.get('start', {}).get('line')}"
        )
        findings.append(
            SemgrepFinding(
                check_id=item.get("check_id", ""),
                path=item.get("path", ""),
                line=int(item.get("start", {}).get("line", 0)),
                severity=extra.get("severity", "WARNING"),
                message=extra.get("message", ""),
                cwe=str(cwe) if cwe else None,
                fingerprint=str(fingerprint),
            )
        )

    return SemgrepResult(
        findings=findings,
        scan_time_ms=int((time.time() - start) * 1000),
        rule_count=len(data.get("rules", [])),
    )


def register_semgrep_tools(mcp):
    @mcp.tool()
    def run_semgrep_tool(repo_path: str, rules: str = "p/security-audit") -> SemgrepResult:
        """Runs Semgrep static analysis on a code repository."""
        return run_semgrep(repo_path, rules)

    return run_semgrep_tool
