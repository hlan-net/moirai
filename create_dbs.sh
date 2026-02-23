#!/bin/sh

# DEPRECATED: This script is superseded by init_db.py which is the single
# source of truth for database initialisation.  Both the API (gunicorn) and
# the MCP server now use init_db.py instead.  This file is kept only as a
# manual fallback and will be removed in v0.5.0.
#
# Original purpose: create CouchDB databases as a pre-startup command in
# Docker Compose.

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
  return 0
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
  return 0
}

# Check CouchDB readiness
check_couchdb_ready

# Create required databases
# Keep in sync with tasks/init.py init_db()
create_database "_users"
create_database "feeds"
create_database "articles"
create_database "issues"
create_database "agent_configs"
create_database "config"
create_database "chat_history"
create_database "users"
create_database "feed_content"

echo "CouchDB database setup complete."
