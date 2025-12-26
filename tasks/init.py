import os
import requests
import time

# initialise the CouchDB database if they don't yet exists

def init_db():
  db_url = os.environ.get("COUCHDB_URI", "http://localhost:5984/")
  dbs = ['feeds', 'articles', 'events']

  # Wait for CouchDB to be ready
  max_retries = 10
  for i in range(max_retries):
    try:
      requests.get(db_url)
      print("CouchDB is up and reachable.")
      break
    except requests.exceptions.RequestException:
      if i < max_retries - 1:
        print(f"Waiting for CouchDB... (attempt {i+1}/{max_retries})")
        time.sleep(5)
      else:
        print("CouchDB reachable timeout. Exiting.")
        os._exit(1)

  for db_name in dbs:
    try:
       # Check if the database exists
      response = requests.get(f"{db_url}{db_name}")
      if response.status_code == 200:
        # Database exists, no need to create
        print(f"Database '{db_name}' exists, continuing...")
        continue

      # If the database doesn't exist, create it
      if response.status_code == 404:
        print(f"Database '{db_name}' does not exist, creating...")
        response = requests.put(f"{db_url}{db_name}")
        if response.status_code == 201:
          print(f"Database '{db_name}' created successfully.")
        else:
          print(f"Failed to create database '{db_name}': {response.text}")
          os._exit(1)
      else:
        print(f"Unexpected status code when checking database '{db_name}': {response.status_code} - {response.text}")
        os._exit(1)

    except requests.exceptions.RequestException as e:
        print(f"Error checking/creating database '{db_name}': {e}")
        os._exit(1)

def run():
  print("Initialising database...")
  init_db()
