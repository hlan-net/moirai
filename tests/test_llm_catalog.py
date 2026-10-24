"""Unit tests for the model catalog and its use by the annotator."""

import json
import os

os.environ.setdefault("ADMIN_PASSWORD", "test_password")

from unittest.mock import MagicMock, patch

import pytest

import tasks.annotator as annotator
from api.llm import catalog as cat

LEGACY_ENV = (
    "ANNOTATION_OLLAMA_BASE_URL",
    "ANNOTATION_MODEL_NAME",
    "ANNOTATION_LANGUAGES",
    "DEFAULT_LLM_PROVIDER",
    "OLLAMA_BASE_URL",
    "MODEL_NAME",
    cat.CATALOG_FILE_ENV,
)

CATALOG = {
    "catalog": {
        "npu-qwen": {
            "provider": "ollama",
            "endpoint": "http://ergo:8000/v1",
            "model": "qwen3:1.7b",
            "languages": ["EN"],
        },
        "cpu-llama": {
            "provider": "ollama",
            "endpoint": "http://ergo:11434/v1",
            "model": "llama3.2:3b",
        },
        "chat-only": {"provider": "openai", "model": "x", "capabilities": ["chat"]},
    },
    "purposes": {"annotation": ["npu-qwen", "chat-only", "cpu-llama"]},
}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in LEGACY_ENV:
        monkeypatch.delenv(var, raising=False)
    cat._cache.clear()
    annotator._paused_until.clear()
    yield
    cat._cache.clear()
    annotator._paused_until.clear()


@pytest.fixture
def catalog_file(tmp_path, monkeypatch):
    def write(data: dict) -> str:
        path = tmp_path / "catalog.json"
        path.write_text(json.dumps(data))
        monkeypatch.setenv(cat.CATALOG_FILE_ENV, str(path))
        return str(path)

    return write


def _names(entries) -> list[str]:
    return [e.name for e in entries]


class TestLegacyEnv:
    def test_no_catalog_uses_default_only(self):
        assert _names(cat.resolve_models("annotation", "en")) == ["default"]
        assert cat.load_catalog() is None

    def test_annotation_primary_only_for_its_languages(self, monkeypatch):
        monkeypatch.setenv("ANNOTATION_OLLAMA_BASE_URL", "http://hailo:8000/v1")
        monkeypatch.setenv("ANNOTATION_MODEL_NAME", "qwen3:1.7b")
        monkeypatch.setenv("ANNOTATION_LANGUAGES", "en, sv")
        assert _names(cat.resolve_models("annotation", "en")) == ["primary", "default"]
        assert _names(cat.resolve_models("annotation", "SV")) == ["primary", "default"]
        assert _names(cat.resolve_models("annotation", "fi")) == ["default"]
        assert _names(cat.resolve_models("annotation", None)) == ["default"]
        assert _names(cat.configured_models("annotation")) == ["primary", "default"]

    def test_unknown_purpose_falls_back_to_default(self):
        assert _names(cat.resolve_models("event_synthesis")) == ["default"]


class TestParseCatalog:
    def test_invalid_entries_and_unknown_names_are_skipped(self):
        parsed = cat.parse_catalog(
            {
                "catalog": {
                    "ok": {"provider": "ollama", "model": "m"},
                    "bad-provider": {"provider": "nope", "model": "m"},
                    "no-model": {"provider": "ollama"},
                },
                "purposes": {"annotation": ["missing", "ok", "bad-provider"]},
            }
        )
        assert set(parsed.entries) == {"ok"}
        assert parsed.purposes == {"annotation": ["ok"]}
        assert parsed.entries["ok"].capabilities == cat.DEFAULT_CAPABILITIES

    def test_aisa_entry_takes_secret_default_model(self, monkeypatch):
        monkeypatch.setenv("AISA_BASE_URL", "http://aisa/v1")
        monkeypatch.setenv("AISA_MODEL", "qwen3:8b")
        parsed = cat.parse_catalog({"catalog": {"a": {"provider": "aisa"}}})
        assert parsed.entries["a"].model == "qwen3:8b"

    def test_api_key_comes_from_env_never_catalog(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "k1")
        monkeypatch.setenv("OTHER_KEY", "k2")
        parsed = cat.parse_catalog(
            {
                "catalog": {
                    "o": {"provider": "openai", "model": "m"},
                    "p": {"provider": "openai", "model": "m", "apiKeyEnv": "OTHER_KEY"},
                    "l": {"provider": "ollama", "model": "m"},
                }
            }
        )
        assert parsed.entries["o"].api_key() == "k1"
        assert parsed.entries["p"].api_key() == "k2"
        assert parsed.entries["l"].api_key() == ""


class TestCatalogFile:
    def test_purpose_order_language_and_capability(self, catalog_file):
        catalog_file(CATALOG)
        # chat-only lacks "json", npu-qwen is English only.
        assert _names(cat.resolve_models("annotation", "en")) == [
            "npu-qwen",
            "cpu-llama",
        ]
        assert _names(cat.resolve_models("annotation", "fi")) == ["cpu-llama"]

    def test_purpose_missing_from_file_uses_legacy(self, catalog_file, monkeypatch):
        catalog_file({"catalog": CATALOG["catalog"], "purposes": {}})
        monkeypatch.setenv("MODEL_NAME", "gemma3")
        entries = cat.resolve_models("annotation", "en")
        assert _names(entries) == ["default"]
        assert entries[0].model == "gemma3"

    def test_file_is_reloaded_when_changed(self, catalog_file):
        path = catalog_file(CATALOG)
        assert _names(cat.resolve_models("annotation", "fi")) == ["cpu-llama"]
        data = {**CATALOG, "purposes": {"annotation": ["npu-qwen"]}}
        with open(path, "w") as fh:
            json.dump(data, fh)
        os.utime(path, (1, 1))
        assert _names(cat.resolve_models("annotation", "en")) == ["npu-qwen"]

    def test_unreadable_or_invalid_file_falls_back(self, tmp_path, monkeypatch):
        monkeypatch.setenv(cat.CATALOG_FILE_ENV, str(tmp_path / "missing.json"))
        assert _names(cat.resolve_models("annotation")) == ["default"]
        bad = tmp_path / "bad.json"
        bad.write_text("{not json")
        monkeypatch.setenv(cat.CATALOG_FILE_ENV, str(bad))
        assert _names(cat.resolve_models("annotation")) == ["default"]

    def test_describe_catalog(self, catalog_file):
        assert "legacy" in cat.describe_catalog()
        catalog_file(CATALOG)
        text = cat.describe_catalog()
        assert "3 entries" in text
        assert "annotation=[npu-qwen, chat-only, cpu-llama]" in text


class TestAnnotatorUsesCatalog:
    VALID = '{"topics": ["tech"], "priority": "low", "sentiment": "neutral"}'

    def test_falls_back_through_catalog_entries(self, catalog_file):
        catalog_file(CATALOG)
        calls = []

        def provider_for(backend=None):
            provider = MagicMock()

            def complete(**kwargs):
                calls.append((backend.name, kwargs["model"]))
                response = MagicMock()
                response.choices = [MagicMock()]
                response.choices[0].message.content = (
                    "not json" if backend.name == "npu-qwen" else self.VALID
                )
                return response

            provider.create_chat_completion.side_effect = complete
            return provider

        with patch.object(annotator, "_get_llm_provider", side_effect=provider_for):
            assert annotator.annotate_article("T", "S", language="en") is not None
        assert calls == [("npu-qwen", "qwen3:1.7b"), ("cpu-llama", "llama3.2:3b")]

    def test_aisa_entry_gets_aisa_provider(self, catalog_file):
        catalog_file(
            {
                "catalog": {"aisa": {"provider": "aisa", "model": "m"}},
                "purposes": {"annotation": ["aisa"]},
            }
        )
        with patch.object(annotator.LLMProviderFactory, "get_provider") as get:
            (backend,) = annotator._backends_for("fi")
            annotator._get_llm_provider(backend)
        get.assert_called_once_with("aisa", "", "")

    def test_model_override_applies_to_fallback(self, catalog_file):
        catalog_file(CATALOG)
        backends = annotator._backends_for("en", "override")
        assert [b.model for b in backends] == ["qwen3:1.7b", "override"]
