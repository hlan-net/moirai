import threading
import os
import requests

def fetch_url(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print(f"Successfully fetched: {url}")
        else:
            print(f"Failed to fetch: {url} with status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")

def schedule_fetch(url, delay):
    """
    Schedule the fetch of a single URL after a given delay and then re-schedule every 10 minutes.
    """
    def periodic_fetch():
        fetch_url(url)
        # Schedule the next fetch after 600 seconds (10 minutes)
        threading.Timer(600, periodic_fetch).start()
    threading.Timer(delay, periodic_fetch).start()

def scheduled_url_fetch():
    """
    Reads URLs from files in the 'feeds' directory, and schedules each URL to be fetched.
    Each URL is scheduled with an initial delay so that requests are spread evenly over 10 minutes.
    """
    feeds_directory = 'feeds'
    urls = []
    for filename in os.listdir(feeds_directory):
        filepath = os.path.join(feeds_directory, filename)
        if os.path.isfile(filepath):
            with open(filepath, 'r') as file:
                for line in file.readlines():
                    url = line.strip()
                    if url:
                        urls.append(url)
    if urls:
        # Calculate delay interval for each URL so that they are spread evenly over 10 minutes
        interval = 600 / len(urls)
        for idx, url in enumerate(urls):
            delay = idx * interval
            schedule_fetch(url, delay)
        print(f"Scheduled {len(urls)} URL fetches spread over 10 minutes.")
    else:
        print("No URLs to fetch.")