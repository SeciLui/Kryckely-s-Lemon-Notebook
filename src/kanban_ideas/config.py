"""Application-wide configuration constants."""

from __future__ import annotations

from pathlib import Path
from typing import Final

APP_TITLE: Final[str] = "Citron Lab – Kanban d'idées"
PACKAGE_ROOT: Final[Path] = Path(__file__).resolve().parent
PROJECT_ROOT: Final[Path] = PACKAGE_ROOT.parent.parent
DATA_ROOT: Final[Path] = PROJECT_ROOT / "data"
IDEAS_ROOT: Final[Path] = DATA_ROOT / "ideas"
IDEAS_ROOT.mkdir(parents=True, exist_ok=True)

STATUSES: Final[list[str]] = [
    "Inbox",
    "À tester",
    "En test",
    "À analyser",
    "Best-of",
    "Kill",
]

TRANSCRIBE_COMMAND_TEMPLATE: Final[list[str]] = [
    "vibe",
    "--input",
    "{input}",
    "--output",
    "{output}",
]
