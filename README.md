# Security Finding Triage Agent

This project scans a GitHub pull request with Semgrep, Gitleaks, and OSV.dev,
correlates findings with changed-file reachability, and publishes one ranked
PR comment plus a GitHub check run.

## Architecture

```mermaid
flowchart TD
    A[GitHub Pull Request] --> B[FastAPI Webhook]
    B --> C[OpenAI Agents SDK Orchestrator]
    C --> D[SAST Agent]
    C --> E[Secrets Agent]
    C --> F[CVE Agent]
    D --> G[Semgrep Tool]
    E --> H[Gitleaks Tool]
    F --> I[OSV.dev Tool]
    G --> J[Correlator Agent]
    H --> J
    I --> J
    J --> K[Reachability Tool]
    J --> L[Deterministic Report]
    L --> M[PR Comment and Check Run]
    B --> N[(SQLite Dedup Store)]
    C -. optional .-> O[Langfuse]
```

## Current runtime design

The OpenAI Agents SDK runs the SAST, secrets, and CVE agents concurrently. Each
agent must call its scanner tool, and the orchestrator uses the tool's structured
output as the authoritative scan result. The correlator agent receives those
results, checks SAST reachability with the reachability tool, and classifies
findings. The orchestrator rejects correlation output that drops findings or
downgrades deterministic priorities; on agent or validation failure it falls
back to deterministic correlation.

The system fails closed: scanner/agent failures and a missing dependency file
block the check and appear in the report. A P1 finding also blocks the check.
LOW reachability confidence means manual review, never “safe.” Secret matches
are redacted before scanner results are returned to the model. GitHub report
rendering remains deterministic.

## Local setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Install Semgrep and Gitleaks, then copy `.env.example` to `.env` and configure
`GROQ_API_KEY`, `GITHUB_TOKEN`, and `GITHUB_WEBHOOK_SECRET`. `GROQ_MODEL` is
optional; it defaults to `openai/gpt-oss-120b`. Langfuse tracing is disabled by
default; set `LANGFUSE_TRACING_ENABLED=true` only when the Langfuse service and
keys are available.

Run the tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
```

## Run the webhook locally

```powershell
.\.venv\Scripts\python.exe -m uvicorn webhook.app:app --reload --port 8000
ngrok http 8000
```

Configure the HTTPS ngrok URL as a GitHub Pull Request webhook targeting
`/webhook/github`. The webhook validates `X-Hub-Signature-256`, immediately
accepts supported events, clones the PR head commit, runs the scanners, and
posts the result in the background.

## Docker

```powershell
docker compose up --build
```

The application listens on port `8000`; the optional Langfuse UI listens on
port `3000`. Do not use the example production secrets unchanged.

## Limitations

Reachability is intentionally MVP-level: same-file findings are HIGH
confidence, direct textual imports/references are MEDIUM, and missing evidence
is LOW. It is not a complete language-aware call graph. A real GitHub test
also requires repository permissions, configured credentials, and a public
webhook tunnel.