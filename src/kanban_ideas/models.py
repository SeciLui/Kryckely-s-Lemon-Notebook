"""Domain models for the Kanban Ideas application."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List

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
class IdeaContext:
    """Describe one ideal context of use for an idea."""

    label: str = ""
    channel: str = "IRL"
    constraints: str = ""

    @classmethod
    def from_dict(cls, payload: Dict[str, Any] | None) -> "IdeaContext":
        payload = payload or {}
        return cls(
            label=str(payload.get("label", "")),
            channel=str(payload.get("channel", "IRL")),
            constraints=str(payload.get("constraints", "")),
        )

    def to_dict(self) -> Dict[str, str]:
        return {
            "label": self.label,
            "channel": self.channel,
            "constraints": self.constraints,
        }


@dataclass(slots=True)
class TestSignals:
    """Capture observable signals emitted during a test run."""

    smile: int = 0
    laugh: int = 0
    relance: int = 0
    fluidite: int = 0
    awkward: int = 0

    @classmethod
    def from_dict(cls, payload: Dict[str, Any] | None) -> "TestSignals":
        payload = payload or {}
        return cls(
            smile=int(payload.get("smile", 0)),
            laugh=int(payload.get("laugh", 0)),
            relance=int(payload.get("relance", 0)),
            fluidite=int(payload.get("fluidite", 0)),
            awkward=int(payload.get("awkward", 0)),
        )

    def to_dict(self) -> Dict[str, int]:
        return {
            "smile": int(self.smile),
            "laugh": int(self.laugh),
            "relance": int(self.relance),
            "fluidite": int(self.fluidite),
            "awkward": int(self.awkward),
        }


@dataclass(slots=True)
class TestRun:
    """Represent one experiment performed with the idea."""

    date: str = ""
    mode: str = "solo (répétition)"
    context_ref: str = ""
    partner_profile: str = ""
    version_used: str = "A"
    outcome_score: int = 0
    signals: TestSignals = field(default_factory=TestSignals)
    notes: str = ""
    evidence: List[str] = field(default_factory=list)
    micro_tweaks: List[str] = field(default_factory=list)
    run_decision: str = "tweak"

    @classmethod
    def from_dict(cls, payload: Dict[str, Any] | None) -> "TestRun":
        payload = payload or {}
        return cls(
            date=str(payload.get("date", "")),
            mode=str(payload.get("mode", "solo (répétition)")),
            context_ref=str(payload.get("context_ref", "")),
            partner_profile=str(payload.get("partner_profile", "")),
            version_used=str(payload.get("version_used", "A")),
            outcome_score=int(payload.get("outcome_score", 0)),
            signals=TestSignals.from_dict(payload.get("signals", {})),
            notes=str(payload.get("notes", "")),
            evidence=[str(item) for item in payload.get("evidence", [])],
            micro_tweaks=[str(item) for item in payload.get("micro_tweaks", [])],
            run_decision=str(payload.get("run_decision", "tweak")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "mode": self.mode,
            "context_ref": self.context_ref,
            "partner_profile": self.partner_profile,
            "version_used": self.version_used,
            "outcome_score": int(self.outcome_score),
            "signals": self.signals.to_dict(),
            "notes": self.notes,
            "evidence": list(self.evidence),
            "micro_tweaks": list(self.micro_tweaks),
            "run_decision": self.run_decision,
        }


@dataclass(slots=True)
class IdeaBestOf:
    """Curated delivery details for validated ideas."""

    final_wording: str = ""
    delivery_tips: List[str] = field(default_factory=list)
    do_use_when: List[str] = field(default_factory=list)
    avoid_when: List[str] = field(default_factory=list)
    example_dialogues: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any] | None) -> "IdeaBestOf":
        payload = payload or {}
        return cls(
            final_wording=str(payload.get("final_wording", "")),
            delivery_tips=[str(item) for item in payload.get("delivery_tips", [])],
            do_use_when=[str(item) for item in payload.get("do_use_when", [])],
            avoid_when=[str(item) for item in payload.get("avoid_when", [])],
            example_dialogues=[str(item) for item in payload.get("example_dialogues", [])],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "final_wording": self.final_wording,
            "delivery_tips": list(self.delivery_tips),
            "do_use_when": list(self.do_use_when),
            "avoid_when": list(self.avoid_when),
            "example_dialogues": list(self.example_dialogues),
        }


@dataclass(slots=True)
class IdeaFiles:
    """Collection of paths to artefacts linked to an idea."""

    audio: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any] | None) -> "IdeaFiles":
        payload = payload or {}
        audio = payload.get("audio")
        if isinstance(audio, dict):  # Backward compatibility with legacy layout
            audio = audio.get("audio", [])
        return cls(
            audio=[str(item) for item in (audio or [])],
            evidence=[str(item) for item in payload.get("evidence", [])],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audio": list(self.audio),
            "evidence": list(self.evidence),
        }


@dataclass(slots=True)
class Idea:
    """Represent a single idea tracked inside the kanban board."""

    id: str
    title: str
    created_at: str
    updated_at: str
    status: str = "Inbox"
    one_liner: str = ""
    category: str = ""
    tags: List[str] = field(default_factory=list)
    purpose: str = ""
    audience_hint: str = ""
    success_criteria: str = ""
    risks: List[str] = field(default_factory=list)
    contexts: List[IdeaContext] = field(default_factory=list)
    test_instructions: str = ""
    next_test_context: str = ""
    priority: str = "low"
    test_runs: List[TestRun] = field(default_factory=list)
    decision: str = "Keep"
    rationale: str = ""
    next_actions: List[str] = field(default_factory=list)
    best_of: IdeaBestOf = field(default_factory=IdeaBestOf)
    files: IdeaFiles = field(default_factory=IdeaFiles)
    version: int = 1
    variant_of: str = ""
    changelog: List[str] = field(default_factory=list)
    folder: Path = field(default_factory=Path)

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

        created_at = now_iso()
        idea = cls(
            id=folder_name,
            title=title or f"idée_{uid}",
            created_at=created_at,
            updated_at=created_at,
            status="Inbox",
            one_liner="",
            folder=folder_path,
            changelog=["Création de l'idée."],
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
        return cls.from_payload(payload, folder_path)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any], folder_path: Path) -> "Idea":
        """Instantiate an :class:`Idea` from a JSON payload."""

        created_at = str(payload.get("created_at", now_iso()))
        updated_at = str(payload.get("updated_at", created_at))
        contexts = [IdeaContext.from_dict(item) for item in payload.get("contexts", [])]
        test_runs = [TestRun.from_dict(item) for item in payload.get("test_runs", [])]

        return cls(
            id=str(payload.get("id", folder_path.name)),
            title=str(payload.get("title", "")),
            created_at=created_at,
            updated_at=updated_at,
            status=str(payload.get("status", "Inbox")),
            one_liner=str(payload.get("one_liner", "")),
            category=str(payload.get("category", "")),
            tags=[str(tag) for tag in payload.get("tags", [])],
            purpose=str(payload.get("purpose", "")),
            audience_hint=str(payload.get("audience_hint", "")),
            success_criteria=str(payload.get("success_criteria", "")),
            risks=[str(risk) for risk in payload.get("risks", [])],
            contexts=contexts,
            test_instructions=str(payload.get("test_instructions", "")),
            next_test_context=str(payload.get("next_test_context", "")),
            priority=str(payload.get("priority", "low")),
            test_runs=test_runs,
            decision=str(payload.get("decision", "Keep")),
            rationale=str(payload.get("rationale", "")),
            next_actions=[str(item) for item in payload.get("next_actions", [])],
            best_of=IdeaBestOf.from_dict(payload.get("best_of", {})),
            files=IdeaFiles.from_dict(payload.get("files", {})),
            version=int(payload.get("version", 1)),
            variant_of=str(payload.get("variant_of", "")),
            changelog=[str(item) for item in payload.get("changelog", [])],
            folder=folder_path,
        )

    def to_payload(self) -> Dict[str, Any]:
        """Return a JSON-serialisable representation of the idea."""

        payload = {
            "id": self.id,
            "title": self.title,
            "one_liner": self.one_liner,
            "status": self.status,
            "category": self.category,
            "tags": list(self.tags),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "purpose": self.purpose,
            "audience_hint": self.audience_hint,
            "success_criteria": self.success_criteria,
            "risks": list(self.risks),
            "contexts": [context.to_dict() for context in self.contexts],
            "test_instructions": self.test_instructions,
            "next_test_context": self.next_test_context,
            "priority": self.priority,
            "test_runs": [run.to_dict() for run in self.test_runs],
            "tests_total": self.tests_total,
            "tests_by_context": self.tests_by_context,
            "effectiveness_score": self.effectiveness_score,
            "decision": self.decision,
            "rationale": self.rationale,
            "next_actions": list(self.next_actions),
            "best_of": self.best_of.to_dict(),
            "files": self.files.to_dict(),
            "version": int(self.version),
            "variant_of": self.variant_of,
            "changelog": list(self.changelog),
        }
        return payload

    def save(self) -> None:
        """Persist the idea metadata to disk."""

        self.updated_at = now_iso()
        idea_json = self.folder / "idea.json"
        idea_json.parent.mkdir(parents=True, exist_ok=True)
        with idea_json.open("w", encoding="utf-8") as handle:
            json.dump(self.to_payload(), handle, ensure_ascii=False, indent=2)

    # Convenience helpers -------------------------------------------------
    def transcript_path(self) -> Path:
        return self.folder / "transcript.txt"

    def analysis_path(self) -> Path:
        return self.folder / "analysis.json"

    def audio_dir(self) -> Path:
        return self.folder / "audio"

    def audio_files(self) -> List[Path]:
        files: List[Path] = []
        for raw in self.files.audio:
            candidate = Path(raw)
            files.append(candidate if candidate.is_absolute() else self.folder / candidate)
        return files

    def register_audio(self, path: Path) -> None:
        """Track a new audio file relative to the idea folder."""

        relative = path.relative_to(self.folder) if path.is_relative_to(self.folder) else path
        if str(relative) not in self.files.audio:
            self.files.audio.append(str(relative))

    # Derived metrics -----------------------------------------------------
    @property
    def tests_total(self) -> int:
        return len(self.test_runs)

    @property
    def tests_by_context(self) -> Dict[str, int]:
        counter: Counter[str] = Counter()
        for run in self.test_runs:
            if run.context_ref:
                counter[run.context_ref] += 1
        return dict(counter)

    @property
    def effectiveness_score(self) -> int:
        if not self.test_runs:
            return 0

        outcome_avg = sum(run.outcome_score for run in self.test_runs) / len(self.test_runs)
        laugh_bonus = sum(run.signals.laugh for run in self.test_runs) * 5
        relance_bonus = sum(run.signals.relance for run in self.test_runs) * 5
        awkward_avg = sum(run.signals.awkward for run in self.test_runs) / len(self.test_runs)

        raw_score = outcome_avg * 18 + laugh_bonus + relance_bonus - awkward_avg * 10
        return max(0, min(100, int(round(raw_score))))

    def iter_test_runs(self) -> Iterable[TestRun]:
        """Yield each stored test run."""

        return iter(self.test_runs)
