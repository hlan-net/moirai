"""Model catalog — named LLM endpoints and the purposes they serve.

The catalog separates *what models exist* from *which job uses which model*:

    {
      "catalog": {
        "npu-qwen":  {"provider": "ollama", "endpoint": "http://ergo:8000/v1",
                      "model": "qwen3:1.7b", "capabilities": ["chat", "json"],
                      "languages": ["en"]},
        "cpu-llama": {"provider": "ollama", "endpoint": "http://ergo:11434/v1",
                      "model": "llama3.2:3b", "capabilities": ["chat", "json"]},
        "aisa":      {"provider": "aisa", "capabilities": ["chat", "json", "tools"]}
      },
      "purposes": {
        "annotation": ["npu-qwen", "cpu-llama"]
      }
    }

The file is JSON (Helm renders ``llm.catalog`` / ``llm.purposes`` into a
ConfigMap) and is found through ``LLM_CATALOG_FILE``. Each purpose maps to an
ordered fallback list; :func:`resolve_models` returns the entries usable for an
article in a given language.

Without a file, or for a purpose the file does not list, the legacy
environment variables are synthesised into the same shape, so existing
deployments behave exactly as before:

    annotation : ``primary``  (ANNOTATION_OLLAMA_BASE_URL + ANNOTATION_MODEL_NAME,
                               languages from ANNOTATION_LANGUAGES)
                 ``default``  (DEFAULT_LLM_PROVIDER, OLLAMA_BASE_URL, MODEL_NAME)

API keys never live in the catalog: ``openai`` / ``gemini`` entries read
``OPENAI_API_KEY`` / ``GEMINI_API_KEY`` (or the variable named by
``apiKeyEnv``), and ``aisa`` entries use the AISA Secret.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

from .aisa import aisa_default_model

logger = logging.getLogger(__name__)

CATALOG_FILE_ENV = "LLM_CATALOG_FILE"
DEFAULT_MODEL = "llama3.1"
KNOWN_PROVIDERS = frozenset({"ollama", "openai", "gemini", "aisa"})

PURPOSE_ANNOTATION = "annotation"

# Capability each purpose needs from a catalog entry. An entry that does not
# declare ``capabilities`` is assumed to support chat + json.
PURPOSE_CAPABILITIES: dict[str, str] = {
    PURPOSE_ANNOTATION: "json",
}
DEFAULT_CAPABILITIES = frozenset({"chat", "json"})

_DEFAULT_API_KEY_ENV = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}


@dataclass(frozen=True)
class ModelEntry:
    """One catalog entry: an endpoint + model with what it can do.

    ``languages`` is empty when the model handles any language.
    """

    name: str
    provider: str
    base_url: str
    model: str
    capabilities: frozenset = DEFAULT_CAPABILITIES
    languages: frozenset = frozenset()
    api_key_env: str = ""

    def supports_language(self, language: Optional[str]) -> bool:
        if not self.languages:
            return True
        return bool(language) and language.lower() in self.languages

    def api_key(self) -> str:
        env = self.api_key_env or _DEFAULT_API_KEY_ENV.get(self.provider, "")
        return os.environ.get(env, "") if env else ""


@dataclass(frozen=True)
class Catalog:
    entries: dict
    purposes: dict


_cache: dict[str, tuple[float, Catalog]] = {}


def _lower_set(values) -> frozenset:
    return frozenset(str(v).strip().lower() for v in values or [] if str(v).strip())


def _parse_entry(name: str, raw: dict) -> ModelEntry:
    if not isinstance(raw, dict):
        raise ValueError("entry must be a JSON object")
    provider = str(raw.get("provider", "ollama")).lower()
    if provider not in KNOWN_PROVIDERS:
        raise ValueError(f"unknown provider '{provider}'")
    model = raw.get("model") or ""
    if not model and provider == "aisa":
        model = aisa_default_model() or ""
    if not model:
        raise ValueError("model is required")
    capabilities = _lower_set(raw.get("capabilities")) or DEFAULT_CAPABILITIES
    return ModelEntry(
        name=name,
        provider=provider,
        base_url=raw.get("endpoint") or "",
        model=model,
        capabilities=capabilities,
        languages=_lower_set(raw.get("languages")),
        api_key_env=raw.get("apiKeyEnv") or "",
    )


def parse_catalog(data: dict) -> Catalog:
    """Build a :class:`Catalog` from its JSON form, skipping invalid parts.

    A broken entry or a purpose naming an unknown entry is logged and left
    out rather than failing the whole catalog.
    """
    if not isinstance(data, dict):
        raise ValueError("catalog root must be a JSON object")
    raw_catalog = data.get("catalog") or {}
    if not isinstance(raw_catalog, dict):
        raise ValueError("'catalog' must be a JSON object")
    entries: dict[str, ModelEntry] = {}
    for name, raw in raw_catalog.items():
        try:
            entries[name] = _parse_entry(name, raw or {})
        except ValueError as e:
            logger.error(f"LLM catalog: skipping entry '{name}': {e}")

    raw_purposes = data.get("purposes") or {}
    if not isinstance(raw_purposes, dict):
        raise ValueError("'purposes' must be a JSON object")
    purposes: dict[str, list[str]] = {}
    for purpose, names in raw_purposes.items():
        known = []
        for name in names or []:
            if name in entries:
                known.append(name)
            else:
                logger.error(
                    f"LLM catalog: purpose '{purpose}' names unknown entry '{name}'"
                )
        purposes[purpose] = known
    return Catalog(entries=entries, purposes=purposes)


def load_catalog() -> Optional[Catalog]:
    """Return the catalog from ``LLM_CATALOG_FILE``, or ``None`` when unset.

    The file is re-read when its mtime changes, so an updated ConfigMap is
    picked up without a restart.
    """
    path = os.environ.get(CATALOG_FILE_ENV, "")
    if not path:
        return None
    try:
        mtime = os.path.getmtime(path)
    except OSError as e:
        logger.warning(f"LLM catalog: cannot read {path}: {e}")
        return None
    cached = _cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        with open(path, encoding="utf-8") as fh:
            catalog = parse_catalog(json.load(fh))
    except (OSError, ValueError) as e:
        logger.error(f"LLM catalog: invalid file {path}: {e}")
        return None
    _cache[path] = (mtime, catalog)
    return catalog


def default_model_name(provider: str) -> str:
    """MODEL_NAME wins; for the aisa provider fall back to the Secret's default model."""
    model = os.environ.get("MODEL_NAME", "")
    if not model and provider == "aisa":
        model = aisa_default_model()
    return model or DEFAULT_MODEL


def legacy_default_entry(model: Optional[str] = None) -> ModelEntry:
    """The process-wide default LLM from DEFAULT_LLM_PROVIDER / MODEL_NAME."""
    # OLLAMA_BASE_URL is set via docker-compose.yml; no hardcoded default
    # to avoid SonarCloud S5332 (http:// in source).
    provider = os.environ.get("DEFAULT_LLM_PROVIDER", "ollama")
    return ModelEntry(
        name="default",
        provider=provider,
        base_url=os.environ.get("OLLAMA_BASE_URL", ""),
        model=model or default_model_name(provider),
    )


def legacy_annotation_primary() -> Optional[ModelEntry]:
    """The dedicated annotation backend from the ANNOTATION_* variables."""
    base_url = os.environ.get("ANNOTATION_OLLAMA_BASE_URL", "")
    model = os.environ.get("ANNOTATION_MODEL_NAME", "")
    if not (base_url and model):
        return None
    return ModelEntry(
        name="primary",
        provider="ollama",
        base_url=base_url,
        model=model,
        languages=_lower_set(os.environ.get("ANNOTATION_LANGUAGES", "en").split(",")),
    )


def _legacy_entries(purpose: str) -> list[ModelEntry]:
    if purpose == PURPOSE_ANNOTATION:
        primary = legacy_annotation_primary()
        return ([primary] if primary else []) + [legacy_default_entry()]
    return [legacy_default_entry()]


def configured_models(purpose: str) -> list[ModelEntry]:
    """Every entry usable for *purpose*, in fallback order, unfiltered by language."""
    catalog = load_catalog()
    if catalog and catalog.purposes.get(purpose):
        entries = [catalog.entries[n] for n in catalog.purposes[purpose]]
    else:
        entries = _legacy_entries(purpose)
    needed = PURPOSE_CAPABILITIES.get(purpose)
    return [entry for entry in entries if not needed or needed in entry.capabilities]


def resolve_models(purpose: str, language: Optional[str] = None) -> list[ModelEntry]:
    """Entries to try, in order, for *purpose* on an article in *language*.

    Entries lacking the capability the purpose needs, or restricted to other
    languages, are skipped. Small NPU models only understand a few languages,
    so an entry with ``languages`` is used only for those.
    """
    return [
        entry
        for entry in configured_models(purpose)
        if entry.supports_language(language)
    ]


def describe_catalog() -> str:
    """One-line summary of the active catalog for startup logs (no keys)."""
    catalog = load_catalog()
    if not catalog:
        return "LLM catalog: none (legacy environment configuration)"
    purposes = ", ".join(
        f"{p}=[{', '.join(names)}]" for p, names in sorted(catalog.purposes.items())
    )
    return (
        f"LLM catalog: {len(catalog.entries)} entries; purposes: {purposes or 'none'}"
    )
