# MCP triage — when Grafana and GitHub are used

Triage runs when an investigation starts: Alertmanager posts a webhook, or you
click **Simulate payments alert** in the console. Causa calls `assemble_brief()`
in `causa/brief.py`, which queries two sources and packs the result into the
investigation brief the investigator receives.

MCP is **not** used by default. The default path is fully offline:

```bash
CAUSA_TRIAGE=mock   # default — MockGrafanaSource + MockGitHubSource
```

Live MCP triage is opt-in:

```bash
CAUSA_TRIAGE=mcp    # McpGrafanaSource + McpGitHubSource (when binary + token ready)
```

---

## When each MCP server runs

| Trigger | What happens |
|---------|--------------|
| Investigation starts (`/webhook/alert` or `/investigations`) | `orchestrator.run_investigation()` → `get_sources()` → `assemble_brief()` |
| `CAUSA_TRIAGE=mock` | No MCP. Fixed realistic data from `causa/sources/mock.py`. |
| `CAUSA_TRIAGE=mcp` | Spawns MCP servers as **stdio subprocesses** for the duration of the triage call. |

MCP servers are **not** long-running services. Causa's Python `mcp` client starts
them, calls one or two tools, then tears them down. This is separate from
`.mcp.json`, which configures MCP for the Cursor IDE only.

---

## Grafana MCP (`mcp-grafana`)

**Implementation:** `McpGrafanaSource` in `causa/sources/mcp.py`

**When:** Every investigation, if `CAUSA_TRIAGE=mcp` (or `mcp-all`).

**How:**

1. Spawns `mcp-grafana --disable-write` over stdio.
2. Calls `query_prometheus` twice against the local Prometheus datasource:
   - p99 of `payments_request_duration_seconds` (request latency)
   - `max(payments_pool_inuse)` (pool saturation)
3. Calls `generate_deeplink` for Grafana panel links on the Payments dashboard.

**Requires:**

| Variable / binary | Purpose |
|-------------------|---------|
| `mcp-grafana` on PATH (or `GRAFANA_MCP_BIN`) | MCP server binary (`go install …/mcp-grafana@latest`) |
| `GRAFANA_URL` | Default `http://localhost:3000` |
| `GRAFANA_SERVICE_ACCOUNT_TOKEN` | Preferred; Viewer role |
| `GRAFANA_USERNAME` / `GRAFANA_PASSWORD` | Fallback for local Grafana (admin/admin) |
| `pip install -r requirements-mcp.txt` | Python `mcp` client library |

**Output in brief:** `metric_signatures[]` — live p99 and pool-in-use observations
plus deeplinks to Grafana panels.

If Grafana MCP fails, the brief records `degraded: ["grafana unavailable: …"]` and
continues with empty metrics rather than crashing.

---

## GitHub MCP (`github-mcp-server`)

**Implementation:** `McpGitHubSource` in `causa/sources/mcp.py`

**When:** Every investigation, if `CAUSA_TRIAGE=mcp` and both the binary and
token are present. With `CAUSA_TRIAGE=mcp-all`, GitHub MCP is required (no mock
fallback). Otherwise Causa falls back to `MockGitHubSource` for GitHub only.

**How:**

1. Spawns `github-mcp-server stdio --read-only --toolsets repos,pull_requests`.
2. Calls `list_pull_requests` on the repo from `CURSOR_TARGET_REPO` (default
   `pablogd-hashi/cursor-causa`): state `closed`, sort `updated`, desc.
3. Keeps PRs with a `merged_at` timestamp (up to 5).

**Requires:**

| Variable / binary | Purpose |
|-------------------|---------|
| `github-mcp-server` on PATH (or `GITHUB_MCP_BIN`) | MCP server binary |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | Fine-grained token, repo read-only |
| `CURSOR_TARGET_REPO` | Repo URL triage searches (same as agent target) |

**Output in brief:** `candidate_changes[]` — recently merged PRs (#, title,
merged_at, url).

The incident window (30 minutes before the alert) is recorded on the brief for
context; the GitHub query intentionally uses a broader "recent merged" filter so
your demo PR shows up even if the merge was more than 30 minutes ago.

If GitHub MCP fails, the brief degrades and continues.

---

## The merge → triage demo flow

This is the story where a real merged PR appears in live triage:

```bash
# 1. Create the regression PR (does not merge)
task regression:pr

# 2. Merge the PR manually on GitHub

# 3. Start stack + Causa with live MCP triage
CAUSA_TRIAGE=mcp task substrate:up
CAUSA_TRIAGE=mcp task run:local   # or: CAUSA_TRIAGE=mcp task demo

# 4. Fire the incident (alert ~90s later)
task break

# 5. Watch the console — brief shows live Grafana metrics + your merged PR
```

Or simulate instantly: open the console and click **Simulate payments alert**
while `CAUSA_TRIAGE=mcp` is set.

**What "merge triggers triage" means:** merging does not auto-start an
investigation. It makes the PR visible to GitHub MCP the **next time** triage
runs (when an alert fires or you simulate one). The brief then links the alert
to the change you merged.

**Runtime vs triage:** Docker compose sets `POOL_MAX_SIZE=50` by default, so
`task break` (pool 10 via env) is the reliable way to fire the alert regardless
of whether main's code default is 50 or 10. After merging the regression PR,
rebuild with `task substrate:up` if you want the container to run the broken code
without an env override.

---

## Source selection reference

From `causa/sources/__init__.py`:

```
CAUSA_TRIAGE=mock     → MockGrafana + MockGitHub          (default, no deps)
CAUSA_TRIAGE=mcp      → McpGrafana + McpGitHub*           (* GitHub if ready, else mock)
CAUSA_TRIAGE=mcp-all  → McpGrafana + McpGitHub            (both required)
```

Install MCP Python deps: `pip install -r requirements-mcp.txt`

Copy tokens: `cp .env.example .env` and fill in Grafana + GitHub values.
