# LLM Configuration Guide

Moirai supports multiple LLM providers to power its agentic capabilities. You can configure these settings directly from the web interface.

## Accessing Configuration

1. Open the Moirai UI (default: [http://localhost:8088](http://localhost:8088)).
2. Navigate to the **Settings** page via the sidebar or top navigation.
3. Scroll to the **LLM Endpoint Configuration** section.

## Supported Providers

### 1. Ollama (Default)

Ideal for running local models without external API costs.

- **Endpoint URL:** Defaults to `http://host.docker.internal:11434/v1`.
  - *Note: If running Moirai in Docker, `host.docker.internal` allows it to access Ollama running on your host machine.*
- **Model Name:** Select a model installed on your Ollama instance (e.g., `llama3`, `gemma`).
  - If the dropdown is empty, ensure your Ollama instance is running and reachable.

### 2. OpenAI

Use powerful cloud models like GPT-4.

- **API Key:** Enter your OpenAI API Key (starts with `sk-...`).
- **Model Name:** Click **Fetch Models** to load available models associated with your key, or manually enter a model name (e.g., `gpt-4-turbo`, `gpt-3.5-turbo`).

### 3. Google Gemini

Use Google's Gemini models.

- **API Key:** Enter your Google Gemini API Key.
- **Model Name:** Click **Fetch Models** to see available models, or manually enter one (e.g., `gemini-1.5-pro`, `gemini-1.5-flash`).

### 4. AISA (in-cluster inference proxy)

AISA is an in-cluster, OpenAI-compatible inference proxy that handles identity, quotas,
budgets and provider isolation upstream of the application. AISA support in Moirai is
**additive**: Ollama, OpenAI and Gemini keep working exactly as before, and direct keys are
never routed through AISA.

- **Credentials:** none are entered in the UI. AISA reconciles a Kubernetes `Secret` into
  Moirai's namespace and the pods read it from the environment (see below).
- **Model Name:** click **Fetch Models** to list the models that currently have a healthy
  backend (`GET /v1/models` through the proxy), or type a name. The consumer's default model
  from the Secret (`OPENAI_MODEL`) is pre-filled when present.
- The **AISA** radio button is disabled when the deployment has no AISA credentials.

#### Environment contract

The AISA-managed Secret carries the standard OpenAI-compatible keys. Moirai reads them
under its own names so they never collide with a direct OpenAI key:

| Secret key | Moirai env var (Helm mapping) | Also accepted (standalone / `envFrom`) |
|---|---|---|
| `OPENAI_BASE_URL` | `AISA_BASE_URL` | `OPENAI_BASE_URL` |
| `OPENAI_API_KEY` | `AISA_API_KEY` (or `AISA_API_KEY_FILE`) | `OPENAI_API_KEY` *(only when `OPENAI_BASE_URL` is set)* |
| `OPENAI_MODEL` / `LLM_MODEL` | `AISA_MODEL` | `OPENAI_MODEL`, `LLM_MODEL` |

Resolution order for inference credentials, per provider selection:

1. **Direct provider selected** (`openai`, `gemini`, explicit `ollama` endpoint): the
   userspace's own key / endpoint, falling back to `OPENAI_API_KEY` / `GEMINI_API_KEY` /
   `OLLAMA_BASE_URL` from the environment. AISA variables are ignored.
2. **`aisa` selected**: `AISA_BASE_URL` + `AISA_API_KEY` from the environment (the
   AISA Secret). The userspace document never stores AISA credentials.
3. **Nothing configured**: the local Ollama default (`http://host.docker.internal:11434/v1`).

Unknown keys in the Secret are ignored. Set `DEFAULT_LLM_PROVIDER=aisa` to make AISA the
process-wide default for new userspaces and the annotation worker (`MODEL_NAME` still wins
over the Secret's default model).

Every service logs the resolved provider, base URL and model at startup
(`LLM config: ...`); keys are never logged.

#### Kubernetes (Helm)

1. Declare Moirai as a consumer in AISA (Admin UI → Consumers, or Consul KV
   `aisa/consumers/moirai`): namespace = Moirai's namespace, target secret =
   `moirai-aisa-key`, quota profile `interactive` (chat) or `batch` (background only).
2. Enable the integration in your values file:

   ```yaml
   aisa:
     enabled: true
     secretName: moirai-aisa-key
     reloader: true        # optional: Stakater Reloader restarts pods on key rotation
   llm:
     provider: aisa        # optional: make AISA the process-wide default provider
   ```

   The chart binds the Secret with `optional: true`, so pods start even before AISA has
   reconciled it. Environment variables are read only at container start: if the Secret
   appears later, or when AISA rotates the key (default every 30 days, 7-day grace),
   restart the deployments or enable `aisa.reloader`.
3. Moirai pods run with `automountServiceAccountToken: false`, so model discovery uses the
   proxy's HTTP `GET /v1/models` (Level 1) rather than the `Model` CRD.

Verify from inside the cluster:

```bash
kubectl get secret moirai-aisa-key -n <namespace>
kubectl run aisa-test -n <namespace> --rm -it --restart=Never \
  --image=curlimages/curl --env-from=secret/moirai-aisa-key -- \
  curl -fsS -H "Authorization: Bearer $OPENAI_API_KEY" "$OPENAI_BASE_URL/models"
```

#### Standalone / Docker Compose

Set `AISA_BASE_URL`, `AISA_API_KEY` (or `AISA_API_KEY_FILE`) and optionally `AISA_MODEL`
in `.env`; `docker-compose.yml` passes them through to the api, worker and mcp-server
services. Leave them empty to run without AISA.

#### Errors and quotas

- **HTTP 429** (`aisa_quota_exceeded`): the consumer's sliding one-hour token quota is
  exhausted. The OpenAI SDK retries honouring `Retry-After`; chat shows a quota message.
- **HTTP 503**: no healthy backend serves the requested model. Pick another model from the
  AISA list.
- The proxy passes the upstream `usage` object through unchanged, so token accounting on
  responses is unaffected.

## Article Annotation

The annotation worker classifies every new article (title + summary) into 1–3
topics from a closed vocabulary (`TOPIC_VOCABULARY` in `tasks/annotator.py`),
a priority and a sentiment. Labels the model invents are mapped through
`TOPIC_ALIASES` or dropped, so only vocabulary labels reach the UI.

Each stored annotation carries `annotation_version`. When the prompt or the
vocabulary changes, bump `ANNOTATION_VERSION` and regenerate the old ones from
inside the worker pod:

```bash
python -m scripts.reannotate_outdated --dry-run                   # count only, seconds
python -m scripts.reannotate_outdated --dry-run --list --limit 50 # also list ids
python -m scripts.reannotate_outdated --days 3 --limit 500        # last 3 days
python -m scripts.reannotate_outdated --userspace <uuid>          # one userspace
python -m scripts.reannotate_outdated --limit 5000 --concurrency 2
```

`--days` defaults to 7: articles expire after `ARTICLE_EXPIRATION_DAYS`, so
regenerating older ones is wasted model time (each call costs seconds on CPU).

**The job is interruptible and resumable.** Each finished article is stamped
with the current version as soon as it is stored and is never listed again.
Stopping the run (Ctrl-C, `kubectl delete pod`, a timeout) loses at most the
articles in flight, and re-running the same command continues with exactly
what is left. Work through a large backlog in batches with `--limit`.

What the operator sees:

- At start, the number of outdated articles in scope. It comes from the
  `annotation/by_version` reduce view (created by `init_db` at startup), so it
  takes seconds; the first query after a deploy builds the index once.
  `--dry-run` stops after this count.
- Every `--progress-every` articles (default 25): `done/total (pct), failed,
  elapsed, s/article, ETA`.
- At the end, the same line plus how many articles are still outdated, so no
  separate dry run is needed to decide whether to run another batch.

`--concurrency N` (default 1) keeps up to N articles in flight. The call is
bound by the annotation backend, so the gain depends on how many requests the
backend serves in parallel: Ollama queues requests beyond `OLLAMA_NUM_PARALLEL`,
and an NPU backend may run only one inference at a time. Raise it in small steps
and watch `s/article`; the worker keeps annotating new articles on the same
backends meanwhile.

The script uses the same backends and language routing as the worker, so a
paused or missing model affects it the same way.

## Switching Providers

To switch between providers:

1. Select the desired provider radio button (Ollama, OpenAI, Gemini, or AISA).
2. Ensure the configuration for that provider is correct.
3. Click **Save All Settings** at the bottom of the page.
4. Navigate back to the **Chat** page to start using the new model.

## Troubleshooting

- **"Fetch Models" fails:**
  - Check if the API Key is correct.
  - Check internet connectivity from the Moirai container.
  - For Ollama, ensure CORS is configured if running on a different origin, or that the container can reach the host.
- **Chat errors:**
  - Check the container logs (`docker compose logs -f api`) for detailed error messages.
  - Verify that the selected model actually supports chat completion / tool calling.
