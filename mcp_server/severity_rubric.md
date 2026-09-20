# Security Finding Severity Rubric
## For Security Triage & Remediation Agent — Reporter Agent

### Priority 1: BLOCK MERGE (post as Required Review)
Conditions: ALL of the following must be true
- Severity: ERROR (Semgrep) OR CVSS ≥ 9.0 (CVE)
- Reachability: HIGH or MEDIUM confidence
- Category: Any of: SQL Injection, Command Injection, Hardcoded Secret, RCE, Auth Bypass

### Priority 2: WARN (post as comment, do not block)
Conditions:
- Severity: ERROR + LOW reachability confidence, OR
- Severity: WARNING + HIGH/MEDIUM reachability, OR
- CVSS 7.0-8.9 (any reachability)

### Priority 3: INFO (include in summary, do not block or warn individually)
Conditions:
- Severity: WARNING or INFO + LOW reachability
- CVSS < 7.0

### Report Format
One GitHub PR comment. Structure:
## 🔍 Security Scan Summary

| Severity | Finding | File | Line | Reachable |
|----------|---------|------|------|-----------|

**Actions Required:** [list only P1 items]
**For Your Awareness:** [P2 count + brief list]
*N findings suppressed as unreachable — see full report in workflow artifacts*
