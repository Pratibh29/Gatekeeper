# Semgrep / Gitleaks / OSV fields used by the MCP tools
# Captured while running Steps 8–11 against test_targets/

## Semgrep JSON (`results[]`)
- `check_id` — rule that fired
- `path` — file path
- `start.line` — line number
- `extra.message` — human-readable description
- `extra.severity` — ERROR / WARNING / INFO
- `extra.metadata.cwe` — CWE identifier (often a list)
- `extra.fingerprint` — stable id for dedup when present

`--config=auto` found SQL injection and command injection in `vulnerable.py`.
`p/security-audit`, `p/python`, and `p/owasp-top-ten` found command injection only
on this fixture. MVP default remains `p/security-audit`; tests that need SQLi
pass `rules="auto"`.

## Gitleaks JSON (`[]`)
- `RuleID` — secret type
- `Match` — matched text (truncate to 50 chars in the tool)
- `File` — file path
- `StartLine` — line number
- `Description` — human-readable
- `Tags` — severity/category tags (may be empty)

## OSV.dev
Single `/v1/query` returns `vulns[].id`, `summary`, `severity`, `affected[].ranges`.
Batch `/v1/querybatch` returns parallel `results[].vulns[]` with only `id` + `modified`.
The CVE tool zips batch hits back to packages, then calls `/v1/query` for details.
