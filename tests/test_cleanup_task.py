"""Unit tests for paginated article cleanup in tasks/cleanup_task.py."""

import json
from unittest.mock import MagicMock, patch

from tasks import cleanup_task


def _page(ids: list[str]) -> MagicMock:
    res = MagicMock(status_code=200)
    res.json.return_value = {
        "rows": [{"id": i, "doc": {"_id": i, "_rev": "1-a"}} for i in ids]
    }
    return res


@patch("tasks.cleanup_task.get_couchdb_uri", return_value="http://db/")
@patch("tasks.cleanup_task.requests.get")
def test_iter_doc_pages_pages_through_all_docs(mock_get, _uri) -> None:
    mock_get.side_effect = [_page(["a", "b"]), _page(["b", "c"]), _page(["c"])]

    pages = list(cleanup_task.iter_doc_pages("articles", page_size=2))

    assert [[d["_id"] for d in p] for p in pages] == [["a", "b"], ["c"]]
    assert "startkey" not in mock_get.call_args_list[0].kwargs["params"]
    assert mock_get.call_args_list[1].kwargs["params"]["startkey"] == json.dumps("b")
    assert mock_get.call_args_list[2].kwargs["params"]["startkey"] == json.dumps("c")


@patch("tasks.cleanup_task.get_couchdb_uri", return_value="http://db/")
@patch("tasks.cleanup_task.requests.get")
def test_iter_doc_pages_keeps_next_doc_when_last_was_deleted(mock_get, _uri) -> None:
    # "b" was deleted after the first page, so the next page starts at "c".
    mock_get.side_effect = [_page(["a", "b"]), _page(["c"])]

    pages = list(cleanup_task.iter_doc_pages("articles", page_size=2))

    assert [[d["_id"] for d in p] for p in pages] == [["a", "b"], ["c"]]


@patch("tasks.cleanup_task.get_couchdb_uri", return_value="http://db/")
@patch("tasks.cleanup_task.requests.get")
def test_iter_doc_pages_skips_design_docs_and_stops_on_error(mock_get, _uri) -> None:
    mock_get.side_effect = [
        _page(["_design/validation", "a"]),
        MagicMock(status_code=500),
    ]

    pages = list(cleanup_task.iter_doc_pages("articles", page_size=2))

    assert [[d["_id"] for d in p] for p in pages] == [["a"]]


@patch("tasks.cleanup_task._process_articles", return_value=1)
@patch("tasks.cleanup_task.iter_doc_pages")
@patch("tasks.cleanup_task.get_all_docs", return_value=[])
def test_run_cleanup_processes_articles_page_by_page(
    _issues, mock_pages, mock_process
) -> None:
    mock_pages.return_value = iter([[{"_id": "a"}], [{"_id": "b"}]])

    cleanup_task.run_cleanup()

    mock_pages.assert_called_once_with("articles")
    assert mock_process.call_count == 2
