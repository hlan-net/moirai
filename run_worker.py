"""Entrypoint for the standalone enrichment worker process.

This script is the dedicated entrypoint for the continuous enrichment worker.
It initialises the database (creates DBs, indexes, design docs, default user)
and then starts the long-running CouchDB changes-feed listener.

Usage:
    python run_worker.py

In Kubernetes this is run as a single-replica Deployment so that only one
enrichment worker processes the changes feed at any time.
In Docker Compose it is run as a separate ``worker`` service.
"""

import logging
import signal
import sys

from tasks import init
from tasks.enrichment_worker import worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


def _handle_signal(signum: int, _frame: object) -> None:
    """Gracefully stop the worker on SIGTERM/SIGINT."""
    logger.info(f"Received signal {signum}, shutting down enrichment worker...")
    worker.running = False
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info("Initialising database...")
    init.run()
    logger.info("Database initialised. Starting enrichment worker...")

    worker.start()
    logger.info("Enrichment worker started. Waiting...")

    # Keep the main thread alive so the daemon worker thread stays running.
    worker.join()
