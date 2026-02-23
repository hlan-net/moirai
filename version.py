"""
Moirai version information
"""

import os

VERSION = "0.5.1-dev"
BUILD_NUMBER = os.environ.get("BUILD_NUMBER", "dev")


def get_version_string():
    """Returns formatted version string"""
    return f"Moirai v{VERSION} (build {BUILD_NUMBER})"
