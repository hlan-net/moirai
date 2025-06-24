from bs4 import BeautifulSoup
from nltk.tokenize import sent_tokenize
from sentence_transformers import SentenceTransformer
import numpy as np
import requests
import json
import os
from .article_processor import ArticleProcessor

class EventCorrelator:
    def __init__(self, articles):
        self.articles = articles
        self.ollama_url = os.environ.get("OLLAMA_URL", "http://192.168.1.12:11434")
        self.model_name = os.environ.get("OLLAMA_MODEL", "llama3.2")
        try:
            self.sentence_model = SentenceTransformer('paraphrase-MiniLM-L6-v2')
        except Exception as e:
            print(f"Warning: Could not load sentence transformer model: {e}")
            self.sentence_model = None

    def analyze_articles(self):
        """
        Analyze the fetched articles and extract relevant events.
        """
        correlated_events = []
        for article in self.articles:
            events = self.extract_events(article)
            correlated_events.extend(events)
        return correlated_events

    def extract_events(self, article):
        """
        Extract events from a single article using NLP.
        """
        events = []
        # Handle both article dictionary and raw text
        if isinstance(article, dict):
            if 'description' in article:
                text = article['description']
            elif 'body' in article:
                soup = BeautifulSoup(article['body'], 'html.parser')
                text = soup.get_text()
            else:
                text = str(article)
        else:
            text = str(article)
            
        sentences = sent_tokenize(text)
        
        # Generate embeddings if model is available
        if self.sentence_model:
            try:
                sentence_embeddings = self.sentence_model.encode(sentences)
            except Exception as e:
                print(f"Warning: Could not generate embeddings: {e}")

        # Use Ollama for advanced event detection
        try:
            prompt = f"""Analyze the following news article and extract key events. 
            List each event on a separate line. Focus on significant developments, 
            announcements, or actions mentioned in the text.
            
            Article: {text[:1000]}...
            
            Events:"""
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                headers={"Content-Type": "application/json"},
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                generated_text = result.get("response", "")
                # Split by lines and filter out empty lines
                events = [line.strip() for line in generated_text.split('\n') if line.strip()]
                print(f"Extracted {len(events)} events using Ollama")
            else:
                print(f"Failed to extract events using Ollama: {response.text}")
                # Fallback to basic keyword detection
                events = self.extract_events_fallback(text)
        except requests.exceptions.RequestException as e:
            print(f"Error connecting to Ollama: {e}")
            # Fallback to basic keyword detection
            events = self.extract_events_fallback(text)

        return events
    
    def extract_events_fallback(self, text):
        """
        Fallback method for event extraction using basic keyword detection.
        """
        events = []
        sentences = sent_tokenize(text)
        
        # Look for sentences containing event-related keywords
        event_keywords = ['announced', 'launched', 'released', 'developed', 'created', 
                         'founded', 'acquired', 'merged', 'partnership', 'agreement',
                         'breakthrough', 'discovered', 'revealed', 'published', 'introduced']
        
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in event_keywords):
                events.append(sentence.strip())
                
        return events[:5]  # Limit to top 5 events

    def run(self):
        """
        Run the event correlation process.
        """
        correlated_events = self.analyze_articles()
        self.handle_correlated_events(correlated_events)

    def handle_correlated_events(self, events):
        """
        Handle the correlated events, store or further analyze.
        """
        for event in events:
            print(f"Correlated event: {event}")
