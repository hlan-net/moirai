"""AISA provider — in-cluster OpenAI-compatible inference proxy.

AISA (see the AISA client integration guide) reconciles a Kubernetes Secret
into the application namespace with the standard OpenAI-compatible contract:

    OPENAI_BASE_URL   mandatory   proxy endpoint, e.g. http://aisa-apisix.aisa.svc/v1
    OPENAI_API_KEY    mandatory   consumer key issued and rotated by AISA
    OPENAI_MODEL /    optional    default model for this consumer
    LLM_MODEL

Moirai consumes that contract through the ``aisa`` provider. The provider is
purely additive: direct OpenAI / Gemini keys and explicit Ollama endpoints keep
working exactly as before and are never routed through AISA.

Resolution order for the AISA settings (first non-empty wins):

    base URL : AISA_BASE_URL  -> OPENAI_BASE_URL
    API key  : AISA_API_KEY_FILE (file contents) -> AISA_API_KEY
               -> OPENAI_API_KEY (only when OPENAI_BASE_URL is set, i.e. the
                  Secret was bound with ``envFrom``)
    model    : AISA_MODEL -> OPENAI_MODEL -> LLM_MODEL

The ``AISA_*`` names exist so the Helm chart can map the Secret keys without
clobbering the direct ``OPENAI_API_KEY`` used by the ``openai`` provider.
``AISA_API_KEY_FILE`` supports the volume-mount pattern where kubelet refreshes
the mounted key on rotation without a pod restart; the file is re-read on every
provider construction.

Unknown keys in the Secret are ignored by construction (we only read the names
above), which keeps forward compatibility with future AISA additions.
"""

import logging
import os
from typing import Optional

from openai import OpenAI

from .base import LLMProvider

logger = logging.getLogger(__name__)

AISA_TIMEOUT_SECONDS = 600.0
AISA_PROVIDER_NAME = "aisa"


def _read_secret_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError as exc:
        logger.warning("AISA: could not read API key file %s: %s", path, exc)
        return ""


def resolve_aisa_config() -> Optional[dict]:
    """Return ``{"base_url", "api_key", "default_model"}`` or ``None``.

    ``None`` means AISA is not configured for this process (no base URL). A
    configured base URL with a missing key is still returned so callers can
    surface a precise error instead of a generic connection failure.
    """
    base_url = (
        os.environ.get("AISA_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or ""
    ).strip()
    if not base_url:
        return None

    api_key = ""
    key_file = (os.environ.get("AISA_API_KEY_FILE") or "").strip()
    if key_file:
        api_key = _read_secret_file(key_file)
    if not api_key:
        api_key = (os.environ.get("AISA_API_KEY") or "").strip()
    if not api_key and os.environ.get("OPENAI_BASE_URL"):
        # Secret bound via envFrom: the contract's own key name applies.
        api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()

    default_model = (
        os.environ.get("AISA_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or os.environ.get("LLM_MODEL")
        or ""
    ).strip()

    return {"base_url": base_url, "api_key": api_key, "default_model": default_model}


def is_aisa_configured() -> bool:
    """True when a base URL and an API key are both available."""
    cfg = resolve_aisa_config()
    return bool(cfg and cfg["api_key"])


def aisa_default_model() -> str:
    cfg = resolve_aisa_config()
    return cfg["default_model"] if cfg else ""


def aisa_status() -> dict:
    """Secret-free status summary for /api/config and startup logs."""
    cfg = resolve_aisa_config()
    if not cfg:
        return {"configured": False, "base_url": "", "default_model": ""}
    return {
        "configured": bool(cfg["api_key"]),
        "base_url": cfg["base_url"],
        "default_model": cfg["default_model"],
    }


class AisaProvider(LLMProvider):
    """OpenAI-compatible client pointed at the AISA proxy.

    The proxy passes the upstream ``usage`` object through untouched, so token
    accounting on responses works as with any OpenAI-compatible backend. The
    openai SDK's built-in retry honours ``Retry-After`` on HTTP 429
    (``aisa_quota_exceeded``); a 503 means no healthy backend serves the model.
    """

    def __init__(self, api_key: str, base_url: str):
        if not base_url:
            raise ValueError(
                "AISA is not configured: AISA_BASE_URL / OPENAI_BASE_URL is missing"
            )
        if not api_key:
            raise ValueError(
                "AISA is not configured: AISA_API_KEY / OPENAI_API_KEY is missing"
            )
        self.base_url = base_url
        self.client = OpenAI(
            api_key=api_key, base_url=base_url, timeout=AISA_TIMEOUT_SECONDS
        )

    @classmethod
    def from_env(cls) -> "AisaProvider":
        cfg = resolve_aisa_config()
        if not cfg:
            raise ValueError(
                "AISA is not configured: AISA_BASE_URL / OPENAI_BASE_URL is missing"
            )
        return cls(api_key=cfg["api_key"], base_url=cfg["base_url"])

    def list_models(self):
        # GET /v1/models — AISA returns only models with a healthy backend.
        models_response = self.client.models.list()
        return [m.id for m in models_response.data]

    def create_chat_completion(self, messages, model, tools, tool_choice):
        return self.client.chat.completions.create(
            model=model, messages=messages, tools=tools, tool_choice=tool_choice
        )


def log_llm_startup_config(log: logging.Logger) -> None:
    """Log the resolved LLM environment at startup. Never logs secret values."""
    default_provider = os.environ.get("DEFAULT_LLM_PROVIDER", "ollama")
    model_name = os.environ.get("MODEL_NAME", "")
    ollama = os.environ.get("OLLAMA_BASE_URL", "")
    status = aisa_status()
    log.info(
        "LLM config: default_provider=%s model=%s ollama_base_url=%s "
        "openai_key=%s gemini_key=%s",
        default_provider,
        model_name or "(unset)",
        ollama or "(unset)",
        "set" if os.environ.get("OPENAI_API_KEY") else "unset",
        "set" if os.environ.get("GEMINI_API_KEY") else "unset",
    )
    if status["base_url"]:
        log.info(
            "LLM config: aisa base_url=%s default_model=%s key=%s",
            status["base_url"],
            status["default_model"] or "(unset)",
            "set" if status["configured"] else "MISSING",
        )
    else:
        log.info("LLM config: aisa not configured (no AISA_BASE_URL / OPENAI_BASE_URL)")
    if default_provider == AISA_PROVIDER_NAME and not status["configured"]:
        log.warning("DEFAULT_LLM_PROVIDER=aisa but AISA credentials are not available")
