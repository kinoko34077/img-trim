"""Resolve the shared application directory for source and frozen builds."""

from pathlib import Path
import sys


def application_dir() -> Path:
    """Return the directory that owns app settings and launch-time files."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # This module lives one package level below the application root.
    return Path(__file__).resolve().parent.parent
