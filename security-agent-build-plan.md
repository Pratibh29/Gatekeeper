# Security Finding Triage & Remediation Agent
## Complete Build Plan — Steps, Resources, Tools, Day-by-Day

---

## Before anything else: understand what you're building

You are building a **multi-agent security review pipeline** that plugs into GitHub pull requests. When a PR is opened, five agents kick in:

1. **SAST Agent** → runs Semgrep (finds code vulnerabilities)
2. **Secret-Scan Agent** → runs Gitleaks (finds exposed secrets/API keys)
3. **CVE Agent** → queries OSV.dev (finds vulnerable dependencies)
4. **Correlator Agent** → for every finding, checks if the vulnerable code is actually *reachable and used* (noise reduction — the entire value-add)
5. **Reporter Agent** → produces one clean PR comment instead of three bot spams

The system posts a single, ranked PR comment and blocks the merge only for CRITICAL + confirmed-reachable findings.

### What it will look like in your repo

```
security-triage-agent/
├── README.md                     ← architecture diagram lives here
├── .env.example
├── docker-compose.yml
├── pyproject.toml                ← single dependency file
│
├── mcp_server/                   ← YOUR custom MCP server
│   ├── server.py
│   └── tools/
│       ├── dep_parser.py         ← parses requirements.txt AND pyproject.toml
│       ├── semgrep_tool.py
│       ├── gitleaks_tool.py
│       ├── osv_tool.py
│       └── reachability_tool.py
│
├── agents/                       ← the 5 agents
│   ├── base.py                   ← Groq client config (build this FIRST, all agents depend on it)
│   ├── orchestrator.py           ← parallel fan-out logic
│   ├── sast_agent.py
│   ├── secrets_agent.py
│   ├── cve_agent.py
│   ├── correlator_agent.py
│   └── reporter_agent.py
│
├── skills/
│   └── security_report.md        ← SKILL.md for report format
│
├── state/
│   └── dedup_store.py            ← SQLite, prevents duplicate alerts
│
├── webhook/
│   ├── app.py                    ← FastAPI receives GitHub webhooks
│   ├── repo_cloner.py            ← clones PR head commit to temp dir
│   ├── get_pr_files.py           ← fetches changed files list from GitHub API
│   └── github_client.py          ← posts PR comments and check runs
│
├── observability/
│   └── tracing.py                ← Langfuse traces every agent call
│
└── tests/
    ├── test_mcp_tools.py
    ├── test_agents.py
    └── test_dedup.py
```

---

## Tool Budget — Read This First, It Changes How You Work

This is the most important section for making free tools last the whole build.

### GitHub Copilot Free (50 chat + 2,000 completions/month)
| What to use it FOR | What NOT to use it for |
|---|---|
| Tab completions while typing (passive, cheap) | Long "generate this whole file" prompts |
| "Explain this Semgrep JSON output format" | Designing architecture (think yourself) |
| Fixing a specific 5-line function | Asking it to write agents from scratch |
| Autocomplete test cases | Anything Cursor can do instead |

**Strategy:** Copilot completions are passive (they fire as you type). Use them constantly. Save the 50 chat slots for quick lookups you'd otherwise Google — "what is the shape of OSV.dev's JSON response?", "how do I parse a GitHub webhook payload?"

### Cursor Hobby (limited agent requests — ~50/month estimated)
| What to use it FOR | What NOT to use it for |
|---|---|
| Generating entire new files from a description | Editing files you can edit manually |
| Refactoring orchestrator.py when the whole structure needs changing | Small bug fixes |
| Writing the MCP server boilerplate from scratch | Writing docstrings |
| Writing the FastAPI webhook boilerplate | Running terminal commands |

**Strategy:** Use Cursor Agent mode (Ctrl+Shift+L or the chat panel) for "generate me this whole file based on this spec." Use @codebase context to give it full context before asking. Each agent request is precious — write a precise multi-paragraph brief before triggering it, so you get it right in one shot. For regular coding, just use the editor normally with tab completions.

### Groq Free Tier (the agent's RUNTIME brain — completely separate from Cursor/Copilot)
- **Model:** `llama-3.3-70b-versatile` (strongest free reasoning model on Groq)
- **Limits:** ~14,400 requests/day, 30 requests/min — plenty for this project's needs
- **Get your key:** https://console.groq.com → sign up free, no card required
- This is what your agents call at *runtime*, in your Python code, via the Groq SDK. Cursor and Copilot help you *write* that Python code. They are completely different things.

### Gemini Flash (backup free LLM)
- If Groq is down or rate-limited: `gemini-1.5-flash` via Google AI Studio
- Free tier: 15 req/min, 1500 req/day — https://aistudio.google.com/app/apikey

### Langfuse (observability — fully free self-hosted)
- Runs in Docker, zero cost
- Shows you traces of every agent call, tool call, and LLM prompt/response
- This is what makes your project look "production-aware" to an interviewer

---

## Full Resource List — What to Read, When, and in What Order

Do not read everything up front. Read exactly what the phase needs.

| When | Resource | URL | Time needed |
|---|---|---|---|
| Phase 0 | MCP official spec quickstart | https://modelcontextprotocol.io/quickstart/server | 30 min |
| Phase 0 | MCP Python SDK README | https://github.com/modelcontextprotocol/python-sdk | 20 min |
| Phase 0 | Groq Python SDK | https://github.com/groq/groq-python | 10 min |
| Phase 1 | Semgrep "Getting started" | https://semgrep.dev/docs/getting-started/quickstart/ | 30 min |
| Phase 1 | Semgrep JSON output format | https://semgrep.dev/docs/cli-reference#exit-codes-and-output | 15 min |
| Phase 1 | Gitleaks README | https://github.com/gitleaks/gitleaks | 20 min |
| Phase 1 | OSV.dev API docs | https://google.github.io/osv.dev/api/ | 15 min |
| Phase 2 | MCP tools spec (exactly how to define a tool) | https://modelcontextprotocol.io/docs/concepts/tools | 20 min |
| Phase 2 | MCP resources spec | https://modelcontextprotocol.io/docs/concepts/resources | 15 min |
| Phase 3 | OpenAI Agents SDK docs (you'll use this for orchestration) | https://openai.github.io/openai-agents-python/ | 45 min |
| Phase 3 | OpenAI Agents SDK handoffs | https://openai.github.io/openai-agents-python/handoffs/ | 20 min |
| Phase 4 | FastAPI "First Steps" | https://fastapi.tiangolo.com/tutorial/first-steps/ | 20 min |
| Phase 4 | GitHub Webhooks docs | https://docs.github.com/en/webhooks/webhook-events-and-payloads | 15 min |
| Phase 4 | GitHub REST API — PR comments | https://docs.github.com/en/rest/issues/comments | 10 min |
| Phase 5 | Langfuse Python SDK | https://langfuse.com/docs/sdk/python/sdk-v3 | 20 min |
| Phase 6 | Python unittest / pytest basics | https://docs.pytest.org/en/stable/getting-started.html | 20 min |
| Phase 6 | Docker Compose v3 reference | https://docs.docker.com/compose/compose-file/compose-file-v3/ | 15 min |

**Do NOT read:**
- LangGraph (not needed for this project — sequential+parallel is simpler with the OpenAI Agents SDK)
- CrewAI (adds complexity you don't need at this scale)
- Any AWS/Azure/GCP docs (zero cloud needed)

---

## Phase 0 — Environment Setup
**Time: 2 days | Goal: Everything installed, "hello world" from each tool**

### Day 1 — Core tools installed and verified

#### Step 1: Python environment
```bash
# Install Python 3.11+ if not already installed
# macOS: brew install python@3.11
# Ubuntu: sudo apt install python3.11 python3.11-venv

# Create your project
mkdir security-triage-agent && cd security-triage-agent
python3.11 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Verify
python --version  # should say 3.11.x
```

#### Step 2: Install all dependencies at once
Create `pyproject.toml` first (Cursor will help you fill this):
```toml
[project]
name = "security-triage-agent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.0.0",              # MCP Python SDK
    "openai-agents>=0.1.0",    # OpenAI Agents SDK for orchestration
    "groq>=0.11.0",            # Groq LLM client
    "python-dotenv>=1.0.0",    # Load .env file into os.environ
    "fastapi>=0.115.0",        # Webhook server
    "uvicorn>=0.30.0",         # ASGI server for FastAPI
    "httpx>=0.27.0",           # Async HTTP client (OSV.dev calls)
    "pygithub>=2.3.0",         # GitHub API client
    "langfuse>=2.0.0",         # Observability
    "pydantic>=2.0.0",         # Structured outputs
    "deepeval>=1.0.0",         # Evaluation harness
]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "pytest-cov", "ruff", "mypy"]
```

```bash
pip install -e ".[dev]"
```

#### Step 3: Install security scanner CLIs
```bash
# Semgrep (SAST scanner)
pip install semgrep
semgrep --version   # verify

# Gitleaks (secret scanner) — download the binary
# macOS:
brew install gitleaks
# Linux (Ubuntu):
wget https://github.com/gitleaks/gitleaks/releases/latest/download/gitleaks_linux_x64.tar.gz
tar -xzf gitleaks_linux_x64.tar.gz
sudo mv gitleaks /usr/local/bin/
# Verify:
gitleaks version
```

#### Step 4: Set up API keys
```bash
# Create .env file (this is NEVER committed to git)
cat > .env << 'EOF'
# LLM Runtime Brain
GROQ_API_KEY=your_groq_key_here

# GitHub Integration
GITHUB_TOKEN=your_github_pat_here
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here

# Observability (Langfuse — get from localhost after Docker setup)
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=http://localhost:3000
EOF

# Create .env.example (this IS committed)
cat > .env.example << 'EOF'
GROQ_API_KEY=your_groq_key_here
GITHUB_TOKEN=ghp_...
GITHUB_WEBHOOK_SECRET=generate_with_openssl_rand_hex_32
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=http://localhost:3000
EOF

# Add .env to gitignore immediately
echo ".env" >> .gitignore
echo ".venv/" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore
```

**Get your keys:**
- Groq: https://console.groq.com → sign up → API Keys → Create
- GitHub PAT: GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic) → generate with `repo`, `pull_requests` scopes

#### Step 5: Verify Groq works (your first LLM call)
```python
# test_groq.py — run this once, then delete
from groq import Groq
import os
from dotenv import load_dotenv
load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "Reply with exactly: GROQ_WORKS"}],
    max_tokens=10
)
print(response.choices[0].message.content)  # Should print GROQ_WORKS
```

```bash
python test_groq.py
```

### Day 2 — MCP SDK hello world + Langfuse Docker

#### Step 6: Run MCP hello world (the official quickstart)
Read this first: https://modelcontextprotocol.io/quickstart/server

Then write your first toy MCP server:
```python
# test_mcp_hello.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("hello-test")

@mcp.tool()
def say_hello(name: str) -> str:
    """Says hello to someone."""
    return f"Hello, {name}! MCP is working."

if __name__ == "__main__":
    mcp.run()
```

```bash
python test_mcp_hello.py
# You should see: Starting MCP server 'hello-test'
```

This proves MCP is installed and working before you build anything real.

#### Step 7: Start Langfuse via Docker (observability layer)
```bash
# Create docker-compose.yml for Langfuse only (you'll add your app later)
cat > docker-compose.langfuse.yml << 'EOF'
version: "3"
services:
  langfuse-server:
    image: langfuse/langfuse:latest
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: "postgresql://langfuse:langfuse@langfuse-db:5432/langfuse"
      NEXTAUTH_SECRET: "supersecretlangfuse"
      NEXTAUTH_URL: "http://localhost:3000"
      SALT: "supersalt"
    depends_on:
      - langfuse-db

  langfuse-db:
    image: postgres:15
    environment:
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: langfuse
      POSTGRES_DB: langfuse
    volumes:
      - langfuse_db:/var/lib/postgresql/data

volumes:
  langfuse_db:
EOF

docker compose -f docker-compose.langfuse.yml up -d
```

- Open http://localhost:3000 → sign up (local only)
- Copy your secret and public key from Settings → API Keys into your `.env` file

**Phase 0 done when:**
- [ ] `semgrep --version` works
- [ ] `gitleaks version` works
- [ ] `python test_groq.py` prints `GROQ_WORKS`
- [ ] MCP hello world server starts without errors
- [ ] Langfuse opens at http://localhost:3000

---

## Phase 1 — Learn the Tools You'll Wrap
**Time: 3 days | Goal: Understand Semgrep, Gitleaks, and OSV.dev output formats before coding**

This phase has no coding. It is research. Understanding the output formats of your tools *before* writing parsers is what separates a working project from a broken one.

### Day 3 — Semgrep

#### Step 8: Run Semgrep manually on a vulnerable target
```bash
# Create a deliberately vulnerable Python file to test against
mkdir test_targets && cat > test_targets/vulnerable.py << 'EOF'
import subprocess
import sqlite3

def run_command(user_input):
    # VULNERABILITY: command injection
    subprocess.run(f"ls {user_input}", shell=True)

def query_db(username, password):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # VULNERABILITY: SQL injection
    cursor.execute(f"SELECT * FROM users WHERE user='{username}' AND pass='{password}'")

SECRET_KEY = "hardcoded-super-secret-key-12345"  # VULNERABILITY: hardcoded secret
EOF

# Run Semgrep with JSON output (this is what your agent will parse)
semgrep --config=auto --json test_targets/vulnerable.py > test_targets/semgrep_output.json
cat test_targets/semgrep_output.json | python -m json.tool
```

**Now study the JSON structure carefully.** The fields you care about:
- `results[].check_id` — the rule that fired
- `results[].path` — the file
- `results[].start.line` — line number
- `results[].extra.message` — human-readable description
- `results[].extra.severity` — ERROR / WARNING / INFO
- `results[].extra.metadata.cwe` — the CWE identifier

Write these down. Your `semgrep_tool.py` will parse exactly this shape.

#### Step 9: Learn Semgrep rule sets available for free
```bash
# The registry rules (free)
semgrep --config=p/security-audit --json test_targets/vulnerable.py

# Python-specific rules
semgrep --config=p/python --json test_targets/vulnerable.py

# OWASP Top 10
semgrep --config=p/owasp-top-ten --json test_targets/vulnerable.py
```

**Resource to read:** https://semgrep.dev/explore — browse available free rule packs. For MVP, use `p/security-audit` — it's comprehensive and well-maintained.

### Day 4 — Gitleaks + OSV.dev

#### Step 10: Run Gitleaks manually
```bash
# Create a file with a fake secret for testing
cat > test_targets/config_with_secret.py << 'EOF'
AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
STRIPE_KEY = "sk_live_abcdefghij1234567890"
EOF

# Run gitleaks on the test directory (JSON output)
gitleaks detect --source test_targets/ --report-format json --report-path test_targets/gitleaks_output.json
cat test_targets/gitleaks_output.json | python -m json.tool
```

**Study the JSON structure:**
- `[].RuleID` — which secret type was detected
- `[].Match` — the matched text (truncated)
- `[].File` — the file path
- `[].StartLine` — line number
- `[].Description` — human-readable
- `[].Tags` — severity tags

#### Step 11: Call OSV.dev API manually
```python
# test_osv.py — run this to understand the response format
import httpx
import json

# Query for a known vulnerable package version
response = httpx.post(
    "https://api.osv.dev/v1/query",
    json={
        "version": "1.21.3",
        "package": {
            "name": "flask",
            "ecosystem": "PyPI"
        }
    }
)
data = response.json()
print(json.dumps(data, indent=2))
```

**Study the response:**
- `vulns[].id` — CVE ID (e.g., CVE-2023-XXXXX)
- `vulns[].summary` — what the vulnerability is
- `vulns[].severity[].score` — CVSS score
- `vulns[].affected[].ranges[]` — version ranges affected

Also test the **batch endpoint** (important for when you check all dependencies at once):
```python
# Batch query — much more efficient than one-at-a-time
response = httpx.post(
    "https://api.osv.dev/v1/querybatch",
    json={
        "queries": [
            {"version": "2.28.0", "package": {"name": "requests", "ecosystem": "PyPI"}},
            {"version": "1.21.3", "package": {"name": "flask", "ecosystem": "PyPI"}}
        ]
    }
)
print(json.dumps(response.json(), indent=2))
```

### Day 5 — Parse your project's dependencies

#### Step 12: Write a requirements.txt parser
Your CVE agent needs to extract package names and versions from whatever dependency file the PR changes:
```bash
# What formats you need to support for MVP:
# 1. requirements.txt  (Python)
# 2. package.json      (Node — stretch goal, skip for MVP if short on time)
# 3. pyproject.toml    (Python modern)
```

Write a small utility in `mcp_server/tools/dep_parser.py` that:
1. Reads a requirements.txt file
2. Returns `[{"name": "flask", "version": "1.21.3", "ecosystem": "PyPI"}, ...]`

Use regex for requirements.txt — it's simpler and more reliable than a parsing library for this use case:
```python
# mcp_server/tools/dep_parser.py
import re
import tomllib  # built-in since Python 3.11 — no extra install needed

def parse_requirements_txt(content: str) -> list[dict]:
    packages = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Match: package==version, package>=version, package~=version
        match = re.match(r"([a-zA-Z0-9_\-\.]+)\s*[=~><!]+\s*([\d\.]+)", line)
        if match:
            packages.append({
                "name": match.group(1).lower(),
                "version": match.group(2),
                "ecosystem": "PyPI"
            })
    return packages


def parse_pyproject_toml(content: str) -> list[dict]:
    """
    Parses pyproject.toml and extracts dependencies from either:
    - [project] dependencies  (PEP 621 standard — what this project uses)
    - [tool.poetry.dependencies] (Poetry format — common alternative)
    Returns the same shape as parse_requirements_txt.
    """
    data = tomllib.loads(content)
    packages = []

    # PEP 621 format: [project] dependencies = ["flask>=2.0", "requests==2.28.0"]
    pep621_deps = data.get("project", {}).get("dependencies", [])
    for dep in pep621_deps:
        match = re.match(r"([a-zA-Z0-9_\-\.]+)\s*[=~><!]+\s*([\d\.]+)", dep)
        if match:
            packages.append({
                "name": match.group(1).lower(),
                "version": match.group(2),
                "ecosystem": "PyPI"
            })

    # Poetry format: [tool.poetry.dependencies] flask = "^2.0"
    poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    for name, version_spec in poetry_deps.items():
        if name.lower() == "python":
            continue  # skip the Python version constraint
        if isinstance(version_spec, str):
            version_match = re.search(r"([\d\.]+)", version_spec)
            if version_match:
                packages.append({
                    "name": name.lower(),
                    "version": version_match.group(1),
                    "ecosystem": "PyPI"
                })

    return packages


def parse_dependency_file(file_path: str) -> list[dict]:
    """
    Auto-detects file type and calls the right parser.
    Call this from osv_tool.py — it handles both formats transparently.
    """
    with open(file_path, "r") as f:
        content = f.read()
    if file_path.endswith("pyproject.toml"):
        return parse_pyproject_toml(content)
    # Default: treat as requirements.txt
    return parse_requirements_txt(content)
```

> **Note:** `tomllib` is built into Python 3.11+ — no extra package needed. This is why `requires-python = ">=3.11"` in your `pyproject.toml` matters. Your `osv_tool.py` should call `parse_dependency_file()` rather than `parse_requirements_txt()` directly — it handles both formats automatically.

**Phase 1 done when:**
- [ ] You can read and explain every field in the Semgrep JSON output
- [ ] You can read and explain every field in the Gitleaks JSON output
- [ ] You understand the OSV.dev batch query format
- [ ] You can parse a requirements.txt into a list of packages

---

## Phase 2 — Build the MCP Server
**Time: 4 days | Goal: A working MCP server with all 4 tools**

### This is where you use Cursor most heavily.

Before opening Cursor: **write your spec first.** A vague prompt gives vague code.

**Write this spec in a comment block at the top of each file before asking Cursor to generate it.** This is the skill that makes free-tier Cursor worthwhile — you spend 10 minutes writing a precise spec, Cursor generates 80% correct code, you spend 10 minutes fixing the rest.

### Day 6 — MCP server scaffold + Semgrep tool

#### Step 13: Create the MCP server entry point

**Before opening Cursor, read the official MCP tool definition spec:** https://modelcontextprotocol.io/docs/concepts/tools

Then use Cursor (Agent mode) with this exact prompt:

```
Create mcp_server/server.py using the FastMCP class from the mcp.server.fastmcp module.

Requirements:
- Server name: "security-triage-mcp"
- Import and register tools from: semgrep_tool, gitleaks_tool, osv_tool, reachability_tool
- Load .env file using python-dotenv
- Add a lifespan context that logs "Security MCP server starting" on startup
- The server should run with mcp.run() at the bottom of the file

Use Python 3.11+ type hints everywhere. No legacy typing module imports.
```

#### Step 14: Build semgrep_tool.py

Write the spec comment first:
```
Tool: run_semgrep
Input: repo_path (str), rules (str = "p/security-audit")
Output: SemgrepResult (Pydantic model with fields: findings list, scan_time_ms, rule_count)

SemgrepFinding fields: check_id, path, line, severity (Literal["ERROR","WARNING","INFO"]),
message, cwe (str | None), fingerprint (str — for dedup)

Runs: semgrep --config={rules} --json {repo_path}
Captures stdout, parses JSON, maps to Pydantic models
On non-zero exit code: if exit code == 1, it found issues (not an error) — Semgrep exits 1 when findings exist
On other non-zero: raise ToolError with stderr content
Timeout: 120 seconds
```

Now use Cursor Agent with this spec. The code it generates should look roughly like:

```python
# mcp_server/tools/semgrep_tool.py
import subprocess
import json
import time
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP

class SemgrepFinding(BaseModel):
    check_id: str
    path: str
    line: int
    severity: str
    message: str
    cwe: str | None = None
    fingerprint: str

class SemgrepResult(BaseModel):
    findings: list[SemgrepFinding]
    scan_time_ms: int
    rule_count: int

def register_semgrep_tools(mcp: FastMCP):
    @mcp.tool()
    def run_semgrep(repo_path: str, rules: str = "p/security-audit") -> SemgrepResult:
        """
        Runs Semgrep static analysis on a code repository.
        Returns structured findings with severity and CWE classification.
        Exit code 1 from Semgrep means findings were found (not an error).
        """
        start = time.time()
        result = subprocess.run(
            ["semgrep", "--config", rules, "--json", repo_path],
            capture_output=True,
            text=True,
            timeout=120
        )
        # Semgrep exits 1 when findings exist — that's not an error
        if result.returncode not in (0, 1):
            raise RuntimeError(f"Semgrep failed: {result.stderr[:500]}")

        data = json.loads(result.stdout)
        findings = []
        for r in data.get("results", []):
            findings.append(SemgrepFinding(
                check_id=r["check_id"],
                path=r["path"],
                line=r["start"]["line"],
                severity=r["extra"].get("severity", "WARNING"),
                message=r["extra"].get("message", ""),
                cwe=r["extra"].get("metadata", {}).get("cwe", [None])[0],
                fingerprint=r.get("extra", {}).get("fingerprint", f"{r['check_id']}:{r['path']}:{r['start']['line']}")
            ))

        elapsed_ms = int((time.time() - start) * 1000)
        return SemgrepResult(
            findings=findings,
            scan_time_ms=elapsed_ms,
            rule_count=len(data.get("rules", []))
        )
```

#### Step 15: Test semgrep_tool in isolation (before wiring to MCP)
```python
# tests/test_mcp_tools.py
import pytest
from mcp_server.tools.semgrep_tool import run_semgrep  # import the inner function

def test_semgrep_finds_sql_injection():
    result = run_semgrep("test_targets/")
    sqli_findings = [f for f in result.findings if "sql" in f.check_id.lower()]
    assert len(sqli_findings) >= 1, "Should find SQL injection in test_targets/vulnerable.py"

def test_semgrep_finds_command_injection():
    result = run_semgrep("test_targets/")
    cmdi = [f for f in result.findings if "subprocess" in f.check_id.lower() or "shell" in f.message.lower()]
    assert len(cmdi) >= 1
```

```bash
pytest tests/test_mcp_tools.py::test_semgrep_finds_sql_injection -v
```

**Do not move on until this test passes.**

### Day 7 — Gitleaks tool + OSV tool

#### Step 16: Build gitleaks_tool.py (same pattern as semgrep)

**Spec for Cursor:**
```
Tool: run_gitleaks
Input: repo_path (str)
Output: GitleaksResult (Pydantic: findings list, scan_time_ms)

GitleaksFinding: rule_id, match (str — first 50 chars only, never log full secret),
file_path, line, description, tags (list[str])

Command: gitleaks detect --source {repo_path} --report-format json --report-path /tmp/gitleaks_report.json --no-git
Read /tmp/gitleaks_report.json after running.
Exit code 1 means secrets found (not an error, like Semgrep).
IMPORTANT: truncate the match field to 50 chars — never store full secrets in logs.
```

The critical safety detail: **never log the full secret value.** Truncate it. This is a security property worth highlighting in your README and in an interview.

#### Step 17: Build osv_tool.py

**Spec for Cursor:**
```
Tool: check_dependencies_for_cves
Input: requirements_file_path (str)
Output: CVEResult (Pydantic: vulnerabilities list, packages_checked int, scan_time_ms)

CVEVulnerability: package_name, installed_version, cve_id, summary,
severity_score (float | None), fixed_in (list[str])

Steps:
1. Read and parse requirements file using parse_requirements_txt utility
2. Build OSV.dev batch query body
3. POST to https://api.osv.dev/v1/querybatch using httpx (async NOT needed — sync is fine for MVP)
4. Map response into CVEVulnerability models
5. Skip entries with no vulnerabilities
Timeout: 30 seconds
```

Write tests for both tools immediately after writing each one, using the same pattern as the Semgrep test.

### Day 8 — Reachability tool (your main differentiator)

This is the hardest tool to build correctly. Read this section carefully before touching Cursor.

#### Step 18: Understand what "reachability" means at MVP scope

Full call-graph analysis (like what a proper SAST engine does) is a compiler-theory problem. You cannot build that in a week. You don't need to.

**MVP definition of "reachable":** Does the PR diff contain a direct import or call to the vulnerable function/package?

Example: Semgrep flags `dangerous_func()` in `utils/helpers.py`. Is it reachable? Check: does any file in the PR's changed files call `dangerous_func` or import the module containing it?

This is grep + light AST, not full call-graph analysis. **Say this explicitly in your README.** Intellectual honesty about limitations is a positive signal in a security context.

**Spec for Cursor:**
```
Tool: check_reachability
Input:
  - finding_path (str) — file containing the vulnerability
  - finding_check_id (str) — the Semgrep rule ID
  - finding_line (int) — line number
  - changed_files (list[str]) — files changed in the PR

Output: ReachabilityResult (Pydantic):
  - is_reachable (bool)
  - confidence (Literal["HIGH", "MEDIUM", "LOW"])
  - evidence (str) — one sentence explaining why/why not
  - method (str) — "direct_import", "same_file", "no_evidence_found"

Logic:
  - If finding_path is in changed_files → is_reachable=True, confidence=HIGH, method="same_file"
  - Else: grep the changed files for the module name extracted from finding_path
    (e.g., finding in "utils/helpers.py" → grep for "helpers" or "from utils")
    If found → is_reachable=True, confidence=MEDIUM, method="direct_import"
  - Else: is_reachable=False, confidence=LOW, method="no_evidence_found"

IMPORTANT: When confidence is LOW, evidence must say "No direct import found;
manual review recommended" — never assert something is safe, only
assert things are unsafe.
```

This fail-safe default (LOW confidence never asserts safety) is a security-critical design decision worth explaining in an interview: "My system will never tell you something is safe when it isn't sure. It defaults to 'needs review' when evidence is absent."

### Day 9 — Resources + MCP server wiring

#### Step 19: Create the severity_rubric.md resource

This is your SKILL.md for the reporter agent. It encodes how to rank findings:

```markdown
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
```

#### Step 20: Wire everything into server.py

Use Cursor to update server.py to register all four tools and expose the severity_rubric as a resource:

```python
# In mcp_server/server.py — ask Cursor to add this
@mcp.resource("security://severity-rubric")
def get_severity_rubric() -> str:
    """The severity classification rubric used by the Reporter Agent."""
    rubric_path = Path(__file__).parent.parent / "skills" / "security_report.md"
    return rubric_path.read_text()
```

**Phase 2 done when:**
- [ ] `python mcp_server/server.py` starts without errors
- [ ] All 4 tools return valid Pydantic models when called directly (not via MCP yet)
- [ ] Tests pass for at least semgrep and gitleaks tools
- [ ] severity_rubric.md is written and reviewed

---

## Phase 3 — Build the 5 Agents
**Time: 5 days | Goal: Each agent runs independently, produces correct output**

### Why OpenAI Agents SDK (not LangGraph, not CrewAI)

For this project's shape — 3 parallel specialists → 1 correlator → 1 reporter — the OpenAI Agents SDK is the right tool because:
1. Its `Runner.run()` handles the LLM loop natively
2. Its `handoff()` primitive is exactly what you need between correlator and reporter
3. It's the simplest framework that demonstrates real agent concepts
4. It works with Groq via an OpenAI-compatible base URL (important — Groq is not "OpenAI" but exposes an OpenAI-compatible API)

**Groq + OpenAI Agents SDK compatibility setup:**
```python
# agents/base.py — create this before building any agent
from agents import set_default_openai_client
from openai import AsyncOpenAI
import os

def configure_groq_client():
    """Configure the Agents SDK to use Groq's OpenAI-compatible API."""
    client = AsyncOpenAI(
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1"
    )
    set_default_openai_client(client)
    return client

# Call this once at startup before any agent runs
GROQ_MODEL = "llama-3.3-70b-versatile"
```

### Day 10 — SAST Agent + Secrets Agent

#### Step 21: Build the SAST Agent

Read the OpenAI Agents SDK docs first: https://openai.github.io/openai-agents-python/

**Key concept:** An Agent has:
- `name` — identifier
- `instructions` — the system prompt (this is where your reasoning lives)
- `tools` — functions it can call

```python
# agents/sast_agent.py
from agents import Agent, function_tool
from mcp_server.tools.semgrep_tool import run_semgrep, SemgrepResult
from agents.base import GROQ_MODEL

@function_tool
def scan_with_semgrep(repo_path: str, rules: str = "p/security-audit") -> SemgrepResult:
    """Run Semgrep SAST scan on the repository."""
    return run_semgrep(repo_path, rules)

SAST_AGENT = Agent(
    name="SAST-Analyst",
    model=GROQ_MODEL,
    instructions="""You are a static analysis security expert.
    
Your job: Run Semgrep on the provided repository path and return the raw findings.

Rules:
- Always use the 'p/security-audit' ruleset unless told otherwise
- Return ALL findings, not just high-severity ones
- Do NOT attempt to interpret or correlate findings — that is not your job
- Format your final response as: SAST_SCAN_COMPLETE: {finding_count} findings

The Correlator Agent will handle interpretation.""",
    tools=[scan_with_semgrep]
)
```

**Build the Secrets Agent with the same pattern.** The instructions should say: "Run Gitleaks. Return all findings. Do NOT truncate or omit any findings. The full secret match is automatically truncated by the tool — do not try to recover it."

### Day 11 — CVE Agent + Correlator Agent

#### Step 22: Build the CVE Agent

Same pattern. Key instruction detail: "Always use the batch OSV.dev endpoint. Never make individual per-package requests. If requirements.txt is not found, return CVE_SCAN_SKIPPED with a reason."

#### Step 23: Build the Correlator Agent (the hard one)

The Correlator is the most important agent. Its job is to take all three sets of raw findings and for each one, call `check_reachability`, then produce a classified, enriched output.

**Cursor prompt for this one:**
```
Create agents/correlator_agent.py using the OpenAI Agents SDK.

The CorrelatorAgent takes as input:
- sast_findings: list[SemgrepFinding]
- secret_findings: list[GitleaksFinding]
- cve_findings: list[CVEVulnerability]
- changed_files: list[str] (files changed in the PR)

For each SAST finding:
  1. Call check_reachability(finding.path, finding.check_id, finding.line, changed_files)
  2. Produce an EnrichedFinding (Pydantic) with all original fields + reachability result + priority (P1/P2/P3)

For secret findings:
  - Always treat as P1 (reachable by definition — it's a secret in the diff)
  - No reachability check needed

For CVE findings:
  - Reachability = check if the package is actually imported in changed files
  - Priority based on CVSS score + reachability

Final output: CorrelationReport (Pydantic):
  - p1_findings: list[EnrichedFinding]  # BLOCK
  - p2_findings: list[EnrichedFinding]  # WARN
  - p3_findings: list[EnrichedFinding]  # INFO
  - total_suppressed: int  # count of findings hidden as unreachable
  - changed_files: list[str]

Model instructions: "Classify each finding using the severity rubric. Be conservative —
when in doubt, escalate to P1. Never downgrade a finding without explicit evidence
that it is unreachable. Your output must be valid JSON matching the CorrelationReport schema."

Use structured output (response_format=CorrelationReport) to ensure valid JSON.
```

#### Step 24: Structured output with Groq

Groq supports structured outputs via the `response_format` parameter on compatible models. Here's the pattern:

```python
from agents import Agent, ModelSettings
from pydantic import BaseModel

class CorrelationReport(BaseModel):
    p1_findings: list[EnrichedFinding]
    p2_findings: list[EnrichedFinding]
    p3_findings: list[EnrichedFinding]
    total_suppressed: int

CORRELATOR_AGENT = Agent(
    name="Security-Correlator",
    model=GROQ_MODEL,
    instructions="...",  # as above
    output_type=CorrelationReport,  # forces structured output
    tools=[check_reachability_tool]
)
```

**Test the Correlator against mock data before connecting to real agents:**
```python
# tests/test_agents.py
import pytest
from agents.correlator_agent import CORRELATOR_AGENT
from agents import Runner
from agents.base import configure_groq_client

@pytest.fixture(autouse=True)
def setup_groq():
    configure_groq_client()

@pytest.mark.asyncio
async def test_correlator_classifies_sql_injection_as_p1():
    mock_findings = {
        "sast_findings": [{
            "check_id": "python.lang.security.audit.sqli",
            "path": "app/routes.py",
            "line": 42,
            "severity": "ERROR",
            "message": "SQL injection via string formatting",
            "cwe": "CWE-89",
            "fingerprint": "abc123"
        }],
        "secret_findings": [],
        "cve_findings": [],
        "changed_files": ["app/routes.py"]  # same file = highly reachable
    }
    result = await Runner.run(CORRELATOR_AGENT, str(mock_findings))
    assert len(result.final_output.p1_findings) == 1
    assert result.final_output.p1_findings[0].reachability.confidence == "HIGH"
```

### Day 12 — Reporter Agent

#### Step 25: Build the Reporter Agent

The Reporter takes a `CorrelationReport` and produces the actual GitHub PR comment markdown.

**SKILL.md usage here:** The Reporter should READ `skills/security_report.md` as its system-prompt context. This is your legitimate use of the SKILL.md concept — the report format guide is procedural knowledge for the model, not a function call.

```python
# agents/reporter_agent.py
from pathlib import Path

SKILL_CONTENT = (Path(__file__).parent.parent / "skills" / "security_report.md").read_text()

REPORTER_AGENT = Agent(
    name="Security-Reporter",
    model=GROQ_MODEL,
    instructions=f"""You are a security report writer for engineering teams.

Your job: Turn a CorrelationReport into one clear, actionable GitHub PR comment.

FORMATTING GUIDE:
{SKILL_CONTENT}

Rules:
- ONE comment, not multiple
- Never repeat the same finding twice
- If p1_findings is empty, the PR PASSES — say so clearly with a ✅
- If p1_findings exist, say ❌ MERGE BLOCKED and list them
- Always include the suppressed count: "X findings suppressed as unreachable"
- Use the exact table format from the formatting guide
- Keep the total comment under 4000 characters (GitHub limit)

Your output must be valid GitHub-flavored markdown."""
)
```

### Day 13 — Wire all agents together into orchestrator.py

#### Step 26: Build the orchestrator

This is the parallel fan-out logic. Use Cursor Agent mode with this spec:

```
Create agents/orchestrator.py

Function: async def run_security_pipeline(repo_path: str, changed_files: list[str], pr_metadata: dict) -> OrchestratorResult

OrchestratorResult (Pydantic):
  - pr_comment_markdown: str
  - should_block_merge: bool (True if any p1 findings)
  - correlation_report: CorrelationReport
  - total_scan_time_ms: int

Steps:
1. Run SAST_AGENT, SECRETS_AGENT, and CVE_AGENT in PARALLEL using asyncio.gather()
   - Each gets the repo_path / appropriate input
   - All three run simultaneously, not sequentially

2. Fan-in: collect all three results

3. Run CORRELATOR_AGENT with merged findings + changed_files

4. Run REPORTER_AGENT with the correlation_report

5. Determine should_block_merge: len(correlation_report.p1_findings) > 0

6. Return OrchestratorResult

Error handling:
- If any of the 3 parallel agents fails: mark that scan as FAILED (not as clean)
- A failed SAST scan does NOT mean "no SAST findings" — it means "scan incomplete"
- Include scan_failures list in OrchestratorResult

Add timing: record start time, record each agent's duration in the result.
```

The parallel execution pattern is the key line:
```python
import asyncio
from agents import Runner

sast_task = Runner.run(SAST_AGENT, repo_path)
secrets_task = Runner.run(SECRETS_AGENT, repo_path)
cve_task = Runner.run(CVE_AGENT, requirements_path)

# All three run at the same time
sast_result, secrets_result, cve_result = await asyncio.gather(
    sast_task, secrets_task, cve_task,
    return_exceptions=True  # Don't let one failure kill the others
)
```

**Phase 3 done when:**
- [ ] Each of the 5 agents runs independently without errors
- [ ] Correlator correctly classifies your test_targets/vulnerable.py findings
- [ ] Orchestrator runs all 3 scanners in parallel (verify with timing — total time should be ~max of the 3, not sum)
- [ ] Reporter produces valid GitHub-flavored markdown

---

## Phase 4 — GitHub Integration
**Time: 4 days | Goal: A real PR triggers the pipeline and gets a comment**

### Day 14 — SQLite dedup store

#### Step 27: Build state/dedup_store.py

This prevents the bot from re-commenting on findings that were already reported in a previous commit to the same PR.

```python
# state/dedup_store.py
import sqlite3
from pathlib import Path

DB_PATH = Path("data/dedup.db")

def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reported_findings (
            fingerprint TEXT PRIMARY KEY,
            pr_number INTEGER,
            repo_full_name TEXT,
            first_seen_at TEXT,
            status TEXT DEFAULT 'open'
        )
    """)
    conn.commit()
    conn.close()

def filter_new_findings(findings: list, pr_number: int, repo: str) -> list:
    """Return only findings not previously reported for this PR."""
    conn = sqlite3.connect(DB_PATH)
    new_findings = []
    for finding in findings:
        fp = finding.fingerprint
        row = conn.execute(
            "SELECT 1 FROM reported_findings WHERE fingerprint=? AND pr_number=? AND repo_full_name=?",
            (fp, pr_number, repo)
        ).fetchone()
        if not row:
            new_findings.append(finding)
    conn.close()
    return new_findings

def record_findings(findings: list, pr_number: int, repo: str):
    """Mark findings as reported."""
    from datetime import datetime
    conn = sqlite3.connect(DB_PATH)
    for finding in findings:
        conn.execute(
            "INSERT OR IGNORE INTO reported_findings VALUES (?,?,?,?,?)",
            (finding.fingerprint, pr_number, repo, datetime.utcnow().isoformat(), "open")
        )
    conn.commit()
    conn.close()
```

### Day 15 — Repo cloning helper + FastAPI webhook receiver

#### Step 28a: Build webhook/repo_cloner.py (do this before app.py)

The webhook needs to clone the PR's head commit to a temp directory so the scanners have real files to work with. This is not covered by PyGitHub — it needs `git` on the system path (already available on your machine and in the Dockerfile).

```python
# webhook/repo_cloner.py
import subprocess
import tempfile
import shutil
import os
from contextlib import contextmanager

@contextmanager
def cloned_repo(clone_url: str, head_sha: str, github_token: str):
    """
    Context manager that clones a repo at a specific commit SHA into a temp
    directory, yields the path, then deletes the directory on exit.

    Usage:
        with cloned_repo(clone_url, head_sha, token) as repo_path:
            run_security_pipeline(repo_path, ...)
        # temp dir is automatically cleaned up here

    Why a context manager: guarantees cleanup even if the pipeline crashes.
    A leaked temp directory with cloned source code is a security problem.
    """
    tmp_dir = tempfile.mkdtemp(prefix="security-triage-")
    try:
        # Embed the token in the URL for authenticated cloning of private repos.
        # Format: https://<token>@github.com/owner/repo.git
        # The token never appears in logs because we strip it from the URL after.
        auth_url = clone_url.replace("https://", f"https://{github_token}@")

        subprocess.run(
            ["git", "clone", "--depth", "1", auth_url, tmp_dir],
            check=True,
            capture_output=True,   # suppress token from stdout/stderr
            timeout=60
        )
        # Checkout the exact commit the PR is at (clone --depth 1 gets HEAD of
        # the default branch; we need the PR's head SHA instead)
        subprocess.run(
            ["git", "fetch", "--depth", "1", "origin", head_sha],
            cwd=tmp_dir,
            check=True,
            capture_output=True,
            timeout=30
        )
        subprocess.run(
            ["git", "checkout", head_sha],
            cwd=tmp_dir,
            check=True,
            capture_output=True,
            timeout=10
        )
        yield tmp_dir
    finally:
        # Always delete — even on exception.
        shutil.rmtree(tmp_dir, ignore_errors=True)
```

> **Security note worth mentioning in interviews:** The GitHub token is embedded in the clone URL, not passed as a CLI flag visible in `ps aux`. `capture_output=True` ensures it never appears in your process logs. The `finally` block guarantees source code is deleted even if the pipeline raises an exception mid-scan.

#### Step 28b: Build webhook/get_pr_files.py

The webhook payload tells you the PR number but NOT which files changed. You need a separate GitHub API call for that.

```python
# webhook/get_pr_files.py
from github import Github
import os

def get_pr_changed_files(repo_full_name: str, pr_number: int) -> list[str]:
    """
    Returns the list of file paths changed in a PR.
    Used by the orchestrator to determine reachability scope.

    Example return: ["app/routes.py", "requirements.txt", "utils/helpers.py"]
    """
    g = Github(os.getenv("GITHUB_TOKEN"))
    repo = g.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)
    # pr.get_files() is paginated — the list() call fetches all pages
    files = list(pr.get_files())
    return [f.filename for f in files]
```

> **Why this is a separate file:** `app.py` receives the webhook and must respond to GitHub within 10 seconds. Fetching PR files, cloning the repo, and running 3 scanners all take longer than that. The pattern is: respond immediately with `{"status": "accepted"}`, then do all the work in a `BackgroundTask`. Keeping helpers in separate files makes that background task easy to import and call without circular imports.

#### Step 28c: Build webhook/app.py

Use Cursor with this spec:
```
Create webhook/app.py using FastAPI.

Imports needed:
- from webhook.repo_cloner import cloned_repo
- from webhook.get_pr_files import get_pr_changed_files
- from agents.orchestrator import run_security_pipeline
- from webhook.github_client import post_pr_comment, create_check_run

Endpoint: POST /webhook/github
- Validate GitHub webhook signature using GITHUB_WEBHOOK_SECRET from env
  (HMAC-SHA256 signature in X-Hub-Signature-256 header)
- Parse the JSON payload
- If event is "pull_request" AND action is "opened" or "synchronize":
  - Extract: repo full_name, PR number, clone_url, head SHA
  - Return {"status": "accepted"} IMMEDIATELY (GitHub requires response < 10s)
  - Use FastAPI BackgroundTasks to run the pipeline asynchronously:
      1. Call get_pr_changed_files(repo_full_name, pr_number) to get changed file list
      2. Use cloned_repo(clone_url, head_sha, GITHUB_TOKEN) context manager to clone
      3. Inside the context: call run_security_pipeline(repo_path, changed_files, pr_metadata)
      4. If should_block_merge: call create_check_run(..., conclusion="failure")
         Else: call create_check_run(..., conclusion="success")
      5. Always: call post_pr_comment(repo_full_name, pr_number, pr_comment_markdown)

Helper function: validate_github_signature(payload: bytes, sig_header: str) -> bool
  - Uses hmac.compare_digest to prevent timing attacks (important security detail!)
```

The timing attack protection is a small but important detail:
```python
import hmac
import hashlib

def validate_github_signature(payload: bytes, sig_header: str) -> bool:
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "").encode()
    expected = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()
    # compare_digest prevents timing attacks — always use this, never ==
    return hmac.compare_digest(expected, sig_header)
```

**Mention this in an interview.** It shows security awareness in your own code, not just in what the agents scan.

#### Step 29: Set up GitHub webhook locally using ngrok (free)

To test the webhook locally without deploying:
```bash
# Install ngrok (free, no credit card for basic tunnel)
# macOS: brew install ngrok
# Or download from: https://ngrok.com/download

# Start your FastAPI server
uvicorn webhook.app:app --reload --port 8000

# In a separate terminal: expose it to the internet
ngrok http 8000
# Note the https://xxxx.ngrok.io URL

# On GitHub: Repository → Settings → Webhooks → Add webhook
# Payload URL: https://xxxx.ngrok.io/webhook/github
# Content type: application/json
# Secret: same as GITHUB_WEBHOOK_SECRET in your .env
# Events: Pull requests
```

### Day 16 — GitHub API calls

#### Step 30: Post PR comments and check runs

```python
# webhook/github_client.py
from github import Github
import os

def get_github_client() -> Github:
    return Github(os.getenv("GITHUB_TOKEN"))

def post_pr_comment(repo_full_name: str, pr_number: int, comment: str):
    g = get_github_client()
    repo = g.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)
    pr.create_issue_comment(comment)

def create_check_run(repo_full_name: str, head_sha: str, conclusion: str, title: str, summary: str):
    """
    conclusion: "success" | "failure" | "neutral"
    failure = blocks merge (like a failed CI check)
    """
    g = get_github_client()
    repo = g.get_repo(repo_full_name)
    repo.create_check_run(
        name="Security Triage Agent",
        head_sha=head_sha,
        status="completed",
        conclusion=conclusion,
        output={"title": title, "summary": summary}
    )
```

### Day 17 — End-to-end test

#### Step 31: Create a test repository and open a real PR

```bash
# Create a tiny test repo on GitHub with your vulnerable.py file
# Open a PR that modifies vulnerable.py
# Watch ngrok logs to see the webhook arrive
# Watch your terminal to see the agents run
# Check the PR on GitHub — you should see the bot comment appear
```

Debug checklist if nothing appears:
- Check ngrok dashboard at http://localhost:4040 for incoming requests
- Check GitHub webhook delivery logs (Settings → Webhooks → Recent Deliveries)
- Check your FastAPI logs for errors
- Verify your GitHub token has `pull_requests:write` permission

**Phase 4 done when:**
- [ ] Opening a PR on your test repo triggers the webhook
- [ ] The pipeline runs and posts a comment on the PR
- [ ] A P1 finding creates a blocking check run
- [ ] The dedup store prevents duplicate comments on re-push

---

## Phase 5 — Observability with Langfuse
**Time: 2 days | Goal: Every agent call is traced and visible in the UI**

### Day 18 — Add tracing to all agents

#### Step 32: Wrap the orchestrator with Langfuse tracing

Read: https://langfuse.com/docs/sdk/python/sdk-v3

```python
# observability/tracing.py
from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context
import os

langfuse = Langfuse(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    host=os.getenv("LANGFUSE_HOST", "http://localhost:3000")
)

def trace_agent_run(agent_name: str, input_data: dict, output_data: dict, duration_ms: int):
    """Manually record an agent span to Langfuse."""
    trace = langfuse.trace(name=f"security-pipeline")
    trace.span(
        name=agent_name,
        input=input_data,
        output=output_data,
        metadata={"duration_ms": duration_ms}
    )
    langfuse.flush()
```

Add `@observe(name="run_security_pipeline")` to your orchestrator function — this automatically traces all LLM calls inside it.

#### Step 33: Add cost tracking per run

```python
# In orchestrator.py — add after each agent run
from langfuse.decorators import langfuse_context

langfuse_context.update_current_observation(
    usage={
        "input": sast_result.usage.prompt_tokens,
        "output": sast_result.usage.completion_tokens,
    }
)
```

After Phase 5, open http://localhost:3000 and you should see:
- A trace for every PR webhook received
- Individual spans for each of the 5 agents
- Token counts and latencies
- Whether findings were found

**This Langfuse dashboard screenshot is what goes in your README.** It is the single biggest visual proof that your project is production-quality, not a toy.

---

## Phase 6 — Polish and GitHub Quality
**Time: 3 days | Goal: The repo looks professional, not like a hackathon dump**

### Day 19 — Docker + CI/CD

#### Step 34: Dockerfile

```dockerfile
FROM python:3.11-slim

# Install system tools
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Semgrep
RUN pip install semgrep

# Install Gitleaks
RUN curl -sSfL https://raw.githubusercontent.com/gitleaks/gitleaks/main/scripts/install.sh | sh -s -- -b /usr/local/bin

WORKDIR /app
COPY pyproject.toml .
RUN pip install -e .

COPY . .

EXPOSE 8000
CMD ["uvicorn", "webhook.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Step 35: docker-compose.yml (full stack)

```yaml
version: "3.8"
services:
  security-agent:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/app/data  # SQLite persistence
    depends_on:
      - langfuse-server

  langfuse-server:
    image: langfuse/langfuse:latest
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: "postgresql://langfuse:langfuse@langfuse-db:5432/langfuse"
      NEXTAUTH_SECRET: "change-me-in-production"
      NEXTAUTH_URL: "http://localhost:3000"
      SALT: "change-me-in-production"
    depends_on:
      - langfuse-db

  langfuse-db:
    image: postgres:15
    environment:
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: langfuse
      POSTGRES_DB: langfuse
    volumes:
      - langfuse_db:/var/lib/postgresql/data

volumes:
  langfuse_db:
```

```bash
# One command to start everything
docker compose up --build
```

### Day 20 — GitHub Actions CI

#### Step 36: .github/workflows/ci.yml

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          
      - name: Install Semgrep
        run: pip install semgrep
        
      - name: Install Gitleaks
        run: |
          curl -sSfL https://raw.githubusercontent.com/gitleaks/gitleaks/main/scripts/install.sh | sh -s -- -b /usr/local/bin
          
      - name: Install dependencies
        run: pip install -e ".[dev]"
        
      - name: Run linting (ruff)
        run: ruff check .
        
      - name: Run tests (excluding eval — those need API keys)
        run: pytest tests/ -v --cov=. --cov-report=xml
        env:
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
          
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
```

Add `GROQ_API_KEY` as a repository secret in GitHub: Settings → Secrets → Actions.

### Day 21 — README (this is as important as the code)

#### Step 37: Write the README

Structure it exactly like this — the order matters for how quickly an interviewer forms an opinion:

```markdown
# 🔍 Security Finding Triage & Remediation Agent

> A multi-agent pipeline that eliminates security scanner noise by 
> correlating raw findings with real code reachability before 
> posting one clean, actionable review to your GitHub PR.

## The Problem
Security bots are so noisy that developers disable them.
Semgrep, Gitleaks, and dependency scanners each post their own comments —
most flagging code paths nobody ever calls. Teams learn to ignore them.

## The Solution
Five agents run in parallel and in sequence to:
1. Find everything (3 parallel scanners)
2. Check if it actually matters (Correlator + reachability analysis)
3. Post one clean, prioritized comment (Reporter)

## Architecture

[DIAGRAM HERE — see below]

## Demo
[GIF HERE — see below]

## Setup
...

## Key Design Decisions
1. **Fail-closed on uncertain reachability**: When confidence is LOW, we flag
   for manual review — never assert safety. Security tools must never silently 
   let things through.
2. **HMAC-SHA256 webhook validation with timing-safe compare**: ...
3. **Secrets truncated at the tool layer**: Full secret values never enter 
   LLM context or logs...
```

#### Step 38: Create the architecture diagram

Use the Mermaid format (renders natively on GitHub):

```markdown
```mermaid
flowchart TD
    A[GitHub PR Opened] --> B[Webhook Receiver\nFastAPI]
    B --> C[Orchestrator]
    
    C --> D[SAST Agent\nSemgrep]
    C --> E[Secrets Agent\nGitleaks]
    C --> F[CVE Agent\nOSV.dev]
    
    D --> G[Correlator Agent]
    E --> G
    F --> G
    
    G --> |calls| H[Reachability Tool\nAST + grep]
    G --> I[Reporter Agent\n+ SKILL.md]
    
    I --> J{P1 findings?}
    J --> |Yes| K[❌ Block Merge\nCheck Run]
    J --> |No| L[✅ Info Comment]
    
    K --> M[Langfuse Trace]
    L --> M
    
    G -.-> N[(SQLite\nDedup Store)]
```
```

#### Step 39: Record a demo GIF

Use [Terminalizer](https://github.com/faressoft/terminalizer) or [Asciinema](https://asciinema.org/) to record:
1. Open a PR on your test repo with vulnerable.py changes
2. Show the ngrok logs lighting up with the webhook
3. Show the agents running with print statements showing timing
4. Open GitHub and show the PR comment appearing

This GIF goes at the top of your README above the fold.

---

## Phase Summary — What to Do Each Day

| Day | Phase | Main deliverable | Cursor requests used |
|-----|-------|-----------------|---------------------|
| 1 | 0 | Tools installed, Groq verified | 0 |
| 2 | 0 | MCP hello world, Langfuse running | 0 |
| 3 | 1 | Understand Semgrep JSON format | 0 |
| 4 | 1 | Understand Gitleaks + OSV.dev | 0 |
| 5 | 1 | Dep parser (requirements.txt + pyproject.toml) written and tested | 2 |
| 6 | 2 | MCP server + Semgrep tool | 3 |
| 7 | 2 | Gitleaks tool + OSV tool | 3 |
| 8 | 2 | Reachability tool | 2 |
| 9 | 2 | Resources + server wired up | 1 |
| 10 | 3 | agents/base.py + SAST Agent + Secrets Agent | 2 |
| 11 | 3 | CVE Agent + Correlator scaffold | 3 |
| 12 | 3 | Reporter Agent + SKILL.md | 2 |
| 13 | 3 | Orchestrator (parallel fan-out) | 3 |
| 14 | 4 | SQLite dedup store | 1 |
| 15 | 4 | repo_cloner.py + get_pr_files.py + FastAPI webhook receiver | 3 |
| 16 | 4 | GitHub API client | 1 |
| 17 | 4 | End-to-end test with real PR | 0 |
| 18 | 5 | Langfuse tracing throughout | 2 |
| 19 | 6 | Docker + docker-compose | 1 |
| 20 | 6 | GitHub Actions CI | 1 |
| 21 | 6 | README + architecture diagram + demo GIF | 0 |
| **Total** | | | **~30 Cursor agent requests** |

This fits comfortably within the free Cursor Hobby tier (~50 estimated). The key is writing precise specs before each Cursor request, not using it for trial-and-error.

---

## Interview Cheat Sheet — What to Say About Each Decision

Keep these answers ready. These are the questions you WILL get.

**Q: "Why five agents and not one big prompt?"**
A: "Three of the five are deterministic tool wrappers — Semgrep, Gitleaks, OSV.dev — where I specifically don't want an LLM making decisions. The LLM reasoning is isolated to the Correlator (which needs to reason about reachability across findings) and the Reporter (which needs to format contextually). Separating deterministic scanning from probabilistic reasoning is a deliberate design choice, not framework cargo-culting."

**Q: "How do you handle false positives?"**
A: "The Correlator's reachability analysis is the noise filter. A Semgrep finding in an imported library you're not actually calling gets downgraded from P1 to P3 — it appears in the summary but doesn't block the merge. The reachability confidence thresholds are tuned to be conservative: when evidence is absent, we default to manual review rather than auto-pass. The system is designed to cry wolf less, not to silently let things through."

**Q: "What if one scanner crashes?"**
A: "The orchestrator uses asyncio.gather with return_exceptions=True. A crashed scanner marks its findings as UNKNOWN rather than CLEAN. The merge is never unblocked because a scanner failed — fail-closed is a first-class design principle, not an afterthought. The Reporter explicitly surfaces scan failures in the PR comment so the team knows to run it manually."

**Q: "How is this different from just running Semgrep in GitHub Actions?"**
A: "Semgrep in Actions is a scanner. This is a triage and decision system. The difference is the Correlator — it answers 'should I care about this right now, given what changed in this specific PR?' Semgrep reports 47 findings across the whole codebase every time. This reports 3 findings that actually matter for this PR. Developers stop ignoring it because it's no longer crying wolf."

---

## Resume Bullet Points (copy, customize numbers)

```
• Built a 5-agent security triage pipeline (Semgrep/Gitleaks/OSV.dev → 
  Correlator → Reporter) that consolidates noisy multi-scanner output into 
  one ranked, actionable PR comment via LLM-powered reachability correlation 
  and a custom MCP server

• Designed parallel agent fan-out (asyncio.gather) reducing total scan 
  time from ~45s sequential to ~18s parallel across 3 concurrent scanners

• Implemented fail-closed security guardrails: uncertain reachability 
  defaults to manual review, never to auto-pass; timing-safe HMAC-SHA256 
  webhook validation prevents replay attacks in GitHub integration

• Added Langfuse distributed tracing across all agent calls with per-span
  token usage and latency; enables prompt debugging without print statements
```

---

## Quick Reference: What Each File Does

| File | What it does | When you build it |
|---|---|---|
| `mcp_server/server.py` | MCP server entry point | Day 6 |
| `mcp_server/tools/semgrep_tool.py` | Wraps Semgrep CLI, returns Pydantic model | Day 6 |
| `mcp_server/tools/gitleaks_tool.py` | Wraps Gitleaks CLI, truncates secrets | Day 7 |
| `mcp_server/tools/osv_tool.py` | Calls OSV.dev batch API | Day 7 |
| `mcp_server/tools/dep_parser.py` | Parses requirements.txt and pyproject.toml | Day 5 |
| `mcp_server/tools/reachability_tool.py` | AST+grep reachability check | Day 8 |
| `agents/base.py` | Groq client config — build this FIRST, all agents depend on it | Day 10 |
| `agents/sast_agent.py` | Semgrep wrapper agent | Day 10 |
| `agents/secrets_agent.py` | Gitleaks wrapper agent | Day 10 |
| `agents/cve_agent.py` | OSV.dev wrapper agent | Day 11 |
| `agents/correlator_agent.py` | Main reasoning agent, produces structured report | Day 11 |
| `agents/reporter_agent.py` | Formats markdown PR comment | Day 12 |
| `agents/orchestrator.py` | Parallel fan-out + pipeline controller | Day 13 |
| `skills/security_report.md` | SKILL.md format guide for Reporter | Day 12 |
| `state/dedup_store.py` | SQLite-backed finding deduplication | Day 14 |
| `webhook/repo_cloner.py` | Clones repo at PR head SHA into temp dir, cleans up on exit | Day 15 |
| `webhook/get_pr_files.py` | Fetches list of files changed in a PR via GitHub API | Day 15 |
| `webhook/app.py` | FastAPI GitHub webhook receiver | Day 15 |
| `webhook/github_client.py` | GitHub API calls (comments, check runs) | Day 16 |
| `observability/tracing.py` | Langfuse trace wrapper | Day 18 |
| `tests/test_mcp_tools.py` | Unit tests for all 4 MCP tools | Days 6-8 |
| `tests/test_agents.py` | Unit tests for Correlator output | Day 11 |
| `docker-compose.yml` | Full stack (agent + Langfuse) | Day 19 |
| `.github/workflows/ci.yml` | CI: lint + test on every push | Day 20 |
| `README.md` | Architecture diagram + demo GIF | Day 21 |
