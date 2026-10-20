"""Unit tests for scripts/reannotate_outdated.py."""

import os

os.environ.setdefault("ADMIN_PASSWORD", "test_password")

from unittest.mock import patch

from scripts.reannotate_outdated import iter_outdated, outdated_selector, reannotate
from tasks.annotator import ANNOTATION_VERSION


def test_selector_targets_annotated_articles_behind_current_version():
    selector = outdated_selector(None)
    assert selector["annotations"] == {"$exists": True}
    assert {"annotation_version": {"$exists": False}} in selector["$or"]
    assert {"annotation_version": {"$lt": ANNOTATION_VERSION}} in selector["$or"]
    assert "userspace" not in selector


def test_selector_scopes_to_userspace():
    assert outdated_selector("abc")["userspace"] == "abc"


def test_selector_days_adds_published_cutoff():
    selector = outdated_selector(None, days=7)
    cutoff = selector["published"]["$gte"]
    assert len(cutoff) == len("2026-01-01T00:00:00")
    assert cutoff < "9999"
    assert "published" not in outdated_selector(None)


@patch("scripts.reannotate_outdated.requests.post")
def test_iter_outdated_pages_with_bookmark_until_empty(mock_post):
    pages = [
        {"docs": [{"_id": "a"}, {"_id": "b"}], "bookmark": "bm1"},
        {"docs": [{"_id": "c"}], "bookmark": "bm2"},
        {"docs": [], "bookmark": "bm3"},
    ]
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.side_effect = pages

    assert [d["_id"] for d in iter_outdated(None, limit=10)] == ["a", "b", "c"]
    assert mock_post.call_args_list[1].kwargs["json"]["bookmark"] == "bm1"


@patch("scripts.reannotate_outdated.requests.post")
def test_iter_outdated_respects_limit(mock_post):
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.return_value = {
        "docs": [{"_id": "a"}, {"_id": "b"}],
        "bookmark": "bm",
    }
    assert len(list(iter_outdated(None, limit=2))) == 2
    assert mock_post.call_args.kwargs["json"]["limit"] == 2


@patch("scripts.reannotate_outdated.store_annotation")
@patch("scripts.reannotate_outdated.annotate_article")
def test_reannotate_passes_language_and_stores(mock_annotate, mock_store):
    mock_annotate.return_value = {
        "topics": ["culture"],
        "priority": "low",
        "sentiment": "neutral",
    }
    mock_store.return_value = True
    doc = {"_id": "x", "title": "T", "summary": "S", "language": "fi"}

    assert reannotate(doc, dry_run=False) is True
    mock_annotate.assert_called_once_with("T", "S", language="fi")
    mock_store.assert_called_once_with("x", mock_annotate.return_value)


@patch("scripts.reannotate_outdated.annotate_article")
def test_dry_run_does_not_call_model(mock_annotate):
    assert reannotate({"_id": "x", "title": "T"}, dry_run=True) is True
    mock_annotate.assert_not_called()
