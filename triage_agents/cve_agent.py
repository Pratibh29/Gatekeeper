from __future__ import annotations

from agents import Agent, function_tool

from mcp_server.tools.osv_tool import CVEResult, check_dependencies_for_cves
from triage_agents.base import GROQ_MODEL


@function_tool
def scan_dependencies(dependency_file_path: str) -> CVEResult:
    """Query OSV.dev for all dependencies in a supported file."""
    return check_dependencies_for_cves(dependency_file_path)


CVE_AGENT = Agent(
    name="CVE-Analyst",
    model=GROQ_MODEL,
    instructions=(
        "Run the dependency scanner using its batch OSV.dev query. "
        "Return all vulnerabilities without making reachability decisions."
    ),
    tools=[scan_dependencies],
)