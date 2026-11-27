"""The search indexes of ``api/db_indexes.py`` match those of start-up (#387).

Two places create the indexes of the `articles` database: start-up
(``tasks/init.py``) and the stand-alone script. A search index that only one
of them knows leaves the other's database without it.
"""

from unittest.mock import MagicMock, patch

from api.db_constants import (
    ARTICLE_SEARCH_GAPS_INDEX,
    ARTICLE_SEARCH_GAPS_SELECTOR,
    ARTICLE_SEARCH_INDEX,
    ARTICLE_SEARCH_INDEX_FIELDS,
)


def _posted_by_the_script() -> dict:
    """Index name -> definition, as ``create_articles_indexes`` posts them."""
    from api import db_indexes

    response = MagicMock()
    response.json.return_value = {"result": "created"}
    with (
        patch("api.db_indexes.get_couchdb_uri", return_value="http://couch/"),
        patch("api.db_indexes.requests.post", return_value=response) as post,
    ):
        created = db_indexes.create_articles_indexes()

    assert all(
        call.args[0] == "http://couch/articles/_index" for call in post.call_args_list
    )
    assert created == post.call_count
    return {
        call.kwargs["json"]["name"]: call.kwargs["json"] for call in post.call_args_list
    }


def _posted_at_start_up() -> dict:
    """Index name -> definition, as ``init_db`` posts them for `articles`."""
    from tasks import init

    response = MagicMock(status_code=200)
    with (
        patch("tasks.init.get_couchdb_uri", return_value="http://couch/"),
        patch("tasks.init.ensure_db"),
        patch("tasks.init._request", return_value=response) as request,
    ):
        init.create_index(
            "articles",
            ARTICLE_SEARCH_INDEX_FIELDS,
            ARTICLE_SEARCH_INDEX,
            ddoc=ARTICLE_SEARCH_INDEX,
        )
        init.create_index(
            "articles",
            ["published"],
            ARTICLE_SEARCH_GAPS_INDEX,
            ddoc=ARTICLE_SEARCH_GAPS_INDEX,
            partial_filter=ARTICLE_SEARCH_GAPS_SELECTOR,
        )
    return {
        call.kwargs["json"]["name"]: call.kwargs["json"]
        for call in request.call_args_list
    }


def test_the_script_creates_the_gaps_index_with_its_selector():
    gaps = _posted_by_the_script()[ARTICLE_SEARCH_GAPS_INDEX]

    assert gaps["ddoc"] == ARTICLE_SEARCH_GAPS_INDEX
    assert gaps["index"] == {
        "fields": ["published"],
        "partial_filter_selector": ARTICLE_SEARCH_GAPS_SELECTOR,
    }


def test_the_script_and_start_up_define_the_search_indexes_alike():
    script = _posted_by_the_script()
    start_up = _posted_at_start_up()

    for name in (ARTICLE_SEARCH_INDEX, ARTICLE_SEARCH_GAPS_INDEX):
        assert script[name] == start_up[name]
