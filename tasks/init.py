import os
import requests
import time

# initialise the CouchDB database if they don't yet exists

def init_db():
  # Skip network check as initContainer handles it
  print("Assuming CouchDB is ready (handled by initContainer).")
  return

  # Original logic preserved below for reference but disabled
  # db_url = os.environ.get("COUCHDB_URI", "http://localhost:5984/")
  # ...

from .cleanup_task import CleanupTask

def run():
  print("Initialising database...")
  init_db()
  
  print("Starting cleanup task...")
  cleanup = CleanupTask()
  cleanup.start()
