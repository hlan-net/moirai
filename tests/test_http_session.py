"""The shared CouchDB session: one per process, used by both request helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests

from api import http_session


def test_session_is_reused_within_a_process():
    first = http_session.couchdb_session()
    assert isinstance(first, requests.Session)
    assert http_session.couchdb_session() is first


def test_session_is_rebuilt_after_a_fork():
    parent = http_session.couchdb_session()
    with patch.object(http_session.os, "getpid", return_value=-1):
        child = http_session.couchdb_session()
    assert child is not parent
    # Back in the "parent" pid a new one is made as well; what matters is that
    # a process never uses a session created under another pid.
    assert http_session.couchdb_session() is not child


def test_session_pools_connections():
    adapter = http_session.couchdb_session().get_adapter("http://couchdb:5984/")
    assert adapter._pool_maxsize == http_session.POOL_SIZE


def test_api_and_mcp_helpers_go_through_the_session():
    from api import db as api_db
    from mcp_service import db as mcp_db

    session = MagicMock()
    session.request.return_value = MagicMock(status_code=200)
    with (
        patch.object(api_db, "couchdb_session", return_value=session),
        patch.object(mcp_db, "couchdb_session", return_value=session),
    ):
        api_db._request("GET", "http://couchdb:5984/articles/a1")
        mcp_db._request("GET", "http://couchdb:5984/feeds/f1")

    assert [c.args for c in session.request.call_args_list] == [
        ("GET", "http://couchdb:5984/articles/a1"),
        ("GET", "http://couchdb:5984/feeds/f1"),
    ]
    # The default timeout is still applied by the helper.
    assert session.request.call_args_list[0].kwargs["timeout"] == 10
