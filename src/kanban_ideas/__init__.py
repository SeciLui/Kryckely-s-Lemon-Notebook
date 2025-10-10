"""Kanban Ideas desktop application."""

from __future__ import annotations

from importlib import metadata

from .app import main

__all__ = ["main", "__version__"]

try:
    __version__ = metadata.version("kanban-ideas")
except metadata.PackageNotFoundError:  # pragma: no cover - fallback for local usage
    __version__ = "0.0.0"
