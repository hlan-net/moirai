import unittest
from datetime import datetime, timezone
from tasks.article_processor import ArticleProcessor


class TestArticleProcessor(unittest.TestCase):
    def test_process_feed(self):
        # Mock feed content
        now = datetime.now(timezone.utc)
        pub_date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

        feed_content = f"""
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <item>
                    <title>Test Article</title>
                    <link>http://example.com/article</link>
                    <description>This is a summary.</description>
                    <pubDate>{pub_date}</pubDate>
                </item>
            </channel>
        </rss>
        """

        processor = ArticleProcessor()
        feed_title, articles = processor.process_feed(
            "http://example.com/feed", feed_content
        )

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], "Test Article")
        self.assertEqual(articles[0]["link"], "http://example.com/article")
        self.assertEqual(articles[0]["summary"], "This is a summary.")


if __name__ == "__main__":
    unittest.main()
