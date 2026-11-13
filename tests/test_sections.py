"""Unit tests for stream sectioning (#266): signal order, path map, feed
category normalisation, annotation fallback, RSS output and ingestion."""

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

os.environ.setdefault("ADMIN_PASSWORD", "test_password")

import pytest  # noqa: E402

from api.rss_ops import generate_rss_item_xml  # noqa: E402
from tasks.article_processor import ArticleProcessor  # noqa: E402
from tasks.sections import (  # noqa: E402
    SECTIONS,
    STREAM_CACHE_KEYS,
    apply_topic_section,
    is_valid_section,
    resolve_section,
    section_from_feed_category,
    section_from_link,
    section_from_topics,
)


class TestFeedCategory:
    @pytest.mark.parametrize(
        "category,expected",
        [
            ("sports", "sports"),
            ("Urheilu", "sports"),
            ("culture", "culture"),
            ("kulttuuri", "culture"),
            ("entertainment", "culture"),
            ("business", "business"),
            ("talous", "business"),
            ("finance", "business"),
            ("economy", "business"),
            ("general", "main"),
            ("tech", None),
            ("imported", None),
            ("", None),
            (None, None),
        ],
    )
    def test_normalisation(self, category, expected):
        assert section_from_feed_category(category) == expected


class TestLinkPathMap:
    @pytest.mark.parametrize(
        "link,expected",
        [
            ("https://www.hs.fi/urheilu/art-2000010000000.html", "sports"),
            ("https://www.hs.fi/kulttuuri/art-2000010000001.html", "culture"),
            ("https://www.hs.fi/talous/art-2000010000002.html", "business"),
            ("https://www.hs.fi/politiikka/art-2000010000003.html", None),
            ("https://yle.fi/urheilu/a/74-20000000", "sports"),
            ("https://yle.fi/a/74-20000001", None),
            ("https://www.is.fi/urheilu/jalkapallo/art-1.html", "sports"),
            ("https://www.is.fi/viihde/art-2.html", "culture"),
            ("https://www.is.fi/taloussanomat/art-3.html", "business"),
            ("https://www.kauppalehti.fi/uutiset/abc/123", "business"),
            ("https://www.iltalehti.fi/talous/a/1", "business"),
            ("https://www.bbc.com/sport/football/1", "sports"),
            ("https://www.bbc.com/news/world-1", None),
            ("https://example.com/", None),
            ("", None),
            (None, None),
            ("not a url", None),
        ],
    )
    def test_path_map(self, link, expected):
        assert section_from_link(link) == expected


class TestTopics:
    def test_first_mapped_topic_wins(self):
        assert section_from_topics(["politics", "sports", "culture"]) == "sports"

    def test_finance_and_entertainment_map(self):
        assert section_from_topics(["finance"]) == "business"
        assert section_from_topics(["entertainment"]) == "culture"

    def test_unmapped_topics_give_nothing(self):
        assert section_from_topics(["politics", "world"]) is None
        assert section_from_topics([]) is None
        assert section_from_topics(None) is None
        assert section_from_topics([42, None]) is None


class TestResolveOrder:
    def test_feed_category_beats_path(self):
        assert resolve_section("sports", "https://www.hs.fi/kulttuuri/art-1.html") == (
            "sports",
            "feed",
        )

    def test_general_feed_defers_to_path(self):
        assert resolve_section("general", "https://www.hs.fi/kulttuuri/art-1.html") == (
            "culture",
            "path",
        )

    def test_path_beats_topic(self):
        assert resolve_section(
            None, "https://www.hs.fi/talous/art-1.html", ["sports"]
        ) == ("business", "path")

    def test_topic_fallback(self):
        assert resolve_section(None, "https://yle.fi/a/74-1", ["sports"]) == (
            "sports",
            "topic",
        )

    def test_default_is_main(self):
        assert resolve_section() == ("main", "default")
        assert resolve_section("tech", "https://example.com/x", ["politics"]) == (
            "main",
            "default",
        )

    def test_every_result_is_a_valid_section(self):
        for category in ("sports", "culture", "business", "general", None):
            section, _ = resolve_section(category, "https://example.com/x")
            assert is_valid_section(section)
        assert not is_valid_section("news")
        assert not is_valid_section(None)


class TestApplyTopicSection:
    def test_path_decision_is_not_overridden(self):
        doc = {"section": "culture", "section_source": "path"}
        assert apply_topic_section(doc, ["sports"]) is False
        assert doc["section"] == "culture"

    def test_feed_decision_is_not_overridden(self):
        doc = {"section": "business", "section_source": "feed"}
        assert apply_topic_section(doc, ["sports"]) is False

    def test_default_moves_to_topic_section(self):
        doc = {"section": "main", "section_source": "default"}
        assert apply_topic_section(doc, ["politics", "sports"]) is True
        assert doc == {"section": "sports", "section_source": "topic"}

    def test_unsectioned_legacy_doc_gets_stamped(self):
        doc = {}
        assert apply_topic_section(doc, ["world"]) is True
        assert doc == {"section": "main", "section_source": "default"}

    def test_no_change_when_already_right(self):
        doc = {"section": "sports", "section_source": "topic"}
        assert apply_topic_section(doc, ["sports"]) is False

    def test_reannotation_can_move_back_to_main(self):
        doc = {"section": "sports", "section_source": "topic"}
        assert apply_topic_section(doc, ["politics"]) is True
        assert doc["section"] == "main"


class TestRssOutput:
    def test_section_category_is_emitted(self):
        article = {
            "title": "T",
            "link": "https://example.com/a",
            "summary": "S",
            "published": "2024-01-01T00:00:00+00:00",
            "section": "sports",
        }
        xml = generate_rss_item_xml(article, {}, lambda s: datetime.fromisoformat(s))
        assert '<category domain="section">sports</category>' in xml

    def test_no_section_no_category(self):
        article = {
            "title": "T",
            "link": "https://example.com/a",
            "summary": "S",
            "published": "2024-01-01T00:00:00+00:00",
        }
        xml = generate_rss_item_xml(article, {}, lambda s: datetime.fromisoformat(s))
        assert 'domain="section"' not in xml


def _feed_xml(*links: str) -> str:
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    items = "".join(
        f"<item><title>Article {i}</title><link>{link}</link>"
        f"<description>Summary</description><pubDate>{now}</pubDate></item>"
        for i, link in enumerate(links)
    )
    return f'<rss version="2.0"><channel><title>Mixed</title>{items}</channel></rss>'


class TestIngestion:
    def test_mixed_feed_sections_by_path(self):
        xml = _feed_xml(
            "https://www.hs.fi/urheilu/art-1.html",
            "https://www.hs.fi/politiikka/art-2.html",
        )
        _, articles = ArticleProcessor().process_feed(
            "https://www.hs.fi/rss/tuoreimmat.xml", xml, "general"
        )
        assert [(a["section"], a["section_source"]) for a in articles] == [
            ("sports", "path"),
            ("main", "default"),
        ]

    def test_section_feed_files_everything(self):
        xml = _feed_xml("https://www.hs.fi/art-1.html", "https://www.hs.fi/art-2.html")
        _, articles = ArticleProcessor().process_feed(
            "https://www.hs.fi/rss/urheilu.xml", xml, "sports"
        )
        assert {a["section"] for a in articles} == {"sports"}
        assert {a["section_source"] for a in articles} == {"feed"}

    def test_process_feed_without_category_still_sections(self):
        xml = _feed_xml("https://www.kauppalehti.fi/uutiset/x/1")
        _, articles = ArticleProcessor().process_feed("https://kl.fi/rss", xml)
        assert articles[0]["section"] == "business"

    def test_store_article_stamps_missing_section_and_clears_section_caches(self):
        article = {
            "title": "t",
            "link": "https://www.hs.fi/kulttuuri/art-1.html",
            "feed_url": "f",
            "userspace": "u",
        }
        redis = MagicMock()
        with patch("tasks.article_processor.requests") as mock_requests, patch(
            "tasks.article_processor.get_redis_client", return_value=redis
        ):
            mock_requests.head.return_value.status_code = 404
            mock_requests.post.return_value.status_code = 201
            ArticleProcessor().store_article(article)
            stored = mock_requests.post.call_args.kwargs["json"]
        assert stored["section"] == "culture"
        assert stored["section_source"] == "path"
        redis.delete.assert_called_once_with(*STREAM_CACHE_KEYS)
        assert set(STREAM_CACHE_KEYS) >= {
            "stream_rss_xml",
            *(f"stream_rss_xml:{s}" for s in SECTIONS),
        }


class TestStoreAnnotationResections:
    def _store(self, doc: dict, topics: list[str]):
        from tasks import annotator

        redis = MagicMock()
        with patch("tasks.annotator.requests") as mock_requests, patch(
            "tasks.annotator.get_redis_client", return_value=redis
        ):
            mock_requests.get.return_value.status_code = 200
            mock_requests.get.return_value.json.return_value = dict(doc)
            mock_requests.put.return_value.status_code = 201
            ok = annotator.store_annotation(
                "a1", {"topics": topics, "priority": "low", "sentiment": "neutral"}
            )
            assert ok
            written = mock_requests.put.call_args.kwargs["json"]
        return written, redis

    def test_topic_moves_default_article(self):
        written, redis = self._store(
            {"_id": "a1", "section": "main", "section_source": "default"}, ["sports"]
        )
        assert written["section"] == "sports"
        assert written["section_source"] == "topic"
        redis.delete.assert_called_once()

    def test_path_article_keeps_section(self):
        written, redis = self._store(
            {"_id": "a1", "section": "culture", "section_source": "path"}, ["sports"]
        )
        assert written["section"] == "culture"
        redis.delete.assert_not_called()
