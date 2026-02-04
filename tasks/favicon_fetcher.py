"""
Favicon fetcher utility for RSS feeds.
Attempts to fetch favicons from various common locations.
"""
import requests
from urllib.parse import urlparse, urljoin


def fetch_favicon_url(feed_url: str, timeout: int = 5) -> str:
    """
    Attempt to fetch the favicon URL for a given feed URL.
    
    Args:
        feed_url: The RSS feed URL
        timeout: Request timeout in seconds
        
    Returns:
        The favicon URL if found, empty string otherwise
    """
    try:
        parsed_url = urlparse(feed_url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        # Try common favicon locations in order of preference
        favicon_paths = [
            "/favicon.ico",
            "/favicon.png",
        ]
        
        headers = {'User-Agent': 'MoiraiBot/1.0 (+https://github.com/hlan-net/moirai)'}
        
        for path in favicon_paths:
            favicon_url = urljoin(base_url, path)
            try:
                response = requests.head(favicon_url, headers=headers, timeout=timeout, allow_redirects=True)
                if response.status_code == 200:
                    # Check if it's actually an image
                    content_type = response.headers.get('Content-Type', '')
                    if 'image' in content_type or path.endswith(('.ico', '.png', '.jpg', '.jpeg', '.svg')):
                        return favicon_url
            except requests.exceptions.RequestException:
                continue
        
        # If common paths don't work, try the default favicon.ico
        default_favicon = urljoin(base_url, "/favicon.ico")
        return default_favicon
        
    except Exception as e:
        print(f"Error fetching favicon for {feed_url}: {e}")
        return ""
