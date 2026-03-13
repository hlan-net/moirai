# MCP Servers Guide for Claude Code + Moirai

This guide explains how to configure and use MCP (Model Context Protocol) servers with Claude Code, including Moirai's own MCP server and external servers for development.

---

## What is MCP?

**Model Context Protocol** is a standard for connecting AI assistants (like Claude) to external tools and data sources. Think of it as plugins for Claude Code.

With MCP, Claude Code can:
- 🔍 Query GitHub repositories and PRs
- ☸️ Interact with Kubernetes clusters
- 📊 Analyze code quality via SonarQube
- 📚 Access knowledge bases (Wikipedia, Google Docs, Microsoft Learn)
- 🎯 Call custom tools (like Moirai's MCP server)

---

## Available MCP Servers

### Your Current Setup

You have 6 MCP servers configured in your `opencodes` config:

#### 1. **GitHub** ✅
- **Type:** Local wrapper
- **Purpose:** Query GitHub repos, issues, PRs, commits
- **Enabled:** Yes
- **Use Cases:**
  - Search for code in moirai repo
  - View PR details
  - Check issue history
  - Search commits for patterns

#### 2. **Kubernetes** ✅
- **Type:** Docker container (mcp/kubernetes)
- **Purpose:** Query and manage Kubernetes clusters
- **Enabled:** Yes
- **Use Cases:**
  - Check Moirai deployment status
  - View pod logs
  - Scale deployments
  - Check resource usage
  - View cluster events

#### 3. **SonarQube** ✅
- **Type:** Docker container
- **Purpose:** Code quality analysis (hlan-net org)
- **Enabled:** Yes
- **Configuration:** SonarCloud integration
- **Use Cases:**
  - Check code coverage
  - Find security issues
  - Analyze technical debt
  - View quality gates

#### 4. **Wikipedia** ✅
- **Type:** Docker container (mcp/wikipedia-mcp)
- **Purpose:** Search Wikipedia for reference content
- **Enabled:** Yes
- **Use Cases:**
  - Research topics for documentation
  - Find definitions and background
  - Verify facts

#### 5. **Google Developer Knowledge** ✅
- **Type:** Remote API
- **Purpose:** Access Google's developer documentation
- **Enabled:** Yes
- **Use Cases:**
  - Learn about Google Cloud, APIs
  - Research best practices
  - Find code samples

#### 6. **Microsoft Learn** ✅
- **Type:** Remote API
- **Purpose:** Access Microsoft documentation
- **Enabled:** Yes
- **Use Cases:**
  - Learn Azure, Office APIs
  - Find deployment patterns
  - Research cloud architectures

---

## How to Enable MCP Servers in Claude Code

### Option A: Configuration File (Recommended)

Claude Code looks for MCP configuration in:
```
~/.claude/mcp-servers.json
```

**Already set up!** File created at `/home/larry/.claude/mcp-servers.json`

### Option B: Command-Line (One-Time Use)

```bash
claude --mcp github --mcp kubernetes --mcp sonarqube
```

### Option C: Environment Variable

```bash
export CLAUDE_MCP_SERVERS="github,kubernetes,sonarqube"
claude
```

---

## Using MCP Servers with Claude Code

### Example 1: Query Kubernetes Status

**Task:** "Show me the status of the Moirai deployment on my K3s cluster"

Claude will:
1. Use the Kubernetes MCP server
2. Connect via your `~/.kube/config`
3. Query the cluster
4. Return pod status, resource usage, logs

**Response:** Real-time cluster state

### Example 2: Search GitHub for Code

**Task:** "Search the moirai repo for all uses of 'forge_issue' MCP tool"

Claude will:
1. Use the GitHub MCP server
2. Search moirai repository
3. Return matching files and line numbers
4. Show context

**Response:** Exact file locations and context

### Example 3: Check Code Quality

**Task:** "What's the code coverage for moirai/mcp_service/tools?"

Claude will:
1. Use the SonarQube MCP server
2. Connect to SonarCloud
3. Query hlan-net organization
4. Return coverage metrics

**Response:** Coverage % by file

### Example 4: Research Best Practices

**Task:** "How should I structure a Kubernetes Helm chart for multi-tier applications?"

Claude will:
1. Search Microsoft Learn (cloud deployment patterns)
2. Search Google Docs (Kubernetes best practices)
3. Combine findings
4. Apply to Moirai's architecture

**Response:** Best practices + recommendations

---

## Moirai's Own MCP Server

Moirai exposes its own MCP server (running on port 8090) which provides tools for:

### MCP Tools Available in Moirai

#### **Feed Management**
- `list_feeds(userspace)` — List RSS feeds
- `add_feed(userspace, url, name)` — Add new feed
- `delete_feed(userspace, feed_id)` — Remove feed
- `refresh_feeds(userspace)` — Trigger feed ingestion

#### **Article Queries**
- `list_articles(userspace, limit, since)` — Get articles
- `search_articles(userspace, query)` — Full-text search
- `get_article(userspace, article_id)` — Fetch article details

#### **Issue/Event Management**
- `forge_issue(userspace, logos, description, premises)` — Create issue ⚠️ (currently broken, see BUG_RAISE_ISSUE_WIZARD.md)
- `list_issues(userspace)` — List all issues
- `seal_issue(userspace, issue_id)` — Archive issue
- `measure_issue(userspace, issue_id, ...)` — Update issue

#### **Agent Configuration**
- `list_agents(userspace)` — View agents
- `add_agent(userspace, config)` — Create agent
- `enable_agent(userspace, agent_id)` — Activate agent

#### **Search & Staleness**
- `search_articles(userspace, query)` — Article search
- `search_issues(userspace, query)` — Issue search
- `check_staleness(userspace)` — Find stale issues

#### **User Management**
- `list_users()` — Admin: list all users
- `create_user(username, password)` — Admin: add user

---

## Connecting Claude Code to Moirai's MCP Server

### Local Development (Docker)

When running Moirai with Docker Compose:

```json
{
  "mcpServers": {
    "moirai": {
      "type": "local",
      "command": [
        "docker",
        "exec",
        "-i",
        "moirai-mcp-server",
        "python",
        "-m",
        "mcp_service.main"
      ],
      "environment": {
        "COUCHDB_URI": "http://moirai-couchdb:5984/",
        "COUCHDB_USER": "admin",
        "COUCHDB_PASSWORD": "password",
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "password",
        "JWT_SECRET_KEY": "your-secret-key",
        "REDIS_PASSWORD": "redis-password"
      }
    }
  }
}
```

### Kubernetes Deployment

When Moirai runs on Kubernetes:

```json
{
  "mcpServers": {
    "moirai": {
      "type": "local",
      "command": [
        "kubectl",
        "exec",
        "-i",
        "deployment/moirai-mcp-server",
        "-n", "default",
        "--",
        "python",
        "-m",
        "mcp_service.main"
      ],
      "environment": {
        "KUBECONFIG": "/home/larry/.kube/config"
      }
    }
  }
}
```

### Remote Deployment (Production)

If Moirai is deployed remotely:

```json
{
  "mcpServers": {
    "moirai": {
      "type": "remote",
      "url": "https://moirai.example.com:8090",
      "headers": {
        "Authorization": "Bearer YOUR_JWT_TOKEN"
      }
    }
  }
}
```

---

## Example Workflows

### Workflow 1: Debug Issue Wizard Bug

**Goal:** Understand why "Raise Issue" is broken and fix it

**Steps:**
1. Use **GitHub** MCP to search moirai repo for "forge_issue" calls
2. Use **SonarQube** MCP to check code quality metrics
3. Ask Claude to analyze the issue (BUG_RAISE_ISSUE_WIZARD.md)
4. Use **Kubernetes** MCP to check production logs if needed

**Command:**
```
"Search GitHub for forge_issue, then analyze the error in BUG_RAISE_ISSUE_WIZARD.md"
```

### Workflow 2: Deploy to Kubernetes

**Goal:** Deploy Moirai to your K3s cluster

**Steps:**
1. Claude reads your Helm chart (locally)
2. Use **Kubernetes** MCP to check cluster capacity
3. Deploy using kubectl commands
4. Monitor with Kubernetes MCP (logs, events, status)

**Command:**
```
"Deploy Moirai to my Kubernetes cluster using Helm. Check cluster resources first."
```

### Workflow 3: Code Quality Check

**Goal:** Ensure v0.7.0 code meets quality standards

**Steps:**
1. Push code to GitHub
2. SonarQube analyzes automatically
3. Claude uses SonarQube MCP to fetch metrics
4. Reports coverage, security issues, technical debt

**Command:**
```
"What's the code quality for the changes in PR #123?"
```

---

## Common MCP Commands in Claude Code

### Check Kubernetes Status
```
/mcp kubernetes describe deployment moirai-mcp-server
```

### Search GitHub
```
/mcp github search "moirai" "forge_issue"
```

### View SonarQube Metrics
```
/mcp sonarqube project hlan-net metrics
```

### Search Wikipedia
```
/mcp wikipedia search "Model Context Protocol"
```

---

## Troubleshooting

### MCP Server Not Available

**Error:** "MCP server 'kubernetes' not found"

**Solution:**
1. Check `/home/larry/.claude/mcp-servers.json` exists
2. Verify server is enabled: `"enabled": true`
3. Check Docker is running: `docker ps`
4. Verify kubeconfig exists: `ls ~/.kube/config`

### Authentication Failed

**For Kubernetes:**
```bash
# Check kubeconfig is valid
kubectl cluster-info

# Verify permissions
kubectl auth can-i get pods --all-namespaces
```

**For GitHub:**
```bash
# Check github-mcp-wrapper.sh exists
ls -la /home/larry/.local/bin/github-mcp-wrapper.sh

# Check GitHub token/auth
cat ~/.github/token  # or however it's stored
```

**For SonarQube:**
```bash
# Check token is valid
echo $SONARQUBE_TOKEN | wc -c  # Should be >40 chars
```

### Docker Container Issues

**If Docker MCP servers fail:**
```bash
# Ensure image is available
docker pull mcp/kubernetes
docker pull mcp/sonarqube
docker pull mcp/wikipedia-mcp

# Test locally
docker run --rm -i mcp/wikipedia-mcp --help
```

---

## Security Best Practices

### 1. **Protect Credentials (CRITICAL!)**

**⚠️ NEVER commit secrets to GitHub!**

Instead, use environment variables:

**Step 1: Store secrets locally (NOT in git)**
```bash
# Add to ~/.bashrc, ~/.zshrc, or ~/.profile
export SONARQUBE_TOKEN="your-actual-token-here"
export GOOGLE_API_KEY="your-actual-key-here"
export GITHUB_TOKEN="your-actual-token-here"  # If not using wrapper
```

**Step 2: Reference in config**
```json
{
  "sonarqube": {
    "environment": {
      "SONARQUBE_TOKEN": "$SONARQUBE_TOKEN",  // Reads from environment
      "SONARQUBE_ORG": "hlan-net"
    }
  },
  "google-dev-kb": {
    "headers": {
      "X-Goog-Api-Key": "$GOOGLE_API_KEY"     // Reads from environment
    }
  }
}
```

**Step 3: Verify secrets are NOT in git**
```bash
# Check ~/.claude/mcp-servers.json is safe
grep -E "sk_|ghp_|AIza" ~/.claude/mcp-servers.json  # Should return nothing!

# Check it wasn't committed
git log -p --all -- ~/.claude/mcp-servers.json
```

**Current Status:** ✅ mcp-servers.json uses environment variable placeholders
- SONARQUBE_TOKEN uses `$SONARQUBE_TOKEN`
- GOOGLE_API_KEY uses `$GOOGLE_API_KEY`
- Never commit actual secrets!

### 2. **Rate Limiting**
- Remote APIs (Google, Microsoft) have rate limits
- Check their documentation for limits
- Use caching where possible

### 3. **Audit Access**
- Log MCP server usage
- Review what Claude Code accesses
- Check Kubernetes audit logs

---

## Next Steps

1. **Verify Setup:**
   ```bash
   # Check MCP servers are available
   claude --list-mcp-servers
   ```

2. **Test Each Server:**
   ```bash
   # Test GitHub
   "List recent commits in moirai repo"

   # Test Kubernetes
   "Show me pod status on my cluster"

   # Test SonarQube
   "What's the code coverage for moirai?"
   ```

3. **Integrate with Workflow:**
   - Use `/mcp kubernetes ...` when debugging deployments
   - Use `/mcp github search ...` when researching code
   - Use `/mcp sonarqube ...` when checking quality

---

## Reference

| Server | Type | Status | Use Cases |
|--------|------|--------|-----------|
| **GitHub** | Local | ✅ Ready | Code search, PR review, issue tracking |
| **Kubernetes** | Local | ✅ Ready | Deployment status, logs, debugging |
| **SonarQube** | Local | ✅ Ready | Code quality, coverage, security |
| **Wikipedia** | Local | ✅ Ready | Research, background, definitions |
| **Google DevKB** | Remote | ✅ Ready | Google Cloud, APIs, best practices |
| **Microsoft Learn** | Remote | ✅ Ready | Azure, Office APIs, cloud patterns |
| **Moirai (Local)** | Local | ⚠️ Optional | Feed/issue management, agents (dev only) |
| **Moirai (K8s)** | Local | ⚠️ Optional | Feed/issue management (production) |

---

**Generated:** 2026-03-13
**Status:** Ready to use
**Questions?** Check individual MCP server docs or ask Claude Code: "How do I use the Kubernetes MCP server?"
