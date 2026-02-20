"""Entrypoint for a single scheduler run (CronJob mode).

This script is the dedicated entrypoint for the periodic feed-fetch scheduler.
It initialises the database, triggers one fetch cycle across all feeds, and
then exits cleanly.

Usage:
    python run_scheduler.py

In Kubernetes this is invoked by a CronJob on a configurable schedule
(e.g. every 10 minutes).  In Docker Compose it can be run on-demand:

    docker compose run --rm api python run_scheduler.py
"""

import logging
import os
import sys

from tasks import init
from tasks.scheduler import _process_feeds
from api.db_config import get_couchdb_uri

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Initialising database...")
    init.run()
    logger.info("Database initialised. Running scheduler cycle...")

    db_url = get_couchdb_uri()
    feeds_db_url = f"{db_url}feeds/_all_docs?include_docs=true"

    result = _process_feeds(feeds_db_url)

    if result.get("error"):
        logger.error(f"Scheduler cycle failed: {result.get('error')}")
        sys.exit(1)

    logger.info(
        f"Scheduler cycle complete. "
        f"total={result.get('total', 0)} "
        f"started={result.get('started', 0)} "
        f"skipped={result.get('skipped', 0)}"
    )
