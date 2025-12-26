import unittest
from datetime import datetime
from tasks.article_processor import ArticleProcessor

class TestArticleProcessor(unittest.TestCase):
    def test_process_feed(self):
        # Mock feed content
        feed_content = """
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <item>
                    <title>Test Article</title>
                    <link>http://example.com/article</link>
                    <description>This is a summary.</description>
                    <pubDate>Fri, 26 Dec 2025 12:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>
        """
        
        processor = ArticleProcessor()
        articles = processor.process_feed("http://example.com/feed", feed_content)
        
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]['title'], "Test Article")
        self.assertEqual(articles[0]['link'], "http://example.com/article")
        self.assertEqual(articles[0]['summary'], "This is a summary.")
        
if __name__ == '__main__':
    unittest.main()
