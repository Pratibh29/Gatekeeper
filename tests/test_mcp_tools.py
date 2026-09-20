from pathlib import Path

from mcp_server.tools.gitleaks_tool import run_gitleaks
from mcp_server.tools.semgrep_tool import run_semgrep

TARGETS = Path(__file__).resolve().parents[1] / "test_targets"


def test_semgrep_finds_sql_injection():
    result = run_semgrep(str(TARGETS), rules="auto")
    sqli_findings = [f for f in result.findings if "sql" in f.check_id.lower()]
    assert len(sqli_findings) >= 1, "Should find SQL injection in test_targets/vulnerable.py"


def test_semgrep_finds_command_injection():
    result = run_semgrep(str(TARGETS), rules="auto")
    cmdi = [
        f
        for f in result.findings
        if "subprocess" in f.check_id.lower() or "shell" in f.message.lower()
    ]
    assert len(cmdi) >= 1


def test_gitleaks_finds_secret():
    result = run_gitleaks(str(TARGETS))
    assert result.findings
    assert all(len(f.match) <= 50 for f in result.findings)
