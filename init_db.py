#!/usr/bin/env python
"""Unified database initialisation entry-point.

Can be called as a standalone script (`python init_db.py`) or imported and
invoked from other Python code (e.g. the gunicorn on_starting hook).

This is the **single source of truth** for database bootstrap logic.  Both the
API (gunicorn) and the MCP server use this so it doesn't matter which service
starts first.
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


def run() -> None:
    """Create databases, indexes, design docs and the default admin user."""
    from tasks.init import init_db, ensure_default_user

    logger.info("Running database initialisation...")
    init_db()
    ensure_default_user()
    logger.info("Database initialisation complete.")


if __name__ == "__main__":
    run()
