"""
Moirai version information
"""

import os

VERSION = "0.4.0"
BUILD_NUMBER = os.environ.get("BUILD_NUMBER", "dev")


def get_version_string():
    """Returns formatted version string"""
    return f"Moirai v{VERSION} (build {BUILD_NUMBER})"
