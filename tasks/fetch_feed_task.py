import os  # Added to read environment variables
import threading
import requests

class FetchFeedTask:
    def __init__(self, url, delay):
        self.url = url
        self.delay = delay
        self.timer = None
        # Use the COUCHDB_URI environment variable if available
        self.couchdb_url = os.environ.get("COUCHDB_URI", "http://localhost:5984/") + "feeds"

    def start(self):
        self.schedule_fetch()

    def schedule_fetch(self):
        self.timer = threading.Timer(self.delay, self.fetch_url)
        self.timer.start()

    def fetch_url(self):
        try:
            response = requests.get(self.url)
            self.handle_response(response)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {self.url}: {e}")
        finally:
            self.schedule_fetch()  # Reschedule for the next fetch

    def handle_response(self, response):
        if response.status_code == 200:
            print(f"Successfully fetched: {self.url}")
            # Prepare document with headers and body to store in CouchDB
            doc = {
                "url": self.url,
                "headers": dict(response.headers),
                "body": response.text
            }
            try:
                res = requests.post(self.couchdb_url, json=doc)
                if res.status_code in (200, 201):
                    print("Feed stored successfully in CouchDB.")
                else:
                    print(f"Failed to store feed in CouchDB: {res.text}")
            except requests.exceptions.RequestException as e:
                print(f"Error storing feed in CouchDB: {e}")
            
        else:
            print(f"Failed to fetch: {self.url} with status code: {response.status_code}")

    def cancel(self):
        if self.timer is not None:
            self.timer.cancel()