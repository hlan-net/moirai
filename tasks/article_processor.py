import feedparser
import hashlib
import json
import os
import requests
import sys
from datetime import datetime
from bs4 import BeautifulSoup
import re

class ArticleProcessor:
    def __init__(self):
        self.couchdb_url = os.environ.get("COUCHDB_URI", "http://localhost:5984/")
        self.articles_db = self.couchdb_url + "articles"
        
    def process_feed(self, feed_url, feed_content):
        """
        Process RSS feed content and extract individual articles.
        """
        try:
            # Parse the RSS feed
            feed = feedparser.parse(feed_content)
            
            articles = []
            for entry in feed.entries:
                article = self.extract_article_data(entry, feed_url)
                if article:
                    articles.append(article)
                    
            return articles
        except Exception as e:
            print(f"Error processing feed {feed_url}: {e}")
            return []
    
    def extract_article_data(self, entry, feed_url):
        """
        Extract structured data from a single RSS entry.
        """
        try:
            # Extract basic information
            title = getattr(entry, 'title', 'No Title')
            link = getattr(entry, 'link', '')
            description = getattr(entry, 'description', '')
            published = getattr(entry, 'published', '')
            
            # Clean and extract text content
            soup = BeautifulSoup(description, 'html.parser')
            clean_description = soup.get_text().strip()
            
            # Create article document
            article = {
                'title': title,
                'link': link,
                'description': clean_description,
                'published': published,
                'feed_url': feed_url,
                'extracted_at': datetime.utcnow().isoformat(),
                'content_length': len(clean_description),
                'language': self.detect_language(clean_description),
                'tags': self.extract_tags(title + ' ' + clean_description),
                'summary': self.create_summary(clean_description)
            }
            
            # Generate unique ID based on content
            article_id = self.generate_article_id(article)
            article['_id'] = article_id
            
            return article
            
        except Exception as e:
            print(f"Error extracting article data: {e}")
            return None
    
    def generate_article_id(self, article):
        """
        Generate a unique ID for the article based on title and link.
        """
        content = f"{article['title']}{article['link']}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def detect_language(self, text):
        """
        Simple language detection (placeholder for more sophisticated detection).
        """
        # This is a simplified approach - in production, use a proper language detection library
        common_english_words = ['the', 'and', 'is', 'in', 'to', 'of', 'a', 'that', 'it', 'with']
        words = text.lower().split()[:50]  # Check first 50 words
        english_count = sum(1 for word in words if word in common_english_words)
        
        return 'en' if english_count > len(words) * 0.1 else 'unknown'
    
    def extract_tags(self, text):
        """
        Extract relevant tags/keywords from the text.
        """
        # Simple keyword extraction based on common patterns
        keywords = []
        
        # Look for capitalized words (potential proper nouns)
        capitalized_words = re.findall(r'\b[A-Z][a-z]+\b', text)
        keywords.extend(capitalized_words[:10])  # Limit to 10
        
        # Look for technology-related terms
        tech_terms = ['AI', 'ML', 'blockchain', 'cryptocurrency', 'software', 'hardware', 
                     'security', 'privacy', 'cloud', 'API', 'database', 'algorithm']
        
        for term in tech_terms:
            if term.lower() in text.lower():
                keywords.append(term)
        
        return list(set(keywords))  # Remove duplicates
    
    def create_summary(self, text):
        """
        Create a brief summary of the article.
        """
        sentences = text.split('.')
        # Return first sentence if it's substantial, otherwise first two sentences
        if len(sentences) > 0 and len(sentences[0]) > 50:
            return sentences[0].strip() + '.'
        elif len(sentences) > 1:
            return (sentences[0] + '.' + sentences[1]).strip() + '.'
        else:
            return text[:200] + '...' if len(text) > 200 else text
    
    def store_article(self, article):
        """
        Store the processed article in CouchDB.
        """
        try:
            # Check if article already exists
            if self.article_exists(article['_id']):
                print(f"Article already exists: {article['title']}")
                return False
            
            # Store the article
            response = requests.post(self.articles_db, json=article)
            
            if response.status_code in (200, 201):
                print(f"Article stored successfully: {article['title']}")
                return True
            else:
                print(f"Failed to store article: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"Error storing article: {e}")
            return False
    
    def article_exists(self, article_id):
        """
        Check if an article already exists in the database.
        """
        try:
            response = requests.get(f"{self.articles_db}/{article_id}")
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def get_all_articles(self):
        """
        Retrieve all articles from the database for analysis.
        """
        try:
            response = requests.get(f"{self.articles_db}/_all_docs", 
                                  params={"include_docs": "true"})
            
            if response.status_code == 200:
                data = response.json()
                return [row["doc"] for row in data["rows"]]
            else:
                print(f"Failed to retrieve articles: {response.text}")
                return []
                
        except requests.exceptions.RequestException as e:
            print(f"Error retrieving articles: {e}")
            return []
