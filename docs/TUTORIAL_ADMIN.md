# Moirai Admin Guide: Deployment & Management

Welcome to the Moirai admin guide! This document covers deploying, configuring, and maintaining Moirai for your organization.

---

## Part 1: Deployment

### Prerequisites

- **Docker & Docker Compose** (recommended) OR Linux/macOS with Python 3.10+
- **CouchDB 3.2+** (persistent database)
- **Redis 6.0+** (caching & distributed locks)
- **3-4 GB RAM, 20 GB disk** minimum

### Option A: Docker Compose (Recommended)

Fastest path to production.

#### 1. Clone the Repository
```bash
git clone https://github.com/your-org/moirai.git
cd moirai
```

#### 2. Set Environment Variables
Create `.env` file:
```env
# CouchDB
COUCHDB_URI=http://couchdb:5984/
COUCHDB_USER=admin
COUCHDB_PASSWORD=secure_password_here

# Admin Credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change_this_to_something_secure

# Security
JWT_SECRET_KEY=generate_with: python -c "import secrets; print(secrets.token_hex(32))"
REDIS_PASSWORD=another_secure_password

# Optional: LLM Configuration
DEFAULT_LLM_PROVIDER=ollama  # or: openai, gemini
MODEL_NAME=llama2  # or: gpt-4, gemini-pro
OLLAMA_BASE_URL=http://ollama:11434

# Optional: Allow Public Read
ALLOW_PUBLIC_READ=false

# Optional: Article Retention
ARTICLE_EXPIRATION_DAYS=30
```

#### 3. Start the Stack
```bash
docker compose up -d
```

This starts:
- 🔵 **Moirai API** on `http://localhost:8088`
- 🔵 **Moirai UI** on `http://localhost:3000`
- 🟢 **MCP Server** on `http://localhost:8090` (internal)
- 🟡 **CouchDB** on `http://localhost:5984` (with admin UI)
- 🟠 **Redis** on `http://localhost:6379` (internal)
- 📊 **Prometheus** on `http://localhost:9000` (metrics)

#### 4. Initialize Databases
```bash
docker compose exec api python -c "from api.db import init_dbs; init_dbs()"
```

#### 5. Verify Installation
```bash
# Check all services are running
docker compose ps

# Access the UI
open http://localhost:3000
# Login with username: admin, password: (from .env)

# Check CouchDB admin
open http://localhost:5984/_utils
# Login with admin credentials from .env
```

### Option B: Local Development

For development on a single machine.

#### 1. Install Dependencies
```bash
# Using mamba (recommended)
mamba env create -f environment.yml
mamba activate moirai

# OR using pip
pip install -r requirements.txt
```

#### 2. Set Up External Services
```bash
# Start CouchDB (macOS with Homebrew)
brew install couchdb
brew services start couchdb

# Start Redis
brew install redis
brew services start redis

# Start Ollama (for LLM, optional)
# Download from https://ollama.ai
ollama pull llama2
ollama serve
```

#### 3. Set Environment Variables
```bash
export COUCHDB_URI=http://localhost:5984/
export COUCHDB_USER=admin
export COUCHDB_PASSWORD=password
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=password
export JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export REDIS_PASSWORD=redis_password
export DEFAULT_LLM_PROVIDER=ollama
export MODEL_NAME=llama2
export OLLAMA_BASE_URL=http://localhost:11434
```

#### 4. Initialize Databases
```bash
python -c "from api.db import init_dbs; init_dbs()"
```

#### 5. Start Services (3 Terminal Windows)
```bash
# Terminal 1: Flask API
python main.py

# Terminal 2: MCP Server
python mcp_server.py

# Terminal 3: Worker & Scheduler
python run_worker.py
```

#### 6. Start UI (separate terminal)
```bash
cd ui
yarn install
yarn dev
```

Access at `http://localhost:5173`

---

## Part 2: User & Feed Management

### Create Admin User
```bash
docker compose exec api python -c "
from api.auth import create_admin
create_admin('username', 'password')
"
```

### Create Regular User
```bash
docker compose exec api python -c "
from api.auth import create_user
create_user('username', 'password', is_admin=False)
"
```

### Add RSS Feeds

#### Via Admin UI (Easiest)
1. Login to `http://localhost:3000` as admin
2. **Click "Feeds" column header** → "Add Feed"
3. **Enter RSS URL:** `https://example.com/feed.xml`
4. **Enter Feed Name:** "Tech News"
5. **Click Add**

#### Via API (Programmatic)
```bash
curl -X POST http://localhost:8088/api/feeds \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Tech News",
    "url": "https://example.com/feed.xml",
    "category": "Technology"
  }'
```

### Popular Feed Sources

#### Technology
- Hacker News: `https://news.ycombinator.com/rss`
- TechCrunch: `https://feeds.techcrunch.com/feed/`
- The Verge: `https://www.theverge.com/rss/index.xml`
- ArXiv (AI/ML): `http://arxiv.org/rss/cs.AI/recent`

#### Business & Markets
- Reuters: `https://feeds.reuters.com/finance/...`
- CNBC: `https://feeds.cnbc.com/id/100003114/`
- Bloomberg: `https://feeds.bloomberg.com/markets/...`

#### Science
- Nature: `https://www.nature.com/nature.rss`
- Science Daily: `https://www.sciencedaily.com/rss/all.xml`
- MIT News: `https://news.mit.edu/rss/feed`

#### Industry-Specific
- Search your industry + "RSS feed"
- Most news sites have `/feed` or `/rss` endpoints

---

## Part 3: Agent Configuration

Agents are AI workers that automatically synthesize articles into Events and detect Trends.

### Types of Agents

**SCHEDULED Agents** — Run on a timer
- ✅ Check for stale events (no new articles in 3 days)
- ✅ Summarize daily trends
- ✅ Generate reports

**ON_NEW_ARTICLE Agents** — Run when articles arrive
- ✅ Create events from new articles (groups related articles)
- ✅ Annotate articles with importance
- ✅ Tag articles by industry/topic

### Configure Default Agents

Moirai comes with pre-configured agents. To view/edit:

#### 1. Via Admin UI
```
Coming soon in v0.7 — for now use CouchDB admin UI
```

#### 2. Via CouchDB Admin
1. Open `http://localhost:5984/_utils` (Fauxton UI)
2. **Select "agent_configs" database**
3. **View documents** to see existing agents
4. **Edit agent properties:**
   - `trigger_type`: `SCHEDULED` or `ON_NEW_ARTICLE`
   - `schedule_interval`: `"1h"`, `"2d"`, etc.
   - `status`: `ACTIVE` or `DISABLED`
   - `llm_model_config`: Which LLM to use

#### 3. Example: Create Custom Agent
```json
{
  "_id": "my-custom-agent",
  "name": "Daily Tech Digest",
  "userspace": "default-workspace-uuid",
  "trigger_type": "SCHEDULED",
  "schedule_interval": "24h",
  "logic_module": "tasks.agent_logic.create_event_from_articles",
  "status": "ACTIVE",
  "llm_model_config": {
    "provider": "openai",
    "model": "gpt-4"
  }
}
```

### Disable Problematic Agents

If an agent is causing issues:

1. Open CouchDB admin UI
2. Find the agent in `agent_configs`
3. Set `"status": "DISABLED"`
4. Click Save

The agent will no longer run. Check server logs for error details.

---

## Part 4: Monitoring & Maintenance

### Check System Health

#### via Docker
```bash
# See all services running
docker compose ps

# View logs
docker compose logs -f api

# Check disk usage
docker system df
```

#### via Prometheus (Metrics)
1. Open `http://localhost:9000`
2. Look for:
   - `moirai_articles_total` — Total articles ingested
   - `moirai_agents_executed_total` — Agent executions
   - `moirai_errors_total` — System errors

### Common Issues & Solutions

#### Issue: "High memory usage"
```bash
# Check which service is using memory
docker stats

# Restart the problematic service
docker compose restart api
```

#### Issue: "No articles appearing"
```bash
# Check feed ingestion
docker compose logs -f api | grep "feed"

# Manually trigger feed fetch
curl http://localhost:8088/api/admin/ingest \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Issue: "Agents not running"
```bash
# Check agent orchestrator logs
docker compose logs -f mcp_server | grep "AgentOrchestrator"

# Verify Redis is running
docker compose exec redis redis-cli ping
# Should return: PONG
```

#### Issue: "CouchDB running out of disk"
```bash
# Check disk usage
docker compose exec couchdb du -sh /opt/couchdb/data

# Compact databases (reduces disk usage)
curl -X POST http://localhost:5984/articles/_compact \
  -u admin:password
```

### Backup & Restore

#### Backup CouchDB
```bash
# Full backup
docker compose exec couchdb couchdb-backup \
  -b /opt/couchdb/backup \
  -u admin -p password

# Or simple: copy the data directory
docker cp moirai-couchdb:/opt/couchdb/data ./backup/couchdb-$(date +%Y%m%d)
```

#### Restore from Backup
```bash
docker compose down
docker cp ./backup/couchdb-20240315 moirai-couchdb:/opt/couchdb/data
docker compose up -d couchdb
```

### Database Maintenance

#### Compact Databases (Reduce Disk Size)
```bash
# Compact articles database
curl -X POST http://localhost:5984/articles/_compact \
  -u admin:password

# Compact all databases
for db in articles feeds issues config agent_configs; do
  curl -X POST http://localhost:5984/$db/_compact -u admin:password
done
```

#### Clean Old Articles
```bash
# Articles older than 30 days are auto-deleted based on ARTICLE_EXPIRATION_DAYS
# To manually delete, use CouchDB query
curl -X POST http://localhost:5984/articles/_find \
  -H "Content-Type: application/json" \
  -u admin:password \
  -d '{
    "selector": {
      "published": {"$lt": "2024-02-13T00:00:00Z"}
    }
  }'
```

---

## Part 5: Security Best Practices

### 1. Change Default Passwords
```env
# In .env, set strong passwords
ADMIN_PASSWORD=<40-char random string>
COUCHDB_PASSWORD=<40-char random string>
JWT_SECRET_KEY=<hex string>
REDIS_PASSWORD=<40-char random string>
```

### 2. Enable HTTPS
```bash
# Use reverse proxy (nginx/traefik) in front of Moirai
# Configure SSL certificates via Let's Encrypt
```

### 3. Enable CSRF Protection
Enabled by default. Disable only for testing:
```env
DISABLE_CSRF=false  # Keep as false in production
```

### 4. Limit Rate Limiting
```env
DISABLE_RATE_LIMIT=false  # Keep as false in production
```

### 5. Restrict Public Read
```env
ALLOW_PUBLIC_READ=false  # Set to false unless you want public access
```

### 6. Rotate JWT Secrets Periodically
```bash
# Every 90 days, generate new JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"
# Update .env and restart services
```

### 7. Regular Updates
```bash
# Check for updates monthly
git pull origin main
docker compose pull
docker compose up -d --build
```

---

## Part 6: Scaling for Production

### For 100-1000 users

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  api:
    replicas: 3  # Multiple API instances
    environment:
      WORKERS: 4  # Gunicorn workers

  couchdb:
    replicas: 3  # CouchDB cluster

  redis:
    # Single Redis with replication to standby
```

### For 1000+ users

- **Split into microservices:** API, MCP Server, Worker separately
- **Use managed CouchDB:** AWS DynamoDB compatible, or hosted Couchbase
- **Use managed Redis:** AWS ElastiCache, Redis Cloud
- **Add CDN:** CloudFront for UI assets
- **Monitor with Prometheus + Grafana**
- **Centralized logging:** ELK Stack or CloudWatch

---

## Part 7: Support & Updates

### Getting Help

- **Bug reports:** GitHub Issues with logs (sanitized)
- **Feature requests:** GitHub Discussions
- **Community:** Slack workspace

### Updating Moirai

```bash
cd moirai
git pull origin main

# Update Docker images
docker compose pull

# Restart with new images
docker compose up -d

# If database schema changed, run migrations
docker compose exec api python -c "from api.db import init_dbs; init_dbs()"
```

### Version History

- **v0.6.0** (latest) — Agent orchestrator, issue-raise wizard, lifespan view
- **v0.5.x** — Basic feed aggregation & article synthesis
- **v0.4.x** — Alpha release

---

## Quick Reference

| Task | Command |
|------|---------|
| Start services | `docker compose up -d` |
| Stop services | `docker compose down` |
| View logs | `docker compose logs -f api` |
| Access UI | `http://localhost:3000` |
| Access CouchDB admin | `http://localhost:5984/_utils` |
| Create user | `docker compose exec api python -c "from api.auth import create_user; create_user(...)"` |
| Add feed | Use Admin UI → Feeds → Add |
| Check health | `docker compose ps` or `http://localhost:9000` |
| Backup | `docker cp moirai-couchdb:/opt/couchdb/data ./backup/` |

---

**Questions?** Check the main [README.md](../README.md) or ask on GitHub Discussions.
