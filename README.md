# Moirai - MCP-Powered GenAI Press Review Service

Moirai is a GenAI-native press review platform designed for the Model Context Protocol (MCP) ecosystem. It allows AI agents to aggregate RSS feeds, synthesize them into "Events," and track long-term "Trends" across isolated userspaces.

## Project Overview

Moirai acts as a synthesis engine that LLM agents use to analyze news. It consists of:

* **MCP Server (Port 8090):** The primary interface for AI agents. Provides tools to fetch news, create events, and track trends via Server-Sent Events (SSE).
* **Admin UI (Port 8088):** A Vue.js dashboard for humans to review the agent's work, manage feeds, and visualize the data.
* **REST API (Port 8088):** The backend for the UI and external integrations.

**Architecture Details:** See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick Start

### 1. Run with Docker Compose

The easiest way to run the full stack (UI, API, Worker, MCP Server, Database):

```bash
docker compose up --build
```

This starts the following services:
* `api` — Flask REST API (stateless, scalable web server)
* `worker` — Enrichment worker (long-running CouchDB changes-feed listener, single instance)
* `ui` — Vue.js frontend (served by Nginx)
* `nginx` — Reverse proxy routing traffic to `api` and `ui`
* `mcp-server` — FastMCP server for agent tool calls
* `couchdb` — Database
* `redis` — Cache

**Endpoints:**
* **Admin UI:** [http://localhost:8088](http://localhost:8088)
* **MCP Server:** [http://localhost:8090/sse](http://localhost:8090/sse)
* **API:** [http://localhost:8088/api](http://localhost:8088/api)

To run the feed scheduler manually (one cycle, then exit):

```bash
docker compose run --rm api python run_scheduler.py
```

### 2. Configure Chat

The UI includes a Chat interface to interact with the Agent.

1. Go to **Chat** in the UI.
2. Open **Settings**.
3. Configure your LLM endpoint (e.g., Ollama at `http://host.docker.internal:11434/v1`) and model (e.g., `llama3.1`).

Dashboard contextual chat is also available directly from cards:

- Articles: open chat with article context, and use **Raise as Issue**
- Issues/Trends: open chat with issue context, and use **Refine Description**
- Feeds: open chat with feed context

Contextual chat sessions are persisted and can be resumed from the `/chat` page.

For article issue creation, the dashboard supports a guided **Raise Issue wizard** that asks clarifying questions before submitting a structured issue-creation prompt.

Chat responses expose timing metadata, and the UI shows per-response duration to help identify slow requests.

### 3. Agent Workflow

1. **Add Feeds:** Ask the agent to "Add the RSS feed for Hacker News".
2. **Synthesize:** Ask the agent to "Check recent articles and create events for major stories".
3. **Review:** Use the dashboard to see the Events and Trends created by the agent.

## Development

### Project Structure

```
.
├── api/             # Flask REST API (Port 8088)
├── ui/              # Vue.js Frontend
├── mcp_server.py    # FastMCP Server (Port 8090)
├── tasks/           # Background tasks and helpers
├── tests/           # Unit and integration tests
├── helm/            # Kubernetes charts
└── docker-compose.yml
```

### Manual Setup (Local Dev)

If you want to run components individually without Docker:

1. **Install Miniforge (if needed):**

    ```bash
    # Linux x86_64
    curl -L -o /tmp/Miniforge3.sh https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
    bash /tmp/Miniforge3.sh
    ```

1. **Create/Use a Miniforge Environment:**

    ```bash
    mamba env create -f environment.yml
    mamba activate moirai
    ```

    If `mamba` is not found after installing Miniforge, run `~/miniforge3/bin/conda init bash` once and open a new shell.

1. **Node.js and Yarn:** the UI needs the Node major in `ui/.nvmrc` and Yarn 4 through Corepack. The commands below use [nvm](https://github.com/nvm-sh/nvm#installing-and-updating) to install Node; install nvm first, or install that Node major another way and skip the `nvm install` line. Node 25 and later no longer bundle Corepack, so install it once per Node version:

    ```bash
    cd ui
    nvm install          # reads ui/.nvmrc
    npm install -g corepack && corepack enable
    yarn install         # also installs the git hooks, see below
    ```

1. **Git hooks:** `yarn install` in `ui/` installs one pre-commit hook for the whole repository (husky, `.husky/pre-commit`). It runs `prettier` on staged UI files and, when Python or YAML files are staged, `black`, `ruff` and the hygiene hooks from `.pre-commit-config.yaml`. The Python half needs `pre-commit` on `PATH`, so commit from a shell with the `moirai` environment active. Do not run `pre-commit install`: husky owns `core.hooksPath`. CI enforces `ruff`, `black --check` and `prettier --check` regardless; the hygiene hooks (trailing whitespace, end of file, YAML syntax, large files) run only locally.

1. **Database:** Ensure CouchDB is running (e.g., via `docker compose up couchdb`).
2. **API:**

    ```bash
    mamba run -n moirai python main.py
    ```

3. **MCP Server:**

    ```bash
    mamba run -n moirai python mcp_server.py
    ```

4. **UI:**

    ```bash
    cd ui
    yarn install
    yarn dev
    ```

### Local Testing Policy

Before committing and pushing changes, run relevant local tests for the area you touched (API, UI, MCP, or integration). If local tests cannot be run, explicitly document why (and what you did instead) in the commit message body or pull request description.

## Documentation

* [Architecture](docs/ARCHITECTURE.md)
* [LLM Configuration](docs/llm-configuration.md) - How to configure Ollama, OpenAI, Gemini, and the in-cluster AISA proxy.
* [External REST API](docs/EXTERNAL_API.md) - Documentation for `/mcp` endpoints on the REST API.
* [Release Process](docs/RELEASE.md) - Release and RC checklist.
* [Example Usage](EXAMPLES.md)

## License

MIT License
