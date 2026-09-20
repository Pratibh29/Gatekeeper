"""
Tool: check_dependencies_for_cves
Input: requirements_file_path (str)
Output: CVEResult (vulnerabilities, packages_checked, scan_time_ms)

1. Parse the dependency file with parse_dependency_file
2. POST a batch query to https://api.osv.dev/v1/querybatch
3. For packages with hits, POST /v1/query to load summary/severity/fixed versions
4. Skip packages with no vulnerabilities
Timeout: 30 seconds
"""
from __future__ import annotations

import time

import httpx
from pydantic import BaseModel

from mcp_server.tools.dep_parser import parse_dependency_file

OSV_QUERYBATCH = "https://api.osv.dev/v1/querybatch"
OSV_QUERY = "https://api.osv.dev/v1/query"


class CVEVulnerability(BaseModel):
    package_name: str
    installed_version: str
    cve_id: str
    summary: str
    severity_score: float | None = None
    fixed_in: list[str]


class CVEResult(BaseModel):
    vulnerabilities: list[CVEVulnerability]
    packages_checked: int
    scan_time_ms: int


def _severity_score(vuln: dict) -> float | None:
    for item in vuln.get("severity") or []:
        if not isinstance(item, dict):
            continue
        raw = item.get("score")
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def _fixed_versions(vuln: dict) -> list[str]:
    fixed: list[str] = []
    for affected in vuln.get("affected") or []:
        for rng in affected.get("ranges") or []:
            for event in rng.get("events") or []:
                if "fixed" in event:
                    fixed.append(str(event["fixed"]))
    return fixed


def _cve_id(vuln: dict) -> str:
    for alias in vuln.get("aliases") or []:
        if str(alias).startswith("CVE-"):
            return str(alias)
    return str(vuln.get("id", "unknown"))


def check_dependencies_for_cves(requirements_file_path: str) -> CVEResult:
    start = time.time()
    packages = parse_dependency_file(requirements_file_path)
    if not packages:
        return CVEResult(vulnerabilities=[], packages_checked=0, scan_time_ms=int((time.time() - start) * 1000))

    payload = {
        "queries": [
            {"version": pkg["version"], "package": {"name": pkg["name"], "ecosystem": pkg["ecosystem"]}}
            for pkg in packages
        ]
    }
    batch = httpx.post(OSV_QUERYBATCH, json=payload, timeout=30)
    batch.raise_for_status()
    results = batch.json().get("results", [])

    vulnerabilities: list[CVEVulnerability] = []
    for package, result in zip(packages, results, strict=False):
        if not result.get("vulns"):
            continue
        detail = httpx.post(
            OSV_QUERY,
            json={
                "version": package["version"],
                "package": {"name": package["name"], "ecosystem": package["ecosystem"]},
            },
            timeout=30,
        )
        detail.raise_for_status()
        for vuln in detail.json().get("vulns") or []:
            vulnerabilities.append(
                CVEVulnerability(
                    package_name=package["name"],
                    installed_version=package["version"],
                    cve_id=_cve_id(vuln),
                    summary=str(vuln.get("summary") or ""),
                    severity_score=_severity_score(vuln),
                    fixed_in=_fixed_versions(vuln),
                )
            )

    return CVEResult(
        vulnerabilities=vulnerabilities,
        packages_checked=len(packages),
        scan_time_ms=int((time.time() - start) * 1000),
    )


def register_osv_tools(mcp):
    @mcp.tool()
    def check_dependencies_for_cves_tool(requirements_file_path: str) -> CVEResult:
        """Check a dependency file for CVEs via OSV.dev."""
        return check_dependencies_for_cves(requirements_file_path)

    return check_dependencies_for_cves_tool
