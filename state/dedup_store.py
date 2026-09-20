from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

DB_PATH = Path("data/dedup.db")


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS reported_findings (
            fingerprint TEXT NOT NULL,
            pr_number INTEGER NOT NULL,
            repo_full_name TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            PRIMARY KEY (fingerprint, pr_number, repo_full_name)
        )
        """
    )
    return connection


def init_db(db_path: Path = DB_PATH) -> None:
    connection = _connect(db_path)
    connection.commit()
    connection.close()


def _fingerprint(finding: object) -> str:
    if isinstance(finding, dict):
        value = finding.get("fingerprint")
    else:
        value = getattr(finding, "fingerprint", None)
    if not value:
        raise ValueError("Finding must provide a fingerprint")
    return str(value)


def filter_new_findings(
    findings: list[object],
    pr_number: int,
    repo: str,
    db_path: Path = DB_PATH,
) -> list[object]:
    connection = _connect(db_path)
    try:
        return [
            finding
            for finding in findings
            if connection.execute(
                "SELECT 1 FROM reported_findings WHERE fingerprint=? AND pr_number=? AND repo_full_name=?",
                (_fingerprint(finding), pr_number, repo),
            ).fetchone()
            is None
        ]
    finally:
        connection.close()


def record_findings(
    findings: list[object],
    pr_number: int,
    repo: str,
    db_path: Path = DB_PATH,
) -> None:
    connection = _connect(db_path)
    timestamp = datetime.now(UTC).isoformat()
    try:
        connection.executemany(
            "INSERT OR IGNORE INTO reported_findings "
            "(fingerprint, pr_number, repo_full_name, first_seen_at, status) VALUES (?, ?, ?, ?, ?)",
            [(_fingerprint(finding), pr_number, repo, timestamp, "open") for finding in findings],
        )
        connection.commit()
    finally:
        connection.close()