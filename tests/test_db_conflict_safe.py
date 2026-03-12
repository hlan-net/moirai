"""Tests for update_couchdb_doc_safe conflict-handling behaviour."""

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault(
    "JWT_SECRET_KEY", "super_secret_test_key_that_is_at_least_32_chars_long"
)

from api.db import update_couchdb_doc_safe


def _make_response(status_code: int, text: str = "") -> MagicMock:
    """Build a minimal requests.Response mock."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


@pytest.fixture(autouse=True)
def _patch_couchdb_uri():
    """Prevent real network calls by patching the CouchDB URI helper."""
    with patch("api.db.get_couchdb_uri", return_value="http://localhost:5984/"):
        yield


class TestUpdateCouchdbDocSafe:
    """Unit tests for the conflict-safe update helper."""

    def test_success_on_first_attempt(self):
        """Happy path: first attempt succeeds with HTTP 200."""
        existing_doc = {"_id": "agent1", "_rev": "1-abc", "status": "active"}
        with patch("api.db.fetch_from_couchdb", return_value=existing_doc), patch(
            "api.db._request", return_value=_make_response(200)
        ) as mock_req:
            result = update_couchdb_doc_safe(
                "agent_configs", "agent1", {"status": "error"}
            )

        assert result is True
        # Only one PUT attempt
        assert mock_req.call_count == 1
        # The PUT body must include the fetched _rev
        put_kwargs = mock_req.call_args.kwargs
        assert put_kwargs["json"]["_rev"] == "1-abc"
        assert put_kwargs["json"]["status"] == "error"

    def test_retries_on_409_then_succeeds(self):
        """Should retry once on 409, then succeed on the second attempt."""
        doc_v1 = {"_id": "agent1", "_rev": "1-abc", "status": "active"}
        doc_v2 = {"_id": "agent1", "_rev": "2-def", "status": "active"}

        fetch_side_effects = [doc_v1, doc_v2]
        request_side_effects = [_make_response(409), _make_response(200)]

        with patch(
            "api.db.fetch_from_couchdb", side_effect=fetch_side_effects
        ), patch("api.db._request", side_effect=request_side_effects) as mock_req, patch(
            "api.db.time"
        ):
            result = update_couchdb_doc_safe(
                "agent_configs", "agent1", {"status": "error"}, max_retries=3
            )

        assert result is True
        assert mock_req.call_count == 2
        # Second call must use the refreshed _rev
        second_body = mock_req.call_args_list[1].kwargs["json"]
        assert second_body["_rev"] == "2-def"

    def test_exhausts_retries_and_returns_false(self):
        """Should return False after max_retries all result in 409."""
        existing_doc = {"_id": "agent1", "_rev": "1-abc", "status": "active"}

        with patch(
            "api.db.fetch_from_couchdb", return_value=existing_doc
        ), patch("api.db._request", return_value=_make_response(409)) as mock_req, patch(
            "api.db.time"
        ):
            result = update_couchdb_doc_safe(
                "agent_configs", "agent1", {"status": "error"}, max_retries=2
            )

        assert result is False
        # Confirms all retry attempts were actually made (2 retries = 2 PUT calls)
        assert mock_req.call_count == 2

    def test_returns_false_when_doc_not_found(self):
        """Should return False immediately if the document does not exist."""
        with patch("api.db.fetch_from_couchdb", return_value=None), patch(
            "api.db._request"
        ) as mock_req:
            result = update_couchdb_doc_safe(
                "agent_configs", "agent1", {"status": "error"}
            )

        assert result is False
        mock_req.assert_not_called()

    def test_returns_false_on_non_409_error(self):
        """Non-409 HTTP errors should not be retried; return False immediately."""
        existing_doc = {"_id": "agent1", "_rev": "1-abc", "status": "active"}

        with patch(
            "api.db.fetch_from_couchdb", return_value=existing_doc
        ), patch("api.db._request", return_value=_make_response(500, "Server error")) as mock_req:
            result = update_couchdb_doc_safe(
                "agent_configs", "agent1", {"status": "error"}
            )

        assert result is False
        # Non-409 errors must not trigger retries — only one PUT attempt
        assert mock_req.call_count == 1

    def test_merged_doc_preserves_existing_fields(self):
        """update_couchdb_doc_safe merges updates into existing doc without losing fields."""
        existing_doc = {
            "_id": "agent1",
            "_rev": "1-abc",
            "status": "active",
            "name": "My Agent",
            "last_run_at": "2026-01-01T00:00:00+00:00",
        }

        captured_bodies = []

        def capture_request(method, url, **kwargs):
            captured_bodies.append(kwargs.get("json", {}))
            return _make_response(200)

        with patch(
            "api.db.fetch_from_couchdb", return_value=existing_doc
        ), patch("api.db._request", side_effect=capture_request):
            result = update_couchdb_doc_safe(
                "agent_configs", "agent1", {"status": "error"}
            )

        assert result is True
        body = captured_bodies[0]
        # Updates applied
        assert body["status"] == "error"
        # Existing fields preserved
        assert body["name"] == "My Agent"
        assert body["last_run_at"] == "2026-01-01T00:00:00+00:00"
        assert body["_rev"] == "1-abc"
