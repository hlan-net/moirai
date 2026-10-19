"""Unit tests for the AISA (in-cluster OpenAI-compatible proxy) provider.

AISA support is additive: these tests assert both that the ``aisa`` provider
resolves its credentials from the AISA Secret contract and that the direct
providers (ollama/openai/gemini) are untouched by AISA environment variables.
"""

from unittest.mock import MagicMock

import pytest

from api.llm import aisa as aisa_mod
from api.llm.aisa import (
    AisaProvider,
    aisa_default_model,
    aisa_status,
    is_aisa_configured,
    resolve_aisa_config,
)
from api.llm.factory import LLMProviderFactory
from api.llm.ollama import OllamaProvider
from api.llm.openai import OpenAIProvider

AISA_VARS = [
    "AISA_BASE_URL",
    "AISA_API_KEY",
    "AISA_API_KEY_FILE",
    "AISA_MODEL",
    "OPENAI_BASE_URL",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "LLM_MODEL",
    "DEFAULT_LLM_PROVIDER",
    "MODEL_NAME",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in AISA_VARS:
        monkeypatch.delenv(var, raising=False)


class TestResolveAisaConfig:
    def test_unconfigured_without_base_url(self):
        assert resolve_aisa_config() is None
        assert is_aisa_configured() is False
        assert aisa_status() == {
            "configured": False,
            "base_url": "",
            "default_model": "",
        }

    def test_helm_mapped_aisa_vars(self, monkeypatch):
        monkeypatch.setenv(
            "AISA_BASE_URL", "http://aisa-apisix.aisa.svc.cluster.local/v1"
        )
        monkeypatch.setenv("AISA_API_KEY", "aisa-secret")
        monkeypatch.setenv("AISA_MODEL", "qwen3:8b")
        cfg = resolve_aisa_config()
        assert cfg == {
            "base_url": "http://aisa-apisix.aisa.svc.cluster.local/v1",
            "api_key": "aisa-secret",
            "default_model": "qwen3:8b",
        }
        assert is_aisa_configured() is True
        assert aisa_default_model() == "qwen3:8b"

    def test_envfrom_secret_contract(self, monkeypatch):
        """Secret bound via envFrom exposes the OpenAI-compatible names directly."""
        monkeypatch.setenv("OPENAI_BASE_URL", "http://aisa/v1")
        monkeypatch.setenv("OPENAI_API_KEY", "aisa-key")
        monkeypatch.setenv("OPENAI_MODEL", "llama3.1")
        cfg = resolve_aisa_config()
        assert cfg["base_url"] == "http://aisa/v1"
        assert cfg["api_key"] == "aisa-key"
        assert cfg["default_model"] == "llama3.1"

    def test_direct_openai_key_is_not_borrowed_without_openai_base_url(
        self, monkeypatch
    ):
        """A direct OPENAI_API_KEY must never become the AISA consumer key."""
        monkeypatch.setenv("AISA_BASE_URL", "http://aisa/v1")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-direct")
        cfg = resolve_aisa_config()
        assert cfg["api_key"] == ""
        assert is_aisa_configured() is False
        assert aisa_status()["configured"] is False
        assert aisa_status()["base_url"] == "http://aisa/v1"

    def test_aisa_vars_take_precedence_over_contract_names(self, monkeypatch):
        monkeypatch.setenv("AISA_BASE_URL", "http://aisa/v1")
        monkeypatch.setenv("AISA_API_KEY", "aisa-key")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-direct")
        cfg = resolve_aisa_config()
        assert cfg["base_url"] == "http://aisa/v1"
        assert cfg["api_key"] == "aisa-key"

    def test_key_file_is_read_and_preferred(self, tmp_path, monkeypatch):
        key_file = tmp_path / "OPENAI_API_KEY"
        key_file.write_text("rotated-key\n")
        monkeypatch.setenv("AISA_BASE_URL", "http://aisa/v1")
        monkeypatch.setenv("AISA_API_KEY", "stale-env-key")
        monkeypatch.setenv("AISA_API_KEY_FILE", str(key_file))
        assert resolve_aisa_config()["api_key"] == "rotated-key"

    def test_missing_key_file_falls_back_to_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AISA_BASE_URL", "http://aisa/v1")
        monkeypatch.setenv("AISA_API_KEY", "env-key")
        monkeypatch.setenv("AISA_API_KEY_FILE", str(tmp_path / "missing"))
        assert resolve_aisa_config()["api_key"] == "env-key"

    def test_llm_model_is_last_model_fallback(self, monkeypatch):
        monkeypatch.setenv("AISA_BASE_URL", "http://aisa/v1")
        monkeypatch.setenv("AISA_API_KEY", "k")
        monkeypatch.setenv("LLM_MODEL", "mistral")
        assert aisa_default_model() == "mistral"


class TestAisaProvider:
    def test_requires_base_url_and_key(self):
        with pytest.raises(ValueError):
            AisaProvider(api_key="k", base_url="")
        with pytest.raises(ValueError):
            AisaProvider(api_key="", base_url="http://aisa/v1")

    def test_from_env_raises_when_unconfigured(self):
        with pytest.raises(ValueError, match="AISA is not configured"):
            AisaProvider.from_env()

    def test_client_points_at_proxy(self, monkeypatch):
        monkeypatch.setenv("AISA_BASE_URL", "http://aisa/v1")
        monkeypatch.setenv("AISA_API_KEY", "aisa-key")
        provider = AisaProvider.from_env()
        assert provider.base_url == "http://aisa/v1"
        assert str(provider.client.base_url).rstrip("/") == "http://aisa/v1"
        assert provider.client.api_key == "aisa-key"

    def test_list_models_and_completion_delegate_to_client(self, monkeypatch):
        monkeypatch.setenv("AISA_BASE_URL", "http://aisa/v1")
        monkeypatch.setenv("AISA_API_KEY", "aisa-key")
        provider = AisaProvider.from_env()
        provider.client = MagicMock()
        provider.client.models.list.return_value.data = [
            MagicMock(id="qwen3:8b"),
            MagicMock(id="llama3.1"),
        ]
        assert provider.list_models() == ["qwen3:8b", "llama3.1"]

        provider.create_chat_completion(
            [{"role": "user", "content": "hi"}], "qwen3:8b", None, None
        )
        provider.client.chat.completions.create.assert_called_once_with(
            model="qwen3:8b",
            messages=[{"role": "user", "content": "hi"}],
            tools=None,
            tool_choice=None,
        )


class TestFactory:
    def test_factory_returns_aisa_provider(self, monkeypatch):
        monkeypatch.setenv("AISA_BASE_URL", "http://aisa/v1")
        monkeypatch.setenv("AISA_API_KEY", "aisa-key")
        provider = LLMProviderFactory().get_provider(
            "aisa", "", "http://ollama:11434/v1"
        )
        assert isinstance(provider, AisaProvider)

    def test_factory_raises_clear_error_when_aisa_unconfigured(self):
        factory = LLMProviderFactory()
        with pytest.raises(ValueError, match="AISA is not configured"):
            factory.get_provider("aisa", "", "")

    def test_direct_providers_ignore_aisa_env(self, monkeypatch):
        """AISA env must not redirect direct OpenAI or Ollama traffic."""
        monkeypatch.setenv("AISA_BASE_URL", "http://aisa/v1")
        monkeypatch.setenv("AISA_API_KEY", "aisa-key")
        openai_provider = LLMProviderFactory().get_provider("openai", "sk-direct", "")
        assert isinstance(openai_provider, OpenAIProvider)
        assert str(openai_provider.client.base_url).startswith("https://api.openai.com")
        assert openai_provider.client.api_key == "sk-direct"

        ollama_provider = LLMProviderFactory().get_provider(
            "ollama", "", "http://ollama:11434/v1"
        )
        assert isinstance(ollama_provider, OllamaProvider)
        assert (
            str(ollama_provider.client.base_url).rstrip("/") == "http://ollama:11434/v1"
        )


class TestValidation:
    def test_llm_config_accepts_aisa(self):
        from api.validation import LLMConfigRequest

        cfg = LLMConfigRequest(provider="aisa", model="qwen3:8b")
        assert cfg.provider == "aisa"

    def test_existing_providers_still_accepted(self):
        from api.validation import LLMConfigRequest

        for provider in ("ollama", "openai", "gemini"):
            assert LLMConfigRequest(provider=provider, model="m").provider == provider


class TestCallSites:
    def test_agent_logic_call_llm_returns_none_when_aisa_unconfigured(self):
        from tasks.agent_logic import _call_llm

        assert _call_llm("prompt", {"provider": "aisa", "model": "x"}) is None

    def test_bluesky_falls_back_when_aisa_unconfigured(self):
        from api.bluesky_ops import generate_bluesky_post_text

        text = generate_bluesky_post_text(
            {"logos": "Headline", "description": "Body"},
            [],
            {"provider": "aisa", "model": "x"},
        )
        assert text.startswith("Headline")

    def test_annotator_default_backend_uses_aisa_model(self, monkeypatch):
        from tasks.annotator import _default_backend

        monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "aisa")
        monkeypatch.setenv("AISA_BASE_URL", "http://aisa/v1")
        monkeypatch.setenv("AISA_MODEL", "qwen3:8b")
        backend = _default_backend()
        assert backend.provider == "aisa"
        assert backend.model == "qwen3:8b"
        monkeypatch.setenv("MODEL_NAME", "gemma3")
        assert _default_backend().model == "gemma3"
        assert _default_backend("override").model == "override"

    def test_annotator_default_backend_without_aisa(self):
        from tasks.annotator import DEFAULT_ANNOTATION_MODEL, _default_backend

        backend = _default_backend()
        assert backend.provider == "ollama"
        assert backend.model == DEFAULT_ANNOTATION_MODEL

    def test_startup_log_never_contains_key(self, monkeypatch):
        monkeypatch.setenv("AISA_BASE_URL", "http://aisa/v1")
        monkeypatch.setenv("AISA_API_KEY", "super-secret-key")
        log = MagicMock()
        aisa_mod.log_llm_startup_config(log)
        rendered = " ".join(
            str(a) for call in log.info.call_args_list for a in call.args
        )
        assert "super-secret-key" not in rendered
        assert "http://aisa/v1" in rendered

    def test_startup_log_warns_when_default_is_aisa_but_unconfigured(self, monkeypatch):
        monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "aisa")
        log = MagicMock()
        aisa_mod.log_llm_startup_config(log)
        log.warning.assert_called_once()


class TestChatRoutes:
    def test_get_api_key_is_empty_for_aisa(self):
        from api.chat_routes import _get_api_key

        assert _get_api_key("aisa", None) == ""

    def test_error_message_for_quota(self, monkeypatch):
        from api.chat_routes import _format_agent_error_message

        monkeypatch.setenv("AISA_BASE_URL", "http://aisa/v1")
        msg = _format_agent_error_message(
            "aisa", None, ["Error code: 429 - aisa_quota_exceeded"]
        )
        assert "quota" in msg.lower()

    def test_error_message_for_connection(self, monkeypatch):
        from api.chat_routes import _format_agent_error_message

        monkeypatch.setenv("AISA_BASE_URL", "http://aisa/v1")
        msg = _format_agent_error_message(
            "aisa", None, ["APIConnectionError: Connection refused"]
        )
        assert "http://aisa/v1" in msg

    def test_ollama_error_message_unchanged(self):
        from api.chat_routes import _format_agent_error_message

        msg = _format_agent_error_message(
            "ollama", "http://ollama:11434/v1", ["Connection refused"]
        )
        assert "Ollama" in msg
        assert "http://ollama:11434/v1" in msg
