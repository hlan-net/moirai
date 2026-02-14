#!/bin/sh

# This script creates necessary CouchDB databases for the Moirai application.
# It's intended to be run as a pre-startup command in Docker Compose.

set -e

COUCHDB_USER=${COUCHDB_USER:-admin}
COUCHDB_PASSWORD=${COUCHDB_PASSWORD:-password}
COUCHDB_URI=${COUCHDB_URI:-http://couchdb:5984/}

echo "Waiting for CouchDB to be ready at ${COUCHDB_URI}..."

# Function to check if CouchDB is ready
check_couchdb_ready() {
  until curl -s -o /dev/null -w "%{http_code}" "${COUCHDB_URI}" | grep -q "200"; do
    echo "CouchDB not yet ready, waiting..."
    sleep 5
  done
  echo "CouchDB is ready!"
}

# Function to create a database if it doesn't exist
create_database() {
  db_name=$1
  echo "Checking database '$db_name'..."
  if ! curl -s -u "$COUCHDB_USER:$COUCHDB_PASSWORD" "${COUCHDB_URI}${db_name}" | grep -q '"error":"not_found"'; then
    echo "Database '$db_name' already exists."
  else
    echo "Creating database '$db_name'..."
    until curl -X PUT -u "$COUCHDB_USER:$COUCHDB_PASSWORD" "${COUCHDB_URI}${db_name}"; do
      echo "Failed to create database '$db_name', retrying..."
      sleep 5
    done
    echo "Database '$db_name' created successfully."
  fi
}

# Check CouchDB readiness
check_couchdb_ready

# Create required databases
create_database "_users"
create_database "feeds"
create_database "articles"
create_database "events"
create_database "trends"
create_database "agent_configs"
create_database "config" # The config DB is also used, ensure it's created

echo "CouchDB database setup complete."
