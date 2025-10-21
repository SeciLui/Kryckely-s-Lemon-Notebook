"""Application-wide configuration constants."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

APP_TITLE: Final[str] = "Citron Lab – Kanban d'idées"
PACKAGE_ROOT: Final[Path] = Path(__file__).resolve().parent
PROJECT_ROOT: Final[Path] = PACKAGE_ROOT.parent.parent
DATA_ROOT: Final[Path] = PROJECT_ROOT / "data"

_workspace_override = os.environ.get("KANBAN_IDEAS_WORKSPACE") or os.environ.get(
    "KANBAN_IDEAS_IDEAS_DIR"
)
if _workspace_override:
    IDEAS_ROOT: Final[Path] = Path(os.path.expanduser(_workspace_override)).resolve()
else:
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

