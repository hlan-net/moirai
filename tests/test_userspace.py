"""
Unit tests for userspace document management and LLM config resolution.
"""

from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# userspace_ops tests
# ---------------------------------------------------------------------------

class TestResolveUserspaceLlmConfig:
    def test_returns_llm_config_when_userspace_exists(self):
        llm_cfg = {"provider": "openai", "model": "gpt-4o", "openai_api_key": "sk-test"}
        doc = {"_id": "uid", "llm_config": llm_cfg}
        with patch("api.userspace_ops.fetch_from_couchdb", return_value=doc):
            from api.userspace_ops import resolve_llm_config
            result = resolve_llm_config("uid")
        assert result == llm_cfg

    def test_returns_empty_dict_when_userspace_missing(self):
        with patch("api.userspace_ops.fetch_from_couchdb", return_value=None):
            from api.userspace_ops import resolve_llm_config
            result = resolve_llm_config("missing-id")
        assert result == {}

    def test_returns_empty_dict_when_llm_config_absent(self):
        doc = {"_id": "uid", "owner_user_id": "uid"}
        with patch("api.userspace_ops.fetch_from_couchdb", return_value=doc):
            from api.userspace_ops import resolve_llm_config
            result = resolve_llm_config("uid")
        assert result == {}


class TestMigrateUserLlmSettingsToUserspace:
    def test_creates_userspace_for_new_user(self):
        user_doc = {
            "_id": "user-uuid",
            "settings": {
                "moirai_llm_provider": "openai",
                "moirai_model": "gpt-4o",
                "moirai_openai_api_key": "sk-test",
                "moirai_ollama_endpoint_url": None,
            },
        }
        with patch("api.userspace_ops.fetch_from_couchdb", return_value=None), \
             patch("api.userspace_ops.store_to_couchdb", return_value={"ok": True}) as mock_store:
            from api.userspace_ops import migrate_user_llm_settings_to_userspace
            result = migrate_user_llm_settings_to_userspace(user_doc)

        assert result is True
        stored_doc = mock_store.call_args[0][1]
        assert stored_doc["_id"] == "user-uuid"
        assert stored_doc["owner_user_id"] == "user-uuid"
        assert stored_doc["llm_config"]["provider"] == "openai"
        assert stored_doc["llm_config"]["openai_api_key"] == "sk-test"

    def test_skips_existing_userspace(self):
        user_doc = {"_id": "user-uuid", "settings": {}}
        existing = {"_id": "user-uuid", "type": "userspace"}
        with patch("api.userspace_ops.fetch_from_couchdb", return_value=existing), \
             patch("api.userspace_ops.store_to_couchdb") as mock_store:
            from api.userspace_ops import migrate_user_llm_settings_to_userspace
            result = migrate_user_llm_settings_to_userspace(user_doc)

        assert result is False
        mock_store.assert_not_called()

    def test_returns_false_without_user_id(self):
        with patch("api.userspace_ops.store_to_couchdb") as mock_store:
            from api.userspace_ops import migrate_user_llm_settings_to_userspace
            result = migrate_user_llm_settings_to_userspace({})

        assert result is False
        mock_store.assert_not_called()

    def test_creates_userspace_with_defaults_when_no_settings(self):
        user_doc = {"_id": "user-uuid", "settings": {}}
        with patch("api.userspace_ops.fetch_from_couchdb", return_value=None), \
             patch("api.userspace_ops.store_to_couchdb", return_value={"ok": True}) as mock_store:
            from api.userspace_ops import migrate_user_llm_settings_to_userspace
            migrate_user_llm_settings_to_userspace(user_doc)

        stored_doc = mock_store.call_args[0][1]
        assert stored_doc["llm_config"]["provider"] == "ollama"
        assert stored_doc["llm_config"]["model"] == "llama3.1"


# ---------------------------------------------------------------------------
# validation tests
# ---------------------------------------------------------------------------

class TestLLMConfigRequest:
    def test_valid_ollama_config(self):
        from api.validation import LLMConfigRequest
        cfg = LLMConfigRequest(provider="ollama", model="llama3.1", ollama_endpoint="http://localhost:11434/v1")
        assert cfg.provider == "ollama"

    def test_valid_openai_config(self):
        from api.validation import LLMConfigRequest
        cfg = LLMConfigRequest(provider="openai", model="gpt-4o", openai_api_key="sk-test")
        assert cfg.openai_api_key == "sk-test"

    def test_invalid_provider_rejected(self):
        from api.validation import LLMConfigRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            LLMConfigRequest(provider="unknown-llm", model="x")

    def test_invalid_ollama_endpoint_rejected(self):
        from api.validation import LLMConfigRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            LLMConfigRequest(provider="ollama", model="llama3.1", ollama_endpoint="not-a-url")


class TestUserspaceCreateRequest:
    def test_valid_request(self):
        from api.validation import UserspaceCreateRequest, LLMConfigRequest
        req = UserspaceCreateRequest(
            name="My Userspace",
            llm_config=LLMConfigRequest(provider="ollama", model="llama3.1"),
        )
        assert req.name == "My Userspace"

    def test_name_required(self):
        from api.validation import UserspaceCreateRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            UserspaceCreateRequest()

    def test_name_sanitized(self):
        from api.validation import UserspaceCreateRequest
        req = UserspaceCreateRequest(name="<script>alert(1)</script>My Space")
        assert "<script>" not in req.name


# ---------------------------------------------------------------------------
# Default userspace resolution
# ---------------------------------------------------------------------------

DEFAULT_UUID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def clear_default_cache(monkeypatch):
    from api.userspace_ops import get_default_userspace

    monkeypatch.setattr("api.userspace_ops._default_userspace_cache", None)
    monkeypatch.delenv("DEFAULT_USERSPACE", raising=False)
    return get_default_userspace


class TestGetDefaultUserspace:
    def test_env_var_wins(self, clear_default_cache, monkeypatch):
        monkeypatch.setenv("DEFAULT_USERSPACE", DEFAULT_UUID)
        with patch("api.userspace_ops.fetch_from_couchdb") as mock_fetch:
            assert clear_default_cache() == DEFAULT_UUID
        mock_fetch.assert_not_called()

    def test_invalid_env_var_returns_none(self, clear_default_cache, monkeypatch):
        monkeypatch.setenv("DEFAULT_USERSPACE", "not-a-uuid")
        assert clear_default_cache() is None

    def test_single_userspace_doc_is_used_and_cached(self, clear_default_cache):
        docs = [{"_id": "_design/x"}, {"_id": DEFAULT_UUID, "type": "userspace"}]
        with patch("api.userspace_ops.fetch_from_couchdb", return_value=docs) as mock_fetch:
            assert clear_default_cache() == DEFAULT_UUID
            assert clear_default_cache() == DEFAULT_UUID
        mock_fetch.assert_called_once()

    def test_ambiguous_returns_none(self, clear_default_cache):
        docs = [{"_id": DEFAULT_UUID}, {"_id": "22222222-2222-4222-8222-222222222222"}]
        with patch("api.userspace_ops.fetch_from_couchdb", return_value=docs):
            assert clear_default_cache() is None


class TestStoreArticleStampsUserspace:
    def _store(self, article):
        from tasks.article_processor import ArticleProcessor

        with patch("tasks.article_processor.requests") as mock_requests:
            mock_requests.head.return_value.status_code = 404
            mock_requests.post.return_value.status_code = 201
            ArticleProcessor().store_article(article)
        return mock_requests.post.call_args.kwargs["json"]

    def test_missing_userspace_gets_default(self):
        article = {"title": "t", "link": "l", "feed_url": "f"}
        with patch(
            "tasks.article_processor.get_default_userspace", return_value=DEFAULT_UUID
        ), patch("tasks.article_processor.get_redis_client", return_value=None):
            stored = self._store(article)
        assert stored["userspace"] == DEFAULT_UUID

    def test_existing_userspace_is_kept(self):
        other = "33333333-3333-4333-8333-333333333333"
        article = {"title": "t", "link": "l", "feed_url": "f", "userspace": other}
        with patch(
            "tasks.article_processor.get_default_userspace", return_value=DEFAULT_UUID
        ) as mock_default, patch("tasks.article_processor.get_redis_client", return_value=None):
            stored = self._store(article)
        assert stored["userspace"] == other
        mock_default.assert_not_called()


class TestCanAccessUserspace:
    def test_default_userspace_open_to_any_user(self):
        from api.userspace_ops import can_access_userspace

        with patch("api.userspace_ops.get_default_userspace", return_value=DEFAULT_UUID), \
             patch("api.userspace_ops.fetch_from_couchdb") as mock_fetch:
            assert can_access_userspace(DEFAULT_UUID, "someone", "user")
        mock_fetch.assert_not_called()

    def test_other_userspace_limited_to_owner_and_admin(self):
        from api.userspace_ops import can_access_userspace

        other = "44444444-4444-4444-8444-444444444444"
        doc = {"_id": other, "owner_user_id": "owner"}
        with patch("api.userspace_ops.get_default_userspace", return_value=DEFAULT_UUID), \
             patch("api.userspace_ops.fetch_from_couchdb", return_value=doc):
            assert can_access_userspace(other, "owner", "user")
            assert not can_access_userspace(other, "intruder", "user")
            assert can_access_userspace(other, "intruder", "admin")

    def test_missing_userspace_doc_denied(self):
        from api.userspace_ops import can_access_userspace

        with patch("api.userspace_ops.get_default_userspace", return_value=None), \
             patch("api.userspace_ops.fetch_from_couchdb", return_value=None):
            assert not can_access_userspace(DEFAULT_UUID, "someone", "user")
