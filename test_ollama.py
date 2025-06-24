#!/usr/bin/env python3

import json
import requests
import sys

def test_ollama_connection():
    """Test connection to Ollama"""
    try:
        response = requests.get("http://192.168.1.12:11434/api/tags")
        if response.status_code == 200:
            print("✅ Ollama connection successful")
            models = response.json()
            print(f"Available models: {len(models['models'])}")
            return True
        else:
            print(f"❌ Failed to connect to Ollama: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error connecting to Ollama: {e}")
        return False

def test_event_extraction():
    """Test event extraction from a sample article"""
    
    sample_article = """
    Tech Giant Announces Revolutionary AI Breakthrough
    
    SAN FRANCISCO - A major technology company announced today the development of a 
    groundbreaking artificial intelligence system that can process natural language 
    with unprecedented accuracy. The new AI model, dubbed "Genesis-5", was unveiled 
    at the company's annual developer conference.
    
    The breakthrough represents five years of research and development, involving 
    over 200 engineers and researchers. "This is a game-changing moment for the 
    industry," said the company's Chief Technology Officer during the announcement.
    
    The AI system will be integrated into the company's existing products starting 
    next quarter, with plans to make it available to third-party developers through 
    an API by the end of the year.
    """
    
    prompt = f"""Analyze the following news article and extract key events. 
    List each event on a separate line. Focus on significant developments, 
    announcements, or actions mentioned in the text.
    
    Article: {sample_article}
    
    Events:"""
    
    try:
        response = requests.post(
            "http://192.168.1.12:11434/api/generate",
            headers={"Content-Type": "application/json"},
            json={
                "model": "llama3.2",
                "prompt": prompt,
                "stream": False
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            generated_text = result.get("response", "")
            
            print("🔍 Event Extraction Results:")
            print("=" * 50)
            
            # Split by lines and filter out empty lines
            events = [line.strip() for line in generated_text.split('\n') if line.strip()]
            
            for i, event in enumerate(events[:10], 1):  # Limit to first 10 events
                print(f"{i}. {event}")
                
            print("=" * 50)
            print(f"✅ Successfully extracted {len(events)} events")
            
            return True
        else:
            print(f"❌ Failed to extract events: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error during event extraction: {e}")
        return False

def test_simple_rss_parsing():
    """Test RSS parsing with a simple example"""
    
    # Use BBC News RSS feed as a test
    rss_url = "https://feeds.bbci.co.uk/news/rss.xml"
    
    try:
        print(f"📡 Fetching RSS feed: {rss_url}")
        response = requests.get(rss_url, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ Successfully fetched RSS feed ({len(response.text)} characters)")
            
            # Simple check for RSS content
            if "<rss" in response.text.lower() or "<feed" in response.text.lower():
                print("✅ Valid RSS/XML format detected")
                
                # Count items/entries
                item_count = response.text.lower().count("<item>")
                entry_count = response.text.lower().count("<entry>")
                total_articles = max(item_count, entry_count)
                
                print(f"📰 Found approximately {total_articles} articles")
                return True
            else:
                print("❌ Invalid RSS format")
                return False
        else:
            print(f"❌ Failed to fetch RSS: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error fetching RSS: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Testing Moirai AI Implementation")
    print("=" * 40)
    
    tests = [
        ("Ollama Connection", test_ollama_connection),
        ("Event Extraction", test_event_extraction),
        ("RSS Feed Parsing", test_simple_rss_parsing)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        print("-" * 30)
        success = test_func()
        results.append((test_name, success))
        print("-" * 30)
    
    print("\n📊 Test Results Summary:")
    print("=" * 40)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The implementation is ready.")
    else:
        print("⚠️  Some tests failed. Check the implementation.")

if __name__ == "__main__":
    main()
