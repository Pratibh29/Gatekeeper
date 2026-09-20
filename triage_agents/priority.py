from __future__ import annotations

from mcp_server.tools.gitleaks_tool import GitleaksFinding
from mcp_server.tools.osv_tool import CVEVulnerability
from mcp_server.tools.reachability_tool import ReachabilityResult
from mcp_server.tools.semgrep_tool import SemgrepFinding
from triage_agents.models import EnrichedFinding

P1_CATEGORY_MARKERS = (
    "sql injection",
    "sqli",
    "cwe-89",
    "command injection",
    "os command",
    "cwe-78",
    "subprocess",
    "shell=true",
    "hardcoded secret",
    "secret",
    "cwe-798",
    "rce",
    "remote code",
    "auth bypass",
    "authentication bypass",
)


def classify_category(*parts: str | None) -> str:
    blob = " ".join(p for p in parts if p).lower()
    if any(marker in blob for marker in ("sql", "cwe-89")):
        return "SQL Injection"
    if any(marker in blob for marker in ("command", "subprocess", "shell", "cwe-78")):
        return "Command Injection"
    if any(marker in blob for marker in ("secret", "gitleaks", "cwe-798", "hardcoded")):
        return "Hardcoded Secret"
    if "rce" in blob or "remote code" in blob:
        return "RCE"
    if "auth" in blob and "bypass" in blob:
        return "Auth Bypass"
    return "Other"


def _is_p1_category(category: str) -> bool:
    return category in {
        "SQL Injection",
        "Command Injection",
        "Hardcoded Secret",
        "RCE",
        "Auth Bypass",
    }


def assign_priority(
    *,
    source: str,
    severity: str,
    cvss: float | None,
    reachability: ReachabilityResult,
    category: str,
) -> str:
    if source == "secret":
        return "P1"

    reachable = reachability.is_reachable and reachability.confidence in {"HIGH", "MEDIUM"}
    high_severity = severity == "ERROR" or (cvss is not None and cvss >= 9.0)
    mid_cvss = cvss is not None and 7.0 <= cvss < 9.0

    if source == "cve":
        if cvss is not None and cvss >= 9.0 and reachable:
            return "P1"
        if mid_cvss or (cvss is not None and cvss >= 7.0):
            return "P2"
        return "P3"

    if high_severity and reachable and (_is_p1_category(category) or category == "Other"):
        return "P1"
    if high_severity and reachability.confidence == "LOW":
        return "P2"
    if severity == "WARNING" and reachable:
        return "P2"
    if mid_cvss:
        return "P2"
    return "P3"


def enrich_sast(finding: SemgrepFinding, reachability: ReachabilityResult) -> EnrichedFinding:
    category = classify_category(finding.check_id, finding.message, finding.cwe)
    return EnrichedFinding(
        source="sast",
        title=finding.check_id,
        file_path=finding.path,
        line=finding.line,
        severity=finding.severity,
        message=finding.message,
        fingerprint=finding.fingerprint,
        cwe=finding.cwe,
        category=category,
        reachability=reachability,
        priority=assign_priority(
            source="sast",
            severity=finding.severity,
            cvss=None,
            reachability=reachability,
            category=category,
        ),
    )


def enrich_secret(finding: GitleaksFinding) -> EnrichedFinding:
    reachability = ReachabilityResult(
        is_reachable=True,
        confidence="HIGH",
        method="same_file",
        evidence="Secret is present in the scanned tree / PR diff.",
    )
    return EnrichedFinding(
        source="secret",
        title=finding.rule_id,
        file_path=finding.file_path,
        line=finding.line,
        severity="ERROR",
        message=finding.description,
        fingerprint=f"{finding.file_path}:{finding.rule_id}:{finding.line}",
        category="Hardcoded Secret",
        reachability=reachability,
        priority="P1",
    )


def enrich_cve(finding: CVEVulnerability, reachability: ReachabilityResult) -> EnrichedFinding:
    severity = "ERROR" if (finding.severity_score or 0) >= 9.0 else "WARNING"
    if finding.severity_score is not None and finding.severity_score < 7.0:
        severity = "INFO"
    return EnrichedFinding(
        source="cve",
        title=finding.cve_id,
        file_path=finding.package_name,
        line=None,
        severity=severity,
        message=finding.summary or finding.cve_id,
        fingerprint=f"{finding.package_name}:{finding.installed_version}:{finding.cve_id}",
        cve_id=finding.cve_id,
        cvss=finding.severity_score,
        category="Vulnerable Dependency",
        reachability=reachability,
        priority=assign_priority(
            source="cve",
            severity=severity,
            cvss=finding.severity_score,
            reachability=reachability,
            category="Vulnerable Dependency",
        ),
    )
