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
from typing import Any, Optional

import requests

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


def _get_llm_provider() -> Any:
    """Create an LLM provider from environment configuration."""
    factory = LLMProviderFactory()
    llm_endpoint = os.environ.get("DEFAULT_LLM_PROVIDER", "ollama")

    # Select the API key matching the chosen provider to avoid passing
    # the wrong credential (e.g. OpenAI key to a Gemini provider).
    api_key = ""
    if llm_endpoint == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
    elif llm_endpoint == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY", "")

    # OLLAMA_BASE_URL is set via docker-compose.yml; no hardcoded default
    # to avoid SonarCloud S5332 (http:// in source).
    ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "")
    return factory.get_provider(llm_endpoint, api_key, ollama_base_url)


def annotate_article(title: str, summary: str, model: Optional[str] = None) -> Optional[dict]:
    """Classify an article using the configured LLM provider.

    Args:
        title: The article title.
        summary: The article summary/description text.
        model: Optional model name override.

    Returns:
        A dict with keys ``topics``, ``priority``, ``sentiment``,
        or ``None`` if annotation fails.
    """
    if not title:
        return None

    model_name = model or os.environ.get("MODEL_NAME", "llama3.1")

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

    try:
        provider = _get_llm_provider()
        response = provider.create_chat_completion(
            messages=messages,
            model=model_name,
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
        return _validate_annotation(result)

    except json.JSONDecodeError as e:
        logger.warning(f"Annotation JSON parse error for '{title[:60]}': {e}")
        return None
    except Exception as e:
        logger.error(f"Annotation LLM error for '{title[:60]}': {e}")
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
