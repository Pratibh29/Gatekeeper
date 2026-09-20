"""
Tool: check_reachability
MVP meaning of reachable: does the PR diff contain a direct import or call
to the vulnerable module/file? This is grep + path matching, not a full call graph.

Logic:
- If finding_path is in changed_files → HIGH / same_file
- Else grep changed files for the module name from finding_path
  If found → MEDIUM / direct_import
- Else LOW / no_evidence_found (never assert safety)
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel


class ReachabilityResult(BaseModel):
    is_reachable: bool
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    evidence: str
    method: Literal["direct_import", "same_file", "no_evidence_found"]


def _normalize(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _module_needles(finding_path: str) -> list[str]:
    posix = _normalize(finding_path)
    path = Path(posix)
    stem = path.stem
    parent = "/".join(path.parent.parts)
    needles = [stem, f"import {stem}", f"from {stem}"]
    if parent and parent != ".":
        dotted = parent.replace("/", ".")
        needles.extend([dotted, f"from {dotted}", f"import {dotted}"])
    return needles


def check_reachability(
    finding_path: str,
    finding_check_id: str = "",
    finding_line: int = 0,
    changed_files: list[str] | None = None,
    repo_root: str | None = None,
) -> ReachabilityResult:
    changed_files = changed_files or []
    root = Path(repo_root).resolve() if repo_root else None
    finding = Path(finding_path)
    if root and finding.is_absolute():
        try:
            finding_path = str(finding.resolve().relative_to(root))
        except ValueError:
            pass
    normalized_changed = {_normalize(item) for item in changed_files}
    if _normalize(finding_path) in normalized_changed:
        return ReachabilityResult(
            is_reachable=True,
            confidence="HIGH",
            method="same_file",
            evidence=f"{finding_path} is in the PR diff (line {finding_line or '?'}).",
        )

    needles = _module_needles(finding_path)
    for changed in changed_files:
        path = Path(changed)
        if root and not path.is_absolute():
            path = root / path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(needle in text for needle in needles):
            return ReachabilityResult(
                is_reachable=True,
                confidence="MEDIUM",
                method="direct_import",
                evidence=(
                    f"Changed file {changed} imports or references the module from "
                    f"{finding_path} ({finding_check_id or 'finding'})."
                ),
            )

    return ReachabilityResult(
        is_reachable=False,
        confidence="LOW",
        method="no_evidence_found",
        evidence="No direct import found; manual review recommended",
    )


def register_reachability_tools(mcp):
    @mcp.tool()
    def check_reachability_tool(
        finding_path: str,
        finding_check_id: str = "",
        finding_line: int = 0,
        changed_files: list[str] | None = None,
    ) -> ReachabilityResult:
        """Assess whether a finding looks reachable from the PR diff."""
        return check_reachability(finding_path, finding_check_id, finding_line, changed_files)

    return check_reachability_tool
