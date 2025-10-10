"""Domain models for the Kanban Ideas application."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from . import config


def now_iso() -> str:
    """Return the current timestamp in ISO format (seconds precision)."""

    return dt.datetime.now().isoformat(timespec="seconds")


def slugify(text: str) -> str:
    """Generate a filesystem-friendly slug from *text*."""

    sanitized = "".join(c if c.isalnum() or c in {" ", "-", "_"} else "_" for c in text)
    slug = "_".join(sanitized.strip().split())
    return slug[:64] or "idee"


@dataclass(slots=True)
class Idea:
    """Represent a single idea tracked inside the kanban board."""

    id: str
    title: str
    created_at: str
    status: str = "Inbox"
    category: str = ""
    tags: List[str] = field(default_factory=list)
    folder: Path = field(default_factory=Path)
    files: Dict[str, List[str]] = field(
        default_factory=lambda: {"audio": []}
    )

    @classmethod
    def create(cls, title: str, *, base_dir: Path | None = None) -> "Idea":
        """Create a new idea on disk and return the corresponding instance."""

        base = base_dir or config.IDEAS_ROOT
        base.mkdir(parents=True, exist_ok=True)

        uid = uuid.uuid4().hex[:8]
        timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        folder_name = f"{timestamp}_{uid}_{slugify(title)}"
        folder_path = base / folder_name
        (folder_path / "audio").mkdir(parents=True, exist_ok=True)

        idea = cls(
            id=uid,
            title=title or f"idée_{uid}",
            created_at=now_iso(),
            status="Inbox",
            folder=folder_path,
        )
        idea.save()
        return idea

    @classmethod
    def load(cls, folder_path: Path) -> "Idea" | None:
        """Load an idea from *folder_path* if possible."""

        idea_json = folder_path / "idea.json"
        if not idea_json.is_file():
            return None
        with idea_json.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return cls(
            id=payload.get("id", ""),
            title=payload.get("title", ""),
            created_at=payload.get("created_at", ""),
            status=payload.get("status", "Inbox"),
            category=payload.get("category", ""),
            tags=list(payload.get("tags", [])),
            folder=folder_path,
            files={key: list(value) for key, value in payload.get("files", {"audio": []}).items()},
        )

    def save(self) -> None:
        """Persist the idea metadata to disk."""

        idea_json = self.folder / "idea.json"
        payload = {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "status": self.status,
            "category": self.category,
            "tags": self.tags,
            "files": self.files,
        }
        with idea_json.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    # Convenience helpers -------------------------------------------------
    def transcript_path(self) -> Path:
        return self.folder / "transcript.txt"

    def analysis_path(self) -> Path:
        return self.folder / "analysis.json"

    def audio_dir(self) -> Path:
        return self.folder / "audio"

    def audio_files(self) -> List[Path]:
        files: List[Path] = []
        for raw in self.files.get("audio", []):
            candidate = Path(raw)
            files.append(candidate if candidate.is_absolute() else self.folder / candidate)
        return files

    def register_audio(self, path: Path) -> None:
        """Track a new audio file relative to the idea folder."""

        relative = path.relative_to(self.folder) if path.is_relative_to(self.folder) else path
        entries = self.files.setdefault("audio", [])
        if str(relative) not in entries:
            entries.append(str(relative))
