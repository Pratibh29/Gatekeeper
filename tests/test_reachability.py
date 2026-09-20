from pathlib import Path

from mcp_server.tools.reachability_tool import check_reachability


def test_same_file_is_high_confidence():
    result = check_reachability(
        finding_path="utils/helpers.py",
        finding_check_id="python.sql.injection",
        finding_line=12,
        changed_files=["utils/helpers.py", "app.py"],
    )
    assert result.is_reachable is True
    assert result.confidence == "HIGH"
    assert result.method == "same_file"


def test_direct_import_is_medium_confidence(tmp_path: Path):
    app = tmp_path / "app.py"
    app.write_text("from utils import helpers\nhelpers.dangerous_func()\n", encoding="utf-8")
    result = check_reachability(
        finding_path="utils/helpers.py",
        finding_check_id="python.lang.security.audit.dangerous",
        finding_line=4,
        changed_files=[str(app)],
    )
    assert result.is_reachable is True
    assert result.confidence == "MEDIUM"
    assert result.method == "direct_import"


def test_no_evidence_stays_low_and_does_not_claim_safe():
    result = check_reachability(
        finding_path="utils/helpers.py",
        finding_check_id="python.sql.injection",
        finding_line=12,
        changed_files=["README.md"],
    )
    assert result.is_reachable is False
    assert result.confidence == "LOW"
    assert result.method == "no_evidence_found"
    assert "manual review recommended" in result.evidence.lower()
