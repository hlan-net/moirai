import unittest
import requests
from tasks.article_processor import ArticleProcessor

class TestLiveLWNFeed(unittest.TestCase):
    def test_fetch_and_parse_lwn(self):
        url = "https://lwn.net/headlines/rss"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Failed to fetch external feed: {e}")

        processor = ArticleProcessor()
        # Pass the real content to the processor
        feed_title, articles = processor.process_feed(url, response.text)
        
        # Basic validation to ensure parsing worked
        self.assertGreater(len(articles), 0, "Should find at least one article in LWN feed")
        
        first_article = articles[0]
        self.assertIn("title", first_article)
        self.assertIn("link", first_article)
        self.assertIn("lwn.net", first_article["link"])
        
if __name__ == '__main__':
    unittest.main()
