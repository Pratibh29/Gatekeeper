from pathlib import Path

from mcp_server.tools.dep_parser import parse_dependency_file, parse_requirements_txt

TARGETS = Path(__file__).resolve().parents[1] / "test_targets"


def test_parse_requirements_txt():
    packages = parse_requirements_txt((TARGETS / "requirements.txt").read_text(encoding="utf-8"))
    names = {pkg["name"]: pkg["version"] for pkg in packages}
    assert names["flask"] == "1.21.3"
    assert names["requests"] == "2.28.0"
    assert all(pkg["ecosystem"] == "PyPI" for pkg in packages)


def test_parse_pyproject_toml():
    packages = parse_dependency_file(str(TARGETS / "sample_pyproject.toml"))
    names = {pkg["name"] for pkg in packages}
    assert "flask" in names
    assert "requests" in names
    assert "django" in names
    assert "python" not in names
