"""Kanban Ideas desktop application."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path

from dotenv import load_dotenv

_PACKAGE_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = _PACKAGE_ROOT.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

from .app import main

__all__ = ["main", "__version__"]

try:
    __version__ = metadata.version("kanban-ideas")
except metadata.PackageNotFoundError:  # pragma: no cover - fallback for local usage
    __version__ = "0.0.0"
