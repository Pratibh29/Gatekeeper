from __future__ import annotations

from pathlib import Path

from agents import Agent

from triage_agents.base import GROQ_MODEL
from triage_agents.models import CorrelationReport, EnrichedFinding

SKILL_CONTENT = (
    Path(__file__).resolve().parent.parent / "skills" / "security_report.md"
).read_text(encoding="utf-8")


def _row(finding: EnrichedFinding) -> str:
    location = finding.file_path.replace("|", "\\|")
    title = finding.title.replace("|", "\\|")
    return (
        f"| {finding.priority} | {title} | {location} | "
        f"{finding.line or '-'} | {finding.reachability.confidence} |"
    )


def render_report(report: CorrelationReport) -> str:
    """Render a bounded, deterministic GitHub comment from a correlation report."""
    lines = [
        "## Security Scan Summary",
        "",
        "**Status:** "
        + ("MERGE BLOCKED" if report.p1_findings or report.scan_failures else "PR PASSES"),
        "",
        "| Severity | Finding | File | Line | Reachable |",
        "|----------|---------|------|------|-----------|",
    ]
    findings = report.p1_findings + report.p2_findings + report.p3_findings
    lines.extend(_row(finding) for finding in findings)
    lines.extend(["", "**Actions Required:**"])
    lines.extend(f"- {finding.title}: {finding.message}" for finding in report.p1_findings)
    lines.extend(["", f"**For Your Awareness:** {len(report.p2_findings)} warning(s)"])
    if report.scan_failures:
        lines.extend(["", "**Scan Failures:**"])
        lines.extend(f"- {failure}" for failure in report.scan_failures)
    lines.extend([
        "",
        f"*{report.total_suppressed} findings suppressed as unreachable; manual review is recommended.*",
    ])
    return "\n".join(lines)[:3900]


REPORTER_AGENT = Agent(
    name="Security-Reporter",
    model=GROQ_MODEL,
    instructions=f"Render one concise GitHub security comment using this rubric:\n{SKILL_CONTENT}",
)