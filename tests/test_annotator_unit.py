"""Unit tests for tasks/annotator.py — validation and LLM annotation logic."""

import os

os.environ.setdefault("ADMIN_PASSWORD", "test_password")

import json
from unittest.mock import patch, MagicMock

import pytest

from tasks.annotator import (
    ANNOTATION_VERSION,
    ANNOTATION_SYSTEM_PROMPT,
    TOPIC_ALIASES,
    TOPIC_VOCABULARY,
    _extract_json,
    _normalise_topics,
    _validate_annotation,
    annotate_article,
    store_annotation,
)


# ===== _validate_annotation =====


class TestValidateAnnotation:
    def test_valid_annotation(self):
        raw = {
            "topics": ["technology", "science"],
            "priority": "high",
            "sentiment": "positive",
        }
        result = _validate_annotation(raw)
        assert result is not None
        assert result["topics"] == ["technology", "science"]
        assert result["priority"] == "high"
        assert result["sentiment"] == "positive"

    def test_topics_normalised_lowercase(self):
        raw = {
            "topics": ["Technology", "SCIENCE"],
            "priority": "low",
            "sentiment": "neutral",
        }
        result = _validate_annotation(raw)
        assert result["topics"] == ["technology", "science"]

    def test_topics_truncated_to_three(self):
        raw = {
            "topics": ["politics", "world", "business", "finance", "health"],
            "priority": "medium",
            "sentiment": "negative",
        }
        result = _validate_annotation(raw)
        assert result["topics"] == ["politics", "world", "business"]

    def test_empty_topics_returns_none(self):
        raw = {"topics": [], "priority": "high", "sentiment": "positive"}
        assert _validate_annotation(raw) is None

    def test_topics_not_list_returns_none(self):
        raw = {"topics": "technology", "priority": "high", "sentiment": "positive"}
        assert _validate_annotation(raw) is None

    def test_invalid_priority_returns_none(self):
        raw = {"topics": ["tech"], "priority": "critical", "sentiment": "positive"}
        assert _validate_annotation(raw) is None

    def test_invalid_sentiment_returns_none(self):
        raw = {"topics": ["tech"], "priority": "high", "sentiment": "angry"}
        assert _validate_annotation(raw) is None

    def test_missing_fields_returns_none(self):
        assert _validate_annotation({}) is None
        assert _validate_annotation({"topics": ["x"]}) is None
        assert _validate_annotation({"topics": ["x"], "priority": "low"}) is None

    def test_topics_with_empty_strings_filtered(self):
        raw = {
            "topics": ["", "tech", ""],
            "priority": "low",
            "sentiment": "neutral",
        }
        result = _validate_annotation(raw)
        assert result["topics"] == ["technology"]

    def test_topics_all_empty_falls_back_to_general(self):
        """No usable label, but priority/sentiment are still worth storing."""
        raw = {"topics": ["", ""], "priority": "low", "sentiment": "neutral"}
        assert _validate_annotation(raw)["topics"] == ["general"]


# ===== _extract_json =====


class TestExtractJson:
    def test_plain_object_unchanged(self):
        assert _extract_json('{"a": 1}') == '{"a": 1}'

    def test_code_fence_stripped(self):
        assert _extract_json('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_trailing_commentary_dropped(self):
        raw = '{"a": 1}\n\nI hope this helps!'
        assert _extract_json(raw) == '{"a": 1}'

    def test_sentencepiece_space_marker_replaced(self):
        raw = '{\n\u2581\u2581"a": 1\n}'
        assert json.loads(_extract_json(raw)) == {"a": 1}

    def test_no_object_returns_stripped_text(self):
        assert _extract_json("  no json here  ") == "no json here"


# ===== closed topic vocabulary =====


class TestTopicVocabulary:
    def test_vocabulary_labels_pass_through(self):
        assert _normalise_topics(["politics", "sports"]) == ["politics", "sports"]

    def test_alias_is_mapped(self):
        assert _normalise_topics(["tech", "economy"]) == ["technology", "business"]

    def test_unknown_label_is_dropped(self):
        assert _normalise_topics(["jews/holocaust", "culture"]) == ["culture"]

    def test_all_unknown_falls_back_to_general(self):
        assert _normalise_topics(["kuolleet", "juutalaisuus"]) == ["general"]

    def test_general_dropped_when_other_topics_present(self):
        assert _normalise_topics(["news", "obituary"]) == ["obituary"]

    def test_duplicates_after_aliasing_are_collapsed(self):
        assert _normalise_topics(["death", "obituary", "deaths"]) == ["obituary"]

    def test_max_three_after_dropping(self):
        raw = ["x", "politics", "y", "world", "business", "finance"]
        assert _normalise_topics(raw) == ["politics", "world", "business"]

    def test_every_alias_targets_the_vocabulary(self):
        assert set(TOPIC_ALIASES.values()) <= set(TOPIC_VOCABULARY)

    def test_prompt_lists_exactly_the_vocabulary(self):
        """The prompt and the validator must not drift apart."""
        for label in TOPIC_VOCABULARY:
            assert f'"{label}"' in ANNOTATION_SYSTEM_PROMPT


# ===== annotate_article =====


class TestAnnotateArticle:
    @patch("tasks.annotator._get_llm_provider")
    def test_successful_annotation(self, mock_get_provider):
        """LLM returns valid JSON — annotation succeeds."""
        mock_provider = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {
                "topics": ["politics", "economy"],
                "priority": "high",
                "sentiment": "negative",
            }
        )
        mock_provider.create_chat_completion.return_value = mock_response
        mock_get_provider.return_value = mock_provider

        result = annotate_article("Election results shock markets", "A long summary...")
        assert result is not None
        assert result["topics"] == ["politics", "business"]  # economy → alias
        assert result["priority"] == "high"
        assert result["sentiment"] == "negative"

    @patch("tasks.annotator._get_llm_provider")
    def test_llm_returns_markdown_fenced_json(self, mock_get_provider):
        """LLM wraps JSON in markdown code fences — should be stripped."""
        mock_provider = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            '```json\n{"topics": ["tech"], "priority": "low", "sentiment": "neutral"}\n```'
        )
        mock_provider.create_chat_completion.return_value = mock_response
        mock_get_provider.return_value = mock_provider

        result = annotate_article("New chip released", "Details here")
        assert result is not None
        assert result["topics"] == ["technology"]

    @patch("tasks.annotator._get_llm_provider")
    def test_empty_title_returns_none(self, mock_get_provider):
        """Empty title should skip LLM call entirely."""
        result = annotate_article("", "Some summary")
        assert result is None
        mock_get_provider.assert_not_called()

    @patch("tasks.annotator._get_llm_provider")
    def test_llm_returns_invalid_json(self, mock_get_provider):
        """LLM returns non-JSON text — should return None."""
        mock_provider = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "I cannot classify this article."
        mock_provider.create_chat_completion.return_value = mock_response
        mock_get_provider.return_value = mock_provider

        result = annotate_article("Some title", "Some summary")
        assert result is None

    @patch("tasks.annotator._get_llm_provider")
    def test_llm_exception_returns_none(self, mock_get_provider):
        """LLM provider raises exception — should return None."""
        mock_provider = MagicMock()
        mock_provider.create_chat_completion.side_effect = Exception("Connection refused")
        mock_get_provider.return_value = mock_provider

        result = annotate_article("Some title", "Some summary")
        assert result is None


# ===== Regression: topics derived from an identity term =====

# Recorded from production on 2026-09-29 (llama3.2:3b, default backend). A
# two-line death notice was tagged politics/security/holocaust on the strength
# of the word "juutalaiselle" alone; nothing in the input supports those topics.
# See issue #249 for the model comparison and the proposed fix.
SELLA_TITLE = "Kuolleet | Näyttelijä Seela Sella haudattiin"
SELLA_SUMMARY = "Sella haudattiin Helsingin juutalaiselle hautausmaalle."
SELLA_LANGUAGE = "fi"
SELLA_RECORDED_OUTPUT = {
    "topics": ["politics", "security", "jews/holocaust"],
    "priority": "medium",
    "sentiment": "negative",
}
UNSUPPORTED_TOPIC_FRAGMENTS = ("politic", "security", "holocaust", "jew")

LIVE_LLM_CONFIGURED = any(
    os.environ.get(k) for k in ("OLLAMA_BASE_URL", "OPENAI_API_KEY", "GEMINI_API_KEY")
)


class TestIdentityTermRegression:
    @patch.dict("tasks.annotator._paused_until", {}, clear=True)
    @patch("tasks.annotator._get_llm_provider")
    def test_model_input_does_not_mention_recorded_topics(self, mock_get_provider):
        """The model saw only title + summary, neither of which names the topics."""
        mock_provider = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(SELLA_RECORDED_OUTPUT)
        mock_provider.create_chat_completion.return_value = mock_response
        mock_get_provider.return_value = mock_provider

        annotate_article(SELLA_TITLE, SELLA_SUMMARY, language=SELLA_LANGUAGE)

        messages = mock_provider.create_chat_completion.call_args.kwargs["messages"]
        user_content = messages[-1]["content"]
        assert user_content == f"Title: {SELLA_TITLE}\nSummary: {SELLA_SUMMARY}"
        assert "holocaust" not in user_content.lower()

    @patch.dict("tasks.annotator._paused_until", {}, clear=True)
    @patch("tasks.annotator._get_llm_provider")
    def test_invented_topic_is_not_stored(self, mock_get_provider):
        """A label the model made up must not survive validation."""
        mock_provider = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(SELLA_RECORDED_OUTPUT)
        mock_provider.create_chat_completion.return_value = mock_response
        mock_get_provider.return_value = mock_provider

        result = annotate_article(SELLA_TITLE, SELLA_SUMMARY, language=SELLA_LANGUAGE)

        topics = result["topics"] if result else []
        assert "jews/holocaust" not in topics

    @pytest.mark.integration
    @pytest.mark.skipif(not LIVE_LLM_CONFIGURED, reason="needs a live annotation LLM")
    def test_live_model_does_not_tag_by_identity_term(self):
        """The configured model must classify the notice by what it is about."""
        result = annotate_article(SELLA_TITLE, SELLA_SUMMARY, language=SELLA_LANGUAGE)

        assert result is not None
        unsupported = [
            topic
            for topic in result["topics"]
            if any(fragment in topic for fragment in UNSUPPORTED_TOPIC_FRAGMENTS)
        ]
        assert unsupported == []


# ===== store_annotation =====


class TestStoreAnnotation:
    @patch("tasks.annotator.requests")
    def test_successful_store(self, mock_requests):
        """Successful GET + PUT flow stores the annotation."""
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {
            "_id": "art123",
            "_rev": "1-abc",
            "title": "Test",
        }

        mock_put_resp = MagicMock()
        mock_put_resp.status_code = 201

        mock_requests.get.return_value = mock_get_resp
        mock_requests.put.return_value = mock_put_resp

        annotation = {"topics": ["tech"], "priority": "low", "sentiment": "neutral"}
        result = store_annotation("art123", annotation)
        assert result is True

        # Verify PUT was called with annotation in the doc
        put_call = mock_requests.put.call_args
        doc = put_call.kwargs.get("json") or put_call[1].get("json")
        assert doc["annotations"] == annotation
        assert "annotated_at" in doc
        assert doc["annotation_version"] == ANNOTATION_VERSION

    @patch("tasks.annotator.requests")
    def test_article_not_found(self, mock_requests):
        """GET returns 404 — store fails gracefully."""
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 404
        mock_requests.get.return_value = mock_get_resp

        annotation = {"topics": ["tech"], "priority": "low", "sentiment": "neutral"}
        result = store_annotation("nonexistent", annotation)
        assert result is False
        mock_requests.put.assert_not_called()

    @patch("tasks.annotator.requests")
    def test_put_conflict(self, mock_requests):
        """PUT returns 409 conflict — store reports failure."""
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {"_id": "art123", "_rev": "1-abc"}

        mock_put_resp = MagicMock()
        mock_put_resp.status_code = 409
        mock_put_resp.text = "Document update conflict"

        mock_requests.get.return_value = mock_get_resp
        mock_requests.put.return_value = mock_put_resp

        annotation = {"topics": ["tech"], "priority": "low", "sentiment": "neutral"}
        result = store_annotation("art123", annotation)
        assert result is False

    @patch("tasks.annotator.requests")
    def test_network_error(self, mock_requests):
        """Network error during GET — store fails gracefully."""
        import requests as real_requests

        mock_requests.get.side_effect = real_requests.exceptions.ConnectionError(
            "Connection refused"
        )
        # Also need to make the exception type accessible
        mock_requests.exceptions = real_requests.exceptions

        annotation = {"topics": ["tech"], "priority": "low", "sentiment": "neutral"}
        result = store_annotation("art123", annotation)
        assert result is False


# ===== RSS annotation category generation =====


class TestRssAnnotationCategories:
    def test_annotations_in_rss_xml(self):
        """Annotations are rendered as <category> tags in RSS XML."""
        from api.rss_ops import generate_rss_item_xml
        from datetime import datetime, timezone

        def mock_parse_dt(s):
            return datetime(2025, 1, 1, tzinfo=timezone.utc)

        article = {
            "title": "Test Article",
            "link": "https://example.com/article",
            "summary": "A test summary.",
            "published": "2025-01-01T00:00:00Z",
            "feed_url": "https://example.com/feed",
            "annotations": {
                "topics": ["technology", "science"],
                "priority": "high",
                "sentiment": "positive",
            },
        }

        xml = generate_rss_item_xml(article, {"https://example.com/feed": "Test Feed"}, mock_parse_dt)

        assert '<category domain="topic">technology</category>' in xml
        assert '<category domain="topic">science</category>' in xml
        assert '<category domain="priority">high</category>' in xml
        assert '<category domain="sentiment">positive</category>' in xml

    def test_no_annotations_no_extra_categories(self):
        """Articles without annotations produce no annotation categories."""
        from api.rss_ops import generate_rss_item_xml
        from datetime import datetime, timezone

        def mock_parse_dt(s):
            return datetime(2025, 1, 1, tzinfo=timezone.utc)

        article = {
            "title": "Plain Article",
            "link": "https://example.com/plain",
            "summary": "No annotations.",
            "published": "2025-01-01T00:00:00Z",
            "feed_url": "https://example.com/feed",
        }

        xml = generate_rss_item_xml(article, {}, mock_parse_dt)

        assert "domain=\"topic\"" not in xml
        assert "domain=\"priority\"" not in xml
        assert "domain=\"sentiment\"" not in xml
