"""Unit tests for annotation backend routing, model verification and 404 backoff."""

import os

os.environ.setdefault("ADMIN_PASSWORD", "test_password")

from unittest.mock import MagicMock, patch

import httpx
import pytest
from openai import NotFoundError

import tasks.annotator as annotator
from tasks.annotation_worker import AnnotationWorker

HAILO = {
    "ANNOTATION_OLLAMA_BASE_URL": "http://hailo:8000/v1",
    "ANNOTATION_MODEL_NAME": "qwen3:1.7b",
    "ANNOTATION_LANGUAGES": "en",
    "OLLAMA_BASE_URL": "http://ergo:11434/v1",
    "MODEL_NAME": "llama3.2:3b",
}

VALID = '{"topics": ["tech"], "priority": "low", "sentiment": "neutral"}'


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    for var in (
        "ANNOTATION_OLLAMA_BASE_URL",
        "ANNOTATION_MODEL_NAME",
        "ANNOTATION_LANGUAGES",
    ):
        monkeypatch.delenv(var, raising=False)
    annotator._paused_until.clear()
    yield
    annotator._paused_until.clear()


def _providers_by_backend(replies: dict):
    """Patch helper: provider whose reply depends on the backend name."""
    calls = []

    def factory(backend=None):
        name = backend.name if backend else "default"
        provider = MagicMock()

        def complete(**kwargs):
            calls.append((name, kwargs["model"]))
            reply = replies[name]
            if isinstance(reply, Exception):
                raise reply
            response = MagicMock()
            response.choices = [MagicMock()]
            response.choices[0].message.content = reply
            return response

        provider.create_chat_completion.side_effect = complete
        return provider

    return factory, calls


def _not_found() -> NotFoundError:
    request = httpx.Request("POST", "http://ollama:11434/v1/chat/completions")
    response = httpx.Response(404, request=request)
    return NotFoundError("model 'llama3.1' not found", response=response, body=None)


class TestModelNamesMatch:
    def test_implicit_latest_tag(self):
        assert annotator._model_names_match("qwen3", "qwen3:latest")
        assert annotator._model_names_match("qwen3:latest", "qwen3")

    def test_different_tags_do_not_match(self):
        assert not annotator._model_names_match("llama3.2:3b", "llama3.2:1b")
        assert not annotator._model_names_match("llama3.1", "llama3.2:latest")


class TestCheckAnnotationModel:
    @patch.dict(os.environ, {"MODEL_NAME": "llama3.2:3b"})
    @patch("tasks.annotator._get_llm_provider")
    def test_model_available(self, mock_get_provider):
        mock_get_provider.return_value.list_models.return_value = [
            "llama3.2:1b",
            "llama3.2:3b",
        ]
        assert annotator.check_annotation_model() is True
        assert annotator.annotation_paused_for() == 0

    @patch.dict(os.environ, {"MODEL_NAME": "llama3.1"})
    @patch("tasks.annotator._get_llm_provider")
    def test_model_missing_pauses_annotation(self, mock_get_provider):
        mock_get_provider.return_value.list_models.return_value = ["llama3.2:3b"]
        assert annotator.check_annotation_model() is False
        assert annotator.annotation_paused_for() > 0

    @patch("tasks.annotator.requests.get", side_effect=Exception("refused"))
    @patch("tasks.annotator._get_llm_provider")
    def test_unreachable_provider_does_not_pause(self, mock_get_provider, _get):
        mock_get_provider.return_value.list_models.side_effect = Exception("refused")
        assert annotator.check_annotation_model() is True
        assert annotator.annotation_paused_for() == 0

    @patch.dict(os.environ, HAILO)
    @patch("tasks.annotator.requests.get")
    @patch("tasks.annotator._get_llm_provider")
    def test_hailo_falls_back_to_native_tags(self, mock_get_provider, mock_get):
        """hailo-ollama has no /v1/models; /api/tags is used instead."""
        provider = MagicMock()
        provider.list_models.side_effect = [Exception("404"), ["llama3.2:3b"]]
        mock_get_provider.return_value = provider
        mock_get.return_value.json.return_value = {"models": [{"name": "qwen3:1.7b"}]}

        assert annotator.check_annotation_model() is True
        mock_get.assert_called_once_with("http://hailo:8000/api/tags", timeout=10)


@patch.dict(os.environ, HAILO)
class TestBackendRouting:
    def test_english_uses_primary(self):
        factory, calls = _providers_by_backend({"primary": VALID})
        with patch("tasks.annotator._get_llm_provider", side_effect=factory):
            assert annotator.annotate_article("T", "S", language="en") is not None
        assert calls == [("primary", "qwen3:1.7b")]

    def test_finnish_skips_primary(self):
        factory, calls = _providers_by_backend({"default": VALID})
        with patch("tasks.annotator._get_llm_provider", side_effect=factory):
            assert annotator.annotate_article("T", "S", language="fi") is not None
        assert calls == [("default", "llama3.2:3b")]

    def test_missing_language_skips_primary(self):
        factory, calls = _providers_by_backend({"default": VALID})
        with patch("tasks.annotator._get_llm_provider", side_effect=factory):
            assert annotator.annotate_article("T", "S") is not None
        assert calls == [("default", "llama3.2:3b")]

    def test_invalid_primary_output_falls_back(self):
        bad = '{"topic": ["business"], "priority": "high", "sentiment": "positive"}'
        factory, calls = _providers_by_backend({"primary": bad, "default": VALID})
        with patch("tasks.annotator._get_llm_provider", side_effect=factory):
            assert annotator.annotate_article("T", "S", language="en") is not None
        assert [c[0] for c in calls] == ["primary", "default"]

    def test_primary_not_found_pauses_only_primary(self):
        factory, calls = _providers_by_backend(
            {"primary": _not_found(), "default": VALID}
        )
        with patch("tasks.annotator._get_llm_provider", side_effect=factory):
            assert annotator.annotate_article("T", "S", language="en") is not None
            assert annotator.annotate_article("T2", "S", language="en") is not None
        assert [c[0] for c in calls] == ["primary", "default", "default"]
        assert annotator._paused_until.get("primary")
        assert "default" not in annotator._paused_until


class TestNotFoundBackoff:
    @patch("tasks.annotator._get_llm_provider")
    def test_not_found_pauses_and_skips_further_calls(self, mock_get_provider):
        provider = MagicMock()
        provider.create_chat_completion.side_effect = _not_found()
        mock_get_provider.return_value = provider

        assert annotator.annotate_article("Title", "Summary") is None
        assert annotator.annotation_paused_for() > 0

        assert annotator.annotate_article("Another", "Summary") is None
        assert provider.create_chat_completion.call_count == 1

    @patch("tasks.annotator._get_llm_provider")
    def test_generic_error_does_not_pause(self, mock_get_provider):
        mock_get_provider.return_value.create_chat_completion.side_effect = Exception(
            "boom"
        )
        assert annotator.annotate_article("Title", "Summary") is None
        assert annotator.annotation_paused_for() == 0


class TestWorkerRespectsPause:
    @patch("tasks.annotation_worker.time.sleep")
    @patch("tasks.annotation_worker.requests.get")
    def test_paused_worker_does_not_consume_changes(self, mock_get, _sleep):
        annotator._paused_until["default"] = annotator.time.monotonic() + 60
        worker = AnnotationWorker()
        worker.last_seq = "5-abc"

        worker._process_changes()

        mock_get.assert_not_called()
        assert worker.last_seq == "5-abc"

    @patch("tasks.annotation_worker.AnnotationWorker._save_last_seq")
    @patch("tasks.annotation_worker.requests.get")
    @patch("tasks.annotator._get_llm_provider")
    def test_pause_mid_batch_keeps_last_seq(
        self, mock_get_provider, mock_get, mock_save
    ):
        mock_get_provider.return_value.create_chat_completion.side_effect = _not_found()
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "results": [
                {"doc": {"_id": "a1", "title": "First"}},
                {"doc": {"_id": "a2", "title": "Second"}},
            ],
            "last_seq": "9-xyz",
        }
        worker = AnnotationWorker()
        worker.last_seq = "5-abc"

        worker._process_changes()

        assert worker.last_seq == "5-abc"
        mock_save.assert_not_called()
        assert mock_get_provider.return_value.create_chat_completion.call_count == 1
