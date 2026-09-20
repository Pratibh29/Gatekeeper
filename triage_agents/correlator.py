from __future__ import annotations

from pathlib import Path

from agents import Agent, function_tool

from mcp_server.tools.gitleaks_tool import GitleaksFinding, GitleaksResult
from mcp_server.tools.osv_tool import CVEResult, CVEVulnerability
from mcp_server.tools.reachability_tool import ReachabilityResult, check_reachability
from mcp_server.tools.semgrep_tool import SemgrepFinding, SemgrepResult
from triage_agents.base import GROQ_MODEL
from triage_agents.models import CorrelationReport, EnrichedFinding
from triage_agents.priority import enrich_cve, enrich_sast, enrich_secret


@function_tool
def check_finding_reachability(
    finding_path: str,
    finding_check_id: str,
    finding_line: int,
    changed_files: list[str],
) -> ReachabilityResult:
    """Expose the reachability decision to the optional SDK correlator."""
    return check_reachability(finding_path, finding_check_id, finding_line, changed_files)


CORRELATOR_AGENT = Agent(
    name="Security-Correlator",
    model=GROQ_MODEL,
    instructions=(
        "For every finding, use the reachability tool and classify it with the security "
        "rubric. Be conservative: low confidence requires manual review."
    ),
    output_type=CorrelationReport,
    tools=[check_finding_reachability],
)


def _package_imported(package_name: str, changed_files: list[str]) -> bool:
    needles = {package_name.lower(), package_name.lower().replace("-", "_")}
    for changed in changed_files:
        path = Path(changed)
        text = changed.lower()
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if any(needle in text for needle in needles):
            return True
    return False


def correlate_findings(
    sast_findings: list[SemgrepFinding] | list[dict],
    secret_findings: list[GitleaksFinding] | list[dict],
    cve_findings: list[CVEVulnerability] | list[dict],
    changed_files: list[str],
    scan_failures: list[str] | None = None,
) -> CorrelationReport:
    """Deterministic correlator implementing the severity rubric (fail-closed)."""
    enriched: list[EnrichedFinding] = []

    for raw in sast_findings:
        finding = raw if isinstance(raw, SemgrepFinding) else SemgrepFinding.model_validate(raw)
        reachability = check_reachability(
            finding.path, finding.check_id, finding.line, changed_files
        )
        enriched.append(enrich_sast(finding, reachability))

    for raw in secret_findings:
        finding = raw if isinstance(raw, GitleaksFinding) else GitleaksFinding.model_validate(raw)
        enriched.append(enrich_secret(finding))

    for raw in cve_findings:
        finding = raw if isinstance(raw, CVEVulnerability) else CVEVulnerability.model_validate(raw)
        imported = _package_imported(finding.package_name, changed_files)
        if imported:
            reachability = ReachabilityResult(
                is_reachable=True,
                confidence="MEDIUM",
                method="direct_import",
                evidence=f"Package {finding.package_name} is referenced in changed files.",
            )
        else:
            reachability = ReachabilityResult(
                is_reachable=False,
                confidence="LOW",
                method="no_evidence_found",
                evidence="No direct import found; manual review recommended",
            )
        enriched.append(enrich_cve(finding, reachability))

    p1 = [item for item in enriched if item.priority == "P1"]
    p2 = [item for item in enriched if item.priority == "P2"]
    p3 = [item for item in enriched if item.priority == "P3"]
    suppressed = sum(1 for item in enriched if item.reachability.method == "no_evidence_found")
    return CorrelationReport(
        p1_findings=p1,
        p2_findings=p2,
        p3_findings=p3,
        total_suppressed=suppressed,
        changed_files=changed_files,
        scan_failures=list(scan_failures or []),
    )


def findings_from_scan_results(
    sast: SemgrepResult | BaseException | None,
    secrets: GitleaksResult | BaseException | None,
    cves: CVEResult | BaseException | None,
    changed_files: list[str],
) -> CorrelationReport:
    failures: list[str] = []
    sast_findings: list[SemgrepFinding] = []
    secret_findings: list[GitleaksFinding] = []
    cve_findings: list[CVEVulnerability] = []

    if isinstance(sast, BaseException):
        failures.append(f"SAST FAILED: {sast}")
    elif sast is not None:
        sast_findings = sast.findings

    if isinstance(secrets, BaseException):
        failures.append(f"SECRETS FAILED: {secrets}")
    elif secrets is not None:
        secret_findings = secrets.findings

    if isinstance(cves, BaseException):
        failures.append(f"CVE FAILED: {cves}")
    elif cves is not None:
        cve_findings = cves.vulnerabilities

    return correlate_findings(
        sast_findings, secret_findings, cve_findings, changed_files, failures
    )
