"""
Favicon fetcher utility for RSS feeds.
Attempts to fetch favicons from various common locations using HTTPS only.
"""
import requests
from urllib.parse import urlparse, urljoin


def fetch_favicon_url(feed_url: str, timeout: int = 5) -> str:
    """
    Attempt to fetch the favicon URL for a given feed URL using HTTPS only.
    
    This function enforces secure connections by:
    - Only using HTTPS for favicon requests
    - Verifying SSL certificates
    - Returning empty string if secure connection cannot be established
    
    Args:
        feed_url: The RSS feed URL
        timeout: Request timeout in seconds
        
    Returns:
        The HTTPS favicon URL if found and verified, empty string otherwise
    """
    try:
        parsed_url = urlparse(feed_url)
        # Always use HTTPS for favicon fetching, regardless of feed URL scheme
        base_url = f"https://{parsed_url.netloc}"
        
        # Try common favicon locations in order of preference
        favicon_paths = [
            "/favicon.ico",
            "/favicon.png",
        ]
        
        headers = {'User-Agent': 'MoiraiBot/1.0 (+https://github.com/hlan-net/moirai)'}
        
        for path in favicon_paths:
            favicon_url = urljoin(base_url, path)
            try:
                # Always verify SSL certificates - do not disable verification
                response = requests.head(favicon_url, headers=headers, timeout=timeout, allow_redirects=True, verify=True)
                if response.status_code == 200:
                    # Check if it's actually an image
                    content_type = response.headers.get('Content-Type', '')
                    if 'image' in content_type or path.endswith(('.ico', '.png', '.jpg', '.jpeg', '.svg')):
                        return favicon_url
            except requests.exceptions.RequestException:
                # If HTTPS connection fails (SSL error, timeout, etc.), continue to next path
                continue
        
        # If no verified favicon found, return empty string
        # Do not fall back to unverified or HTTP connections
        return ""
        
    except Exception as e:
        print(f"Error fetching favicon for {feed_url}: {e}")
        return ""
