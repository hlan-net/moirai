"""
Moirai version information
"""

import os


def _read_build_info():
    """Read version and build number from containerized build-info file."""
    build_info_file = "/etc/moirai/build-info"
    version = "dev"
    build_number = "unknown"

    if os.path.exists(build_info_file):
        try:
            with open(build_info_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("APP_VERSION="):
                        version = line.split("=", 1)[1]
                    elif line.startswith("BUILD_NUMBER="):
                        build_number = line.split("=", 1)[1]
        except (IOError, OSError):
            pass  # Fall back to defaults if file can't be read

    return version, build_number


VERSION, BUILD_NUMBER = _read_build_info()


def get_version_string():
    """Returns formatted version string"""
    return f"Moirai v{VERSION} ({BUILD_NUMBER})"
