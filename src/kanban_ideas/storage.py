"""Utility helpers for reading and writing idea data."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from . import config
from .models import Idea


def iter_idea_directories(base_dir: Path | None = None) -> Iterable[Path]:
    """Yield every idea directory stored in *base_dir*."""

    base = base_dir or config.IDEAS_ROOT
    base.mkdir(parents=True, exist_ok=True)
    return sorted(p for p in base.iterdir() if p.is_dir())


def load_all_ideas(base_dir: Path | None = None) -> List[Idea]:
    """Load every idea present in *base_dir*."""

    ideas: List[Idea] = []
    for folder in iter_idea_directories(base_dir):
        idea = Idea.load(folder)
        if idea:
            ideas.append(idea)
    return ideas


def read_text(path: Path) -> str:
    """Read UTF-8 text from *path* and return an empty string on failure."""

    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def write_text(path: Path, content: str) -> None:
    """Write UTF-8 *content* to *path*, creating parent folders when needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
