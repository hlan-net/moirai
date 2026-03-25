"""
Bluesky social export helpers.

Provides LLM-based post generation and atproto Client posting.
Used by the POST /api/issues/<id>/share endpoint and the
publish_to_bluesky MCP tool.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

BLUESKY_MAX_CHARS = 300
_OLLAMA_DEFAULT_ENDPOINT = "http://host.docker.internal:11434/v1"


def generate_bluesky_post_text(
    issue: dict,
    articles: list[dict],
    llm_config: dict,
) -> str:
    """Call the configured LLM to generate a ≤300-character Bluesky post.

    Falls back to a plain-text summary if the LLM call fails.
    """
    from api.llm.factory import LLMProviderFactory

    provider_name = llm_config.get("provider", "ollama")
    model = llm_config.get("model", "llama3.1")

    if provider_name == "openai":
        api_key = llm_config.get("openai_api_key") or ""
    elif provider_name == "gemini":
        api_key = llm_config.get("gemini_api_key") or ""
    else:
        api_key = ""

    ollama_base_url = llm_config.get("ollama_endpoint") or _OLLAMA_DEFAULT_ENDPOINT

    llm_provider = LLMProviderFactory().get_provider(provider_name, api_key, ollama_base_url)

    article_lines = []
    for art in articles[:5]:
        title = (art.get("title") or art.get("url") or "").strip()
        if title:
            article_lines.append(f"- {title[:120]}")

    article_context = "\n".join(article_lines) if article_lines else "(no linked articles)"

    prompt = (
        f"Write a Bluesky post (max {BLUESKY_MAX_CHARS} characters, no hashtags) "
        f"summarizing this news issue:\n\n"
        f"Title: {issue.get('logos', '')}\n"
        f"Description: {issue.get('description', '')}\n\n"
        f"Related articles:\n{article_context}\n\n"
        f"Reply with ONLY the post text, nothing else."
    )

    try:
        response = llm_provider.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            tools=None,
            tool_choice=None,
        )
        text = response.choices[0].message.content.strip()
        return text[:BLUESKY_MAX_CHARS]
    except Exception as exc:
        logger.warning("LLM post generation failed, using fallback: %s", exc)
        fallback = f"{issue.get('logos', 'Moirai issue')}: {issue.get('description', '')}".strip()
        return fallback[:BLUESKY_MAX_CHARS]


def post_to_bluesky(handle: str, app_password: str, text: str) -> str:
    """Post text to Bluesky and return the URI of the created post.

    Raises on authentication or API failure.
    """
    from atproto import Client

    client = Client()
    client.login(handle, app_password)
    response = client.send_post(text)
    return response.uri


def bluesky_uri_to_url(uri: str, handle: str) -> Optional[str]:
    """Convert an atproto URI (at://did:.../rkey) to a Bluesky web URL."""
    try:
        # at://did:plc:xxx/app.bsky.feed.post/rkey
        parts = uri.split("/")
        rkey = parts[-1]
        return f"https://bsky.app/profile/{handle}/post/{rkey}"
    except Exception:
        return None
