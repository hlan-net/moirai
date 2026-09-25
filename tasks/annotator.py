"""AI annotation module for articles.

Uses the configured LLM provider to classify articles with:
- topics: list of topic labels (e.g., "technology", "politics", "science")
- priority: "low" | "medium" | "high"
- sentiment: "positive" | "neutral" | "negative"

Annotations are stored directly on the article document in CouchDB
under the ``annotations`` key.
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests
from openai import NotFoundError

from api.db_config import get_couchdb_uri
from api.llm.factory import LLMProviderFactory

logger = logging.getLogger(__name__)

ANNOTATION_SYSTEM_PROMPT = """You are a news article classifier. Given an article's title and summary, respond with a JSON object containing exactly these fields:

- "topics": an array of 1-3 short topic labels (lowercase, e.g. "technology", "politics", "climate", "finance", "health", "science", "sports", "entertainment", "security", "business")
- "priority": one of "low", "medium", or "high" based on newsworthiness and impact
- "sentiment": one of "positive", "neutral", or "negative" based on the overall tone

Respond ONLY with the JSON object, no other text."""

ANNOTATION_USER_TEMPLATE = """Title: {title}
Summary: {summary}"""

DEFAULT_ANNOTATION_MODEL = "llama3.1"

# When a backend reports its model as missing (HTTP 404), pause that backend
# instead of sending one doomed request per incoming article.
MODEL_NOT_FOUND_BACKOFF_SECONDS = 600
_paused_until: dict[str, float] = {}


@dataclass(frozen=True)
class AnnotationBackend:
    """An LLM endpoint + model used for annotation.

    ``primary`` is the optional dedicated annotation backend (e.g. a
    low-power NPU running hailo-ollama) configured via ``ANNOTATION_*`` env
    vars. ``default`` is the general LLM configuration (``DEFAULT_LLM_PROVIDER``,
    ``OLLAMA_BASE_URL``, ``MODEL_NAME``) and serves as the fallback.
    """

    name: str
    provider: str
    base_url: str
    model: str


def _default_backend(model: Optional[str] = None) -> AnnotationBackend:
    # OLLAMA_BASE_URL is set via docker-compose.yml; no hardcoded default
    # to avoid SonarCloud S5332 (http:// in source).
    return AnnotationBackend(
        name="default",
        provider=os.environ.get("DEFAULT_LLM_PROVIDER", "ollama"),
        base_url=os.environ.get("OLLAMA_BASE_URL", ""),
        model=model or os.environ.get("MODEL_NAME", DEFAULT_ANNOTATION_MODEL),
    )


def _primary_backend() -> Optional[AnnotationBackend]:
    base_url = os.environ.get("ANNOTATION_OLLAMA_BASE_URL", "")
    model = os.environ.get("ANNOTATION_MODEL_NAME", "")
    if not (base_url and model):
        return None
    return AnnotationBackend(
        name="primary", provider="ollama", base_url=base_url, model=model
    )


def _primary_languages() -> set[str]:
    raw = os.environ.get("ANNOTATION_LANGUAGES", "en")
    return {lang.strip().lower() for lang in raw.split(",") if lang.strip()}


def _configured_backends() -> list[AnnotationBackend]:
    primary = _primary_backend()
    return ([primary] if primary else []) + [_default_backend()]


def _backends_for(
    language: Optional[str], model: Optional[str] = None
) -> list[AnnotationBackend]:
    """Backends to try, in order, for an article in *language*.

    Small NPU models only understand a few languages, so the primary backend
    is used only for languages listed in ``ANNOTATION_LANGUAGES``; everything
    else goes straight to the default backend. A primary failure (invalid
    output, error) falls back to the default backend.
    """
    backends = []
    primary = _primary_backend()
    if primary and language and language.lower() in _primary_languages():
        backends.append(primary)
    backends.append(_default_backend(model))
    return backends


def _get_llm_provider(backend: Optional[AnnotationBackend] = None) -> Any:
    """Create an LLM provider for *backend* (default: env configuration)."""
    backend = backend or _default_backend()

    # Select the API key matching the chosen provider to avoid passing
    # the wrong credential (e.g. OpenAI key to a Gemini provider).
    api_key = ""
    if backend.provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
    elif backend.provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY", "")

    return LLMProviderFactory().get_provider(
        backend.provider, api_key, backend.base_url
    )


def _describe(backend: AnnotationBackend) -> str:
    return f"'{backend.model}' on {backend.provider} ({backend.name})"


def _pause_backend(backend: AnnotationBackend, reason: str) -> None:
    _paused_until[backend.name] = time.monotonic() + MODEL_NOT_FOUND_BACKOFF_SECONDS
    logger.error(
        f"{reason} — pausing {backend.name} annotation backend for "
        f"{MODEL_NOT_FOUND_BACKOFF_SECONDS}s. Configure an installed model."
    )


def _backend_paused_for(backend: AnnotationBackend) -> float:
    return max(0.0, _paused_until.get(backend.name, 0.0) - time.monotonic())


def annotation_paused_for() -> float:
    """Seconds until every configured backend is usable again (0 when active).

    Non-zero while any backend is paused, so the worker holds articles back
    rather than skipping the ones that backend would have handled.
    """
    return max(_backend_paused_for(b) for b in _configured_backends())


def _model_names_match(wanted: str, available: str) -> bool:
    # Ollama treats "name" and "name:latest" as the same model.
    def norm(name: str) -> str:
        return name if ":" in name else f"{name}:latest"

    return norm(wanted) == norm(available)


def _list_models(backend: AnnotationBackend) -> list[str]:
    try:
        return _get_llm_provider(backend).list_models()
    except Exception:
        if backend.provider != "ollama":
            raise
    # hailo-ollama lacks the OpenAI-compatible /v1/models; use the native API.
    root = backend.base_url.rstrip("/").removesuffix("/v1")
    res = requests.get(f"{root}/api/tags", timeout=10)
    res.raise_for_status()
    return [m["name"] for m in res.json().get("models", [])]


def check_annotation_model() -> bool:
    """Verify each configured annotation backend has its model installed.

    Returns False (and pauses the affected backend) only when a model list
    was fetched and the model is not in it. An unreachable provider is logged
    but not treated as a missing model.
    """
    all_ok = True
    for backend in _configured_backends():
        try:
            available = _list_models(backend)
        except Exception as e:
            logger.warning(
                f"Could not list models to verify annotation model "
                f"{_describe(backend)}: {e}"
            )
            continue

        if any(_model_names_match(backend.model, m) for m in available):
            logger.info(f"Annotation model {_describe(backend)} available")
            continue

        all_ok = False
        _pause_backend(
            backend,
            f"Annotation model {_describe(backend)} not found "
            f"(available: {', '.join(sorted(available)) or 'none'})",
        )
    return all_ok


def annotate_article(
    title: str,
    summary: str,
    model: Optional[str] = None,
    language: Optional[str] = None,
) -> Optional[dict]:
    """Classify an article using the configured LLM backends.

    Args:
        title: The article title.
        summary: The article summary/description text.
        model: Optional model name override for the default backend.
        language: ISO 639-1 code of the article; decides whether the primary
            annotation backend may be used.

    Returns:
        A dict with keys ``topics``, ``priority``, ``sentiment``,
        or ``None`` if annotation fails.
    """
    if not title:
        return None

    # Truncate very long summaries to save tokens
    truncated_summary = (summary or "")[:1000]

    messages = [
        {"role": "system", "content": ANNOTATION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": ANNOTATION_USER_TEMPLATE.format(
                title=title, summary=truncated_summary
            ),
        },
    ]

    for backend in _backends_for(language, model):
        if _backend_paused_for(backend) > 0:
            continue
        result = _annotate_with(backend, messages, title)
        if result is not None:
            return result
    return None


def _annotate_with(
    backend: AnnotationBackend, messages: list[dict], title: str
) -> Optional[dict]:
    try:
        provider = _get_llm_provider(backend)
        response = provider.create_chat_completion(
            messages=messages,
            model=backend.model,
            tools=None,
            tool_choice=None,
        )

        content = response.choices[0].message.content.strip()
        # Strip markdown code fences if the model wraps the JSON
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            if content.endswith("```"):
                content = content[: -len("```")]
            content = content.strip()

        result = json.loads(content)

        # Validate and normalise
        annotation = _validate_annotation(result)
        if annotation is None:
            logger.warning(
                f"Invalid annotation from {_describe(backend)} for '{title[:60]}'"
            )
        return annotation

    except json.JSONDecodeError as e:
        logger.warning(
            f"Annotation JSON parse error from {_describe(backend)} "
            f"for '{title[:60]}': {e}"
        )
        return None
    except NotFoundError as e:
        _pause_backend(backend, f"Annotation model {_describe(backend)} not found: {e}")
        return None
    except Exception as e:
        logger.error(
            f"Annotation LLM error from {_describe(backend)} for '{title[:60]}': {e}"
        )
        return None


def _validate_annotation(raw: dict) -> Optional[dict]:
    """Validate and normalise an annotation dict from the LLM."""
    topics = raw.get("topics")
    priority = raw.get("priority")
    sentiment = raw.get("sentiment")

    if not isinstance(topics, list) or not topics:
        return None
    if priority not in ("low", "medium", "high"):
        return None
    if sentiment not in ("positive", "neutral", "negative"):
        return None

    # Normalise topics: lowercase strings, max 3
    clean_topics = [str(t).lower().strip() for t in topics[:3] if t]
    if not clean_topics:
        return None

    return {
        "topics": clean_topics,
        "priority": priority,
        "sentiment": sentiment,
    }


def store_annotation(article_id: str, annotation: dict) -> bool:
    """Write the annotation dict onto the article document in CouchDB.

    Uses GET-then-PUT to handle ``_rev`` automatically.

    Args:
        article_id: The CouchDB document ID of the article.
        annotation: The annotation dict (topics, priority, sentiment).

    Returns:
        True if the update succeeded, False otherwise.
    """
    couchdb_url = get_couchdb_uri()
    doc_url = f"{couchdb_url}articles/{article_id}"

    try:
        # Fetch current doc to get _rev
        res = requests.get(doc_url, timeout=10)
        if res.status_code != 200:
            logger.error(
                f"Failed to fetch article {article_id} for annotation: {res.status_code}"
            )
            return False

        doc = res.json()
        doc["annotations"] = annotation
        doc["annotated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        put_res = requests.put(doc_url, json=doc, timeout=10)
        if put_res.status_code in (200, 201):
            return True
        else:
            logger.error(
                f"Failed to store annotation for {article_id}: "
                f"{put_res.status_code} {put_res.text}"
            )
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error storing annotation for {article_id}: {e}")
        return False
