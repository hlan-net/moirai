"""AI annotation module for articles.

Uses the configured LLM provider to classify articles with:
- topics: 1-3 labels from the closed ``TOPIC_VOCABULARY``
- priority: "low" | "medium" | "high"
- sentiment: "positive" | "neutral" | "negative"

Annotations are stored directly on the article document in CouchDB
under the ``annotations`` key.
"""

import json
import logging
import time
from dataclasses import replace
from typing import Any, Optional

import requests
from openai import NotFoundError

from api.db_config import get_couchdb_uri
from api.llm.catalog import (
    DEFAULT_MODEL,
    PURPOSE_ANNOTATION,
    ModelEntry,
    configured_models,
    legacy_default_entry,
    resolve_models,
)
from api.llm.factory import LLMProviderFactory

logger = logging.getLogger(__name__)

# Closed topic vocabulary. Anything the model returns outside this list is
# mapped through TOPIC_ALIASES or dropped, so invented labels never reach the
# UI (issue #249). Keep in sync with the prompt below.
TOPIC_VOCABULARY: tuple[str, ...] = (
    "politics",
    "world",
    "local",
    "business",
    "finance",
    "technology",
    "science",
    "climate",
    "health",
    "security",
    "crime",
    "sports",
    "culture",
    "entertainment",
    "obituary",
    "lifestyle",
    "general",
)

# Labels small models commonly produce → vocabulary entry.
TOPIC_ALIASES: dict[str, str] = {
    "tech": "technology",
    "economy": "business",
    "economics": "business",
    "markets": "finance",
    "environment": "climate",
    "energy": "climate",
    "medicine": "health",
    "military": "security",
    "defense": "security",
    "defence": "security",
    "war": "security",
    "terrorism": "security",
    "sport": "sports",
    "arts": "culture",
    "art": "culture",
    "theatre": "culture",
    "theater": "culture",
    "music": "culture",
    "film": "culture",
    "cinema": "culture",
    "literature": "culture",
    "books": "culture",
    "celebrity": "entertainment",
    "celebrities": "entertainment",
    "celebrity news": "entertainment",
    "television": "entertainment",
    "tv": "entertainment",
    "death": "obituary",
    "deaths": "obituary",
    "celebrity death": "obituary",
    "funeral": "obituary",
    "mortality": "obituary",
    "people": "obituary",
    "international": "world",
    "world news": "world",
    "local news": "local",
    "education": "general",
    "news": "general",
    "society": "general",
}

ANNOTATION_SYSTEM_PROMPT = """You are a news article classifier. Given an article's title and summary, respond with a JSON object containing exactly these fields:

- "topics": an array of 1-3 labels chosen ONLY from this list: "politics", "world", "local", "business", "finance", "technology", "science", "climate", "health", "security", "crime", "sports", "culture", "entertainment", "obituary", "lifestyle", "general"
- "priority": "high" for major breaking news with broad impact, "medium" for notable news of national or sector-wide interest, "low" for routine or niche items
- "sentiment": "positive", "neutral", or "negative" — the tone of the writing, not the seriousness of the subject. Plain factual reporting is "neutral" even when the subject is sad or serious.

Rules:
- Topics describe what the article is ABOUT. Do not derive topics from the nationality, religion, ethnicity or other group membership of people mentioned in it.
- A death notice, funeral or obituary is "obituary" plus the person's field (e.g. "culture" for an actor, "sports" for an athlete).
- The article may be in any language; the labels are always the English ones above.

Respond ONLY with the JSON object, no other text."""

ANNOTATION_USER_TEMPLATE = """Title: {title}
Summary: {summary}"""

# Bump when the prompt or vocabulary changes in a way that makes stored
# annotations stale. Stored on the article as ``annotation_version`` so
# outdated ones can be found and regenerated (scripts/reannotate_outdated.py).
ANNOTATION_VERSION = 2

# Map/reduce view that counts annotated articles by version, so "how many are
# still outdated" is a reduce query instead of a full Mango scan. Each article
# is emitted once under "*" (all userspaces) and once under its userspace:
# key = [scope, annotation_version or null, published]. Created by init_db().
ANNOTATION_DESIGN_DOC = "annotation"
ANNOTATION_VERSION_VIEW = "by_version"
ANNOTATION_ALL_SCOPE = "*"
ANNOTATION_VIEWS = {
    ANNOTATION_VERSION_VIEW: {
        "map": (
            "function(doc) {"
            " if (!doc.annotations) return;"
            " var v = doc.annotation_version === undefined"
            " ? null : doc.annotation_version;"
            " var p = doc.published === undefined ? null : doc.published;"
            " emit(['*', v, p], null);"
            " if (doc.userspace) emit([doc.userspace, v, p], null);"
            " }"
        ),
        "reduce": "_count",
    }
}

DEFAULT_ANNOTATION_MODEL = DEFAULT_MODEL

# When a backend reports its model as missing (HTTP 404), pause that backend
# instead of sending one doomed request per incoming article.
MODEL_NOT_FOUND_BACKOFF_SECONDS = 600
_paused_until: dict[str, float] = {}

# Annotation backends are model catalog entries (``api/llm/catalog.py``): the
# ``annotation`` purpose of LLM_CATALOG_FILE, or without one the legacy
# ``primary`` (ANNOTATION_* env vars) and ``default`` (DEFAULT_LLM_PROVIDER,
# OLLAMA_BASE_URL, MODEL_NAME) backends.
AnnotationBackend = ModelEntry


def _default_backend(model: Optional[str] = None) -> AnnotationBackend:
    return legacy_default_entry(model)


def _configured_backends() -> list[AnnotationBackend]:
    return configured_models(PURPOSE_ANNOTATION)


def _backends_for(
    language: Optional[str], model: Optional[str] = None
) -> list[AnnotationBackend]:
    """Backends to try, in order, for an article in *language*.

    Backends restricted to some languages (small NPU models) are skipped for
    other languages; a failure (invalid output, error) falls through to the
    next backend. *model* overrides the model of the last (fallback) backend.
    """
    backends = resolve_models(PURPOSE_ANNOTATION, language)
    if model and backends:
        backends[-1] = replace(backends[-1], model=model)
    return backends


def _get_llm_provider(backend: Optional[AnnotationBackend] = None) -> Any:
    """Create an LLM provider for *backend* (default: env configuration)."""
    backend = backend or _default_backend()

    # The entry selects the API key matching its provider, so the wrong
    # credential (e.g. OpenAI key to a Gemini provider) is never passed.
    return LLMProviderFactory().get_provider(
        backend.provider, backend.api_key(), backend.base_url
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

        content = response.choices[0].message.content
        result = json.loads(_extract_json(content))

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


def _extract_json(content: str) -> str:
    """Isolate the JSON object in a model reply.

    Small models wrap the object in code fences, add commentary after it,
    or (gemma3n) indent with the SentencePiece space marker U+2581, which
    is not JSON whitespace. Returns the text from the first ``{`` to the
    last ``}``; the caller's ``json.loads`` still decides validity.
    """
    content = content.replace("▁", " ")
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end < start:
        return content.strip()
    return content[start : end + 1]


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

    clean_topics = _normalise_topics(topics)
    if not clean_topics:
        return None

    return {
        "topics": clean_topics,
        "priority": priority,
        "sentiment": sentiment,
    }


def _normalise_topics(topics: list) -> list[str]:
    """Map raw model labels onto the closed vocabulary, max 3, order kept.

    Labels outside the vocabulary (after alias mapping) are dropped. If none
    survive, ``["general"]`` is returned so a valid priority/sentiment is
    still stored rather than leaving the article un-annotated.
    """
    result: list[str] = []
    for raw_topic in topics:
        if not raw_topic:
            continue
        label = str(raw_topic).lower().strip()
        label = TOPIC_ALIASES.get(label, label)
        if label in TOPIC_VOCABULARY and label not in result:
            result.append(label)
        if len(result) == 3:
            break
    if not result:
        return ["general"]
    # "general" only carries information when it is the sole topic.
    if len(result) > 1 and "general" in result:
        result.remove("general")
    return result


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
        doc["annotation_version"] = ANNOTATION_VERSION

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
