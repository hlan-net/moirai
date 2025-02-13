import threading
import requests

class FetchFeedTask:
    def __init__(self, url, delay):
        self.url = url
        self.delay = delay
        self.timer = None

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
            # Process the response content as needed
        else:
            print(f"Failed to fetch: {self.url} with status code: {response.status_code}")

    def cancel(self):
        if self.timer is not None:
            self.timer.cancel()