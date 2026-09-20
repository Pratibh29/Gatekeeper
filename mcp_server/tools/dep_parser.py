from __future__ import annotations

import re
import tomllib

_REQ_PATTERN = re.compile(r"([a-zA-Z0-9_\-\.]+)\s*[=~><!]+\s*([\d\.]+)")


def parse_requirements_txt(content: str) -> list[dict[str, str]]:
    packages: list[dict[str, str]] = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-")):
            continue
        match = _REQ_PATTERN.match(line)
        if match:
            packages.append({
                "name": match.group(1).lower(),
                "version": match.group(2),
                "ecosystem": "PyPI",
            })
    return packages


def parse_pyproject_toml(content: str) -> list[dict[str, str]]:
    """
    Parses pyproject.toml and extracts dependencies from either:
    - [project] dependencies  (PEP 621)
    - [tool.poetry.dependencies] (Poetry)
    Returns the same shape as parse_requirements_txt.
    """
    data = tomllib.loads(content)
    packages: list[dict[str, str]] = []

    pep621_deps = data.get("project", {}).get("dependencies", [])
    for dep in pep621_deps:
        match = _REQ_PATTERN.match(dep)
        if match:
            packages.append({
                "name": match.group(1).lower(),
                "version": match.group(2),
                "ecosystem": "PyPI",
            })

    poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    for name, version_spec in poetry_deps.items():
        if name.lower() == "python":
            continue
        if isinstance(version_spec, dict):
            version_spec = str(version_spec.get("version", ""))
        if isinstance(version_spec, str):
            version_match = re.search(r"([\d\.]+)", version_spec)
            if version_match:
                packages.append({
                    "name": name.lower(),
                    "version": version_match.group(1),
                    "ecosystem": "PyPI",
                })

    return packages


def parse_dependency_file(file_path: str) -> list[dict[str, str]]:
    """Auto-detects file type and calls the right parser."""
    with open(file_path, encoding="utf-8") as handle:
        content = handle.read()
    if file_path.endswith(".toml"):
        return parse_pyproject_toml(content)
    return parse_requirements_txt(content)
