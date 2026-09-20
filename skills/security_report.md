# Security Finding Severity Rubric
## For Security Triage & Remediation Agent — Reporter Agent

This file is the Reporter Agent's SKILL.md: procedural knowledge for ranking
findings and formatting the single GitHub PR comment.

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

Hardcoded secrets in the PR diff are always Priority 1 (reachable by definition).

When evidence is missing, escalate rather than mark the finding safe. LOW
reachability never means "safe" — it means "manual review recommended".

### Report Format
One GitHub PR comment. Structure:

## 🔍 Security Scan Summary

| Severity | Finding | File | Line | Reachable |
|----------|---------|------|------|-----------|
| P1 | example | path | 1 | HIGH |

**Actions Required:** [list only P1 items]
**For Your Awareness:** [P2 count + brief list]
*N findings suppressed as unreachable — see full report in workflow artifacts*

If there are no P1 findings, start with ✅ PR PASSES.
If there are P1 findings, start with ❌ MERGE BLOCKED.
