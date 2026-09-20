from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from mcp_server.tools.gitleaks_tool import register_gitleaks_tools
from mcp_server.tools.osv_tool import register_osv_tools
from mcp_server.tools.reachability_tool import register_reachability_tools
from mcp_server.tools.semgrep_tool import register_semgrep_tools

load_dotenv()


@asynccontextmanager
async def lifespan(_server: FastMCP):
    print("Security MCP server starting")
    yield


mcp = FastMCP("security-triage-mcp", lifespan=lifespan)

register_semgrep_tools(mcp)
register_gitleaks_tools(mcp)
register_osv_tools(mcp)
register_reachability_tools(mcp)


@mcp.resource("security://severity-rubric")
def get_severity_rubric() -> str:
    """The severity classification rubric used by the Reporter Agent."""
    rubric_path = Path(__file__).resolve().parent.parent / "skills" / "security_report.md"
    return rubric_path.read_text(encoding="utf-8")


if __name__ == "__main__":
    mcp.run()
