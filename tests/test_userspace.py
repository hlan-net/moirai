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
