import os
from .cleanup_task import CleanupTask

# initialise the CouchDB database if they don't yet exists

def init_db():
  # Skip network check as initContainer handles it
  print("Assuming CouchDB is ready (handled by initContainer).")
  return

def run():
  print("Initialising database...")
  init_db()
  
  print("Starting cleanup task...")
  cleanup = CleanupTask()
  cleanup.start()
