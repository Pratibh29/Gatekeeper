"""
Tool: run_gitleaks
Input: repo_path (str)
Output: GitleaksResult (findings, scan_time_ms)

GitleaksFinding.match is truncated to 50 chars — never store full secrets.
Exit code 1 means secrets were found (not an error).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from pydantic import BaseModel


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


class GitleaksFinding(BaseModel):
    rule_id: str
    match: str
    file_path: str
    line: int
    description: str
    tags: list[str]


class GitleaksResult(BaseModel):
    findings: list[GitleaksFinding]
    scan_time_ms: int


def run_gitleaks(repo_path: str) -> GitleaksResult:
    report_path = Path(tempfile.gettempdir()) / "gitleaks_report.json"
    if report_path.exists():
        report_path.unlink()

    start = time.time()
    completed = subprocess.run(
        [
            _resolve_executable("gitleaks"),
            "detect",
            "--source",
            repo_path,
            "--report-format",
            "json",
            "--report-path",
            str(report_path),
            "--no-git",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=120,
    )
    if completed.returncode not in (0, 1):
        raise RuntimeError(f"Gitleaks failed: {(completed.stderr or completed.stdout)[:500]}")

    if not report_path.exists():
        return GitleaksResult(findings=[], scan_time_ms=int((time.time() - start) * 1000))

    payload = json.loads(report_path.read_text(encoding="utf-8") or "[]")
    findings = [
        GitleaksFinding(
            rule_id=str(item.get("RuleID", "")),
            match=str(item.get("Match", ""))[:50],
            file_path=str(item.get("File", "")),
            line=int(item.get("StartLine", 0) or 0),
            description=str(item.get("Description", "")),
            tags=[str(tag) for tag in item.get("Tags", [])],
        )
        for item in payload
    ]
    return GitleaksResult(findings=findings, scan_time_ms=int((time.time() - start) * 1000))


def register_gitleaks_tools(mcp):
    @mcp.tool()
    def run_gitleaks_tool(repo_path: str) -> GitleaksResult:
        """Run Gitleaks and return truncated secret findings."""
        return run_gitleaks(repo_path)

    return run_gitleaks_tool
