from __future__ import annotations

from agents import Agent, function_tool

from mcp_server.tools.semgrep_tool import SemgrepResult, run_semgrep
from triage_agents.base import GROQ_MODEL


@function_tool
def scan_with_semgrep(repo_path: str, rules: str = "p/security-audit") -> SemgrepResult:
    """Run Semgrep and return every structured finding."""
    return run_semgrep(repo_path, rules)


SAST_AGENT = Agent(
    name="SAST-Analyst",
    model=GROQ_MODEL,
    instructions=(
        "Run the Semgrep tool on the supplied repository and return all findings. "
        "Do not interpret, suppress, or correlate findings."
    ),
    tools=[scan_with_semgrep],
)