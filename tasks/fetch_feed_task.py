import hashlib
import json
import os  # Added to read environment variables
import sys  # Added for sys.exit
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

            # Calculate hash of the document
            doc_hash = hashlib.sha256(json.dumps(doc, sort_keys=True).encode('utf-8')).hexdigest()

            # Check if the document already exists based on the hash
            if self.is_duplicate(doc_hash):
                print("Feed already exists and hasn't changed. Skipping storage.")
                return

            doc["_id"] = doc_hash  # Use the hash as the document ID

            try:
                res = requests.post(self.couchdb_url, json=doc)
                if res.status_code in (200, 201):
                    print("Feed stored successfully in CouchDB.")
                elif res.status_code == 404:
                    print("Database not found in CouchDB, cannot store feed.")
                    os._exit(1)
                else:
                    print(f"Failed to store feed in CouchDB: {res.text}")
                    os._exit(1)
            except requests.exceptions.RequestException as e:
                print(f"Error storing feed in CouchDB: {e}")
                os._exit(1)
        else:
            print(f"Failed to fetch: {self.url} with status code: {response.status_code}")

    def cancel(self):
        if self.timer is not None:
            self.timer.cancel()

    def is_duplicate(self, doc_hash):
        """
        Checks if a document with the given hash already exists in CouchDB.
        """
        try:
            # Attempt to retrieve the document by its ID (hash)
            response = requests.get(f"{self.couchdb_url}/{doc_hash}")
            if response.status_code == 200:
                # Document exists
                return True
            elif response.status_code == 404:
                # Document does not exist
                return False
            else:
                print(f"Error checking for duplicate: {response.text}")
                os._exit(1)
        except requests.exceptions.RequestException as e:
            print(f"Error checking for duplicate: {e}")
            os._exit(1)