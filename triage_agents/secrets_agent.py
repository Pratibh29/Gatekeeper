from __future__ import annotations

from agents import Agent, function_tool

from mcp_server.tools.gitleaks_tool import GitleaksResult, run_gitleaks
from triage_agents.base import GROQ_MODEL


@function_tool
def scan_with_gitleaks(repo_path: str) -> GitleaksResult:
    """Run Gitleaks; the underlying tool truncates secret values."""
    return run_gitleaks(repo_path)


SECRETS_AGENT = Agent(
    name="Secrets-Analyst",
    model=GROQ_MODEL,
    instructions=(
        "Run Gitleaks on the supplied repository and return every finding. "
        "Never attempt to recover or reproduce a secret value."
    ),
    tools=[scan_with_gitleaks],
)