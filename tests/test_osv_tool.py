from pathlib import Path

from mcp_server.tools.osv_tool import check_dependencies_for_cves


def test_osv_finds_flask_cves():
    requirements = Path(__file__).resolve().parents[1] / "test_targets" / "requirements.txt"
    result = check_dependencies_for_cves(str(requirements))
    assert result.packages_checked >= 2
    assert any(v.package_name == "flask" for v in result.vulnerabilities)
