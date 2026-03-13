"""
Moirai version information
"""

import os

VERSION = os.environ.get("APP_VERSION", "dev")
BUILD_NUMBER = os.environ.get("BUILD_NUMBER", "dev")


def get_version_string():
    """Returns formatted version string"""
    return f"Moirai v{VERSION} ({BUILD_NUMBER})"
