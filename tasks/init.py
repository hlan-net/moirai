import os
import requests

# initialise the CouchDB database if they don't yet exists

def init_db():
  db_url = os.environ.get("COUCHDB_URI", "http://localhost:5984/")
  dbs = ['feeds', 'articles', 'evnets']

  for db_name in dbs:
    try:
       # Check if the database exists
      response = requests.get(f"{db_url}{db_name}")
      if response.status_code == 200:
        # Database exists, no need to create
        print("Database exists, continuing...")
        return

      # If the database doesn't exist, create it
      if response.status_code == 404:
        print("Database does not exist, creating...")
        response = requests.put(f"{db_url}{db_name}")
        if response.status_code == 201:
          print("Database created successfully.")
          return
        else:
          print(f"Failed to create database: {response.text}")
          os._exit(1)
      else:
        print(f"Unexpected status code when checking database: {response.status_code} - {response.text}")
        os._exit(1)

    except requests.exceptions.RequestException as e:
        print(f"Error checking/creating database: {e}")
        os._exit(1)

def run():
  print("Initialising database...")
  init_db()