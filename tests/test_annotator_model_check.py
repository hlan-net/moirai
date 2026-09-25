"""Unit tests for annotation model verification and 404 backoff."""

import os

os.environ.setdefault("ADMIN_PASSWORD", "test_password")

from unittest.mock import MagicMock, patch

import httpx
import pytest
from openai import NotFoundError

import tasks.annotator as annotator
from tasks.annotation_worker import AnnotationWorker


@pytest.fixture(autouse=True)
def reset_pause():
    annotator._paused_until = 0.0
    yield
    annotator._paused_until = 0.0


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

    @patch("tasks.annotator._get_llm_provider")
    def test_unreachable_provider_does_not_pause(self, mock_get_provider):
        mock_get_provider.return_value.list_models.side_effect = Exception("refused")
        assert annotator.check_annotation_model() is True
        assert annotator.annotation_paused_for() == 0


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
        annotator._paused_until = annotator.time.monotonic() + 60
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
