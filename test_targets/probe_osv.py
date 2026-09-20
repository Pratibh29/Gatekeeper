"""Step 11: inspect OSV.dev single and batch response shapes."""
from __future__ import annotations

import json

import httpx


def main() -> None:
    single = httpx.post(
        "https://api.osv.dev/v1/query",
        json={"version": "1.21.3", "package": {"name": "flask", "ecosystem": "PyPI"}},
        timeout=30,
    )
    single.raise_for_status()
    print("=== /v1/query ===")
    print(json.dumps(single.json(), indent=2)[:4000])

    batch = httpx.post(
        "https://api.osv.dev/v1/querybatch",
        json={
            "queries": [
                {"version": "2.28.0", "package": {"name": "requests", "ecosystem": "PyPI"}},
                {"version": "1.21.3", "package": {"name": "flask", "ecosystem": "PyPI"}},
            ]
        },
        timeout=30,
    )
    batch.raise_for_status()
    print("=== /v1/querybatch ===")
    print(json.dumps(batch.json(), indent=2)[:4000])


if __name__ == "__main__":
    main()
