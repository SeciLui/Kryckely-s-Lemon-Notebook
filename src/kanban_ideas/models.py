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


PRIORITIES: tuple[str, ...] = ("low", "med", "high")
IDEA_DECISIONS: tuple[str, ...] = ("Keep", "Tweak", "Kill")
TEST_RUN_DECISIONS: tuple[str, ...] = ("keep", "tweak", "kill")
TEST_RUN_MODES: tuple[str, ...] = (
    "solo (répétition)",
    "sim (IA)",
    "live (IRL)",
    "scène",
)
CONTEXT_CHANNELS: tuple[str, ...] = ("IRL", "scène", "audio", "vidéo", "chat")

MAX_CONTEXTS: int = 3
MAX_TAGS: int = 6
MAX_NEXT_ACTIONS: int = 3
MAX_EXAMPLE_DIALOGUES: int = 2


def _clean_str_list(values: Iterable[Any], *, limit: int | None = None) -> List[str]:
    """Return a list of non-empty strings stripped from *values*.

    Parameters
    ----------
    values:
        Any iterable producing raw values to coerce to strings.
    limit:
        Optional maximum number of entries to keep. When provided, the
        resulting list is truncated to ``limit`` items. This is useful for the
        fields where the product requirements explicitly mention an upper
        bound (e.g. « ≤3 contextes », « 3–6 tags », « 1–3 next actions »).
    """

    cleaned: List[str] = []
    for item in values:
        text = str(item).strip()
        if not text:
            continue
        cleaned.append(text)
        if limit is not None and len(cleaned) >= limit:
            break
    return cleaned


def _clamp_int(value: Any, minimum: int, maximum: int, *, default: int) -> int:
    """Clamp *value* within ``[minimum, maximum]`` returning *default* on error."""

    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _normalise_choice(value: Any, allowed: Iterable[str], default: str) -> str:
    """Return *value* if it is part of *allowed*, otherwise *default*."""

    text = str(value).strip()
    allowed_set = set(allowed)
    return text if text in allowed_set else default


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

    def __post_init__(self) -> None:
        self.label = self.label.strip()
        raw_channel = str(self.channel).strip()
        if not raw_channel:
            self.channel = "IRL"
        else:
            canonical_map = {option.lower(): option for option in CONTEXT_CHANNELS}
            self.channel = canonical_map.get(raw_channel.lower(), raw_channel)
        self.constraints = self.constraints.strip()

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

    def __post_init__(self) -> None:
        self.smile = _clamp_int(self.smile, 0, 1, default=0)
        self.laugh = _clamp_int(self.laugh, 0, 1, default=0)
        self.relance = _clamp_int(self.relance, 0, 1, default=0)
        self.fluidite = _clamp_int(self.fluidite, 0, 5, default=0)
        self.awkward = _clamp_int(self.awkward, 0, 5, default=0)

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

    def __post_init__(self) -> None:
        self.date = str(self.date).strip()
        self.mode = _normalise_choice(self.mode, TEST_RUN_MODES, TEST_RUN_MODES[0])
        self.context_ref = str(self.context_ref).strip()
        self.partner_profile = str(self.partner_profile).strip()
        self.version_used = str(self.version_used).strip() or "A"
        self.outcome_score = _clamp_int(self.outcome_score, 0, 5, default=0)
        if not isinstance(self.signals, TestSignals):
            signals_payload: Dict[str, Any] = {}
            if hasattr(self.signals, "to_dict"):
                signals_payload = self.signals.to_dict()  # type: ignore[assignment]
            else:
                try:
                    signals_payload = dict(self.signals)
                except Exception:  # pragma: no cover - defensive fallback
                    signals_payload = {}
            self.signals = TestSignals.from_dict(signals_payload)
        self.notes = str(self.notes).strip()
        self.evidence = _clean_str_list(self.evidence)
        self.micro_tweaks = _clean_str_list(self.micro_tweaks)
        choice = _normalise_choice(self.run_decision.lower(), TEST_RUN_DECISIONS, "tweak")
        self.run_decision = choice

    @classmethod
    def from_dict(cls, payload: Dict[str, Any] | None) -> "TestRun":
        payload = payload or {}
        return cls(
            date=str(payload.get("date", "")),
            mode=str(payload.get("mode", "solo (répétition)")),
            context_ref=str(payload.get("context_ref", "")),
            partner_profile=str(payload.get("partner_profile", "")),
            version_used=str(payload.get("version_used", "A")),
            outcome_score=payload.get("outcome_score", 0),
            signals=TestSignals.from_dict(payload.get("signals", {})),
            notes=str(payload.get("notes", "")),
            evidence=payload.get("evidence", []),
            micro_tweaks=payload.get("micro_tweaks", []),
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

    def __post_init__(self) -> None:
        self.final_wording = self.final_wording.strip()
        self.delivery_tips = _clean_str_list(self.delivery_tips)
        self.do_use_when = _clean_str_list(self.do_use_when)
        self.avoid_when = _clean_str_list(self.avoid_when)
        self.example_dialogues = _clean_str_list(
            self.example_dialogues, limit=MAX_EXAMPLE_DIALOGUES
        )

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

    def __post_init__(self) -> None:
        self.audio = _clean_str_list(self.audio)
        self.evidence = _clean_str_list(self.evidence)

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

    def __post_init__(self) -> None:
        self._ensure_valid_state()

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
            "signals": self.signals,
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

        self._ensure_valid_state()
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

    @property
    def signals(self) -> Dict[str, float]:
        if not self.test_runs:
            return {
                "smile": 0,
                "laugh": 0,
                "relance": 0,
                "fluidite_avg": 0.0,
                "awkward_avg": 0.0,
            }

        runs_count = len(self.test_runs)
        smile_total = sum(run.signals.smile for run in self.test_runs)
        laugh_total = sum(run.signals.laugh for run in self.test_runs)
        relance_total = sum(run.signals.relance for run in self.test_runs)
        fluidite_avg = sum(run.signals.fluidite for run in self.test_runs) / runs_count
        awkward_avg = sum(run.signals.awkward for run in self.test_runs) / runs_count

        return {
            "smile": int(smile_total),
            "laugh": int(laugh_total),
            "relance": int(relance_total),
            "fluidite_avg": float(round(fluidite_avg, 2)),
            "awkward_avg": float(round(awkward_avg, 2)),
        }

    @property
    def signals_summary(self) -> Dict[str, float]:
        """Backward compatible alias for :pyattr:`signals`."""

        return self.signals

    def iter_test_runs(self) -> Iterable[TestRun]:
        """Yield each stored test run."""

        return iter(self.test_runs)

    # Internal helpers ---------------------------------------------------
    def _ensure_valid_state(self) -> None:
        self.id = str(self.id).strip()
        self.title = self.title.strip()
        self.created_at = str(self.created_at).strip()
        self.updated_at = str(self.updated_at).strip()
        self.status = _normalise_choice(self.status, config.STATUSES, "Inbox")
        self.one_liner = self.one_liner.strip()
        self.category = self.category.strip()
        self.tags = _clean_str_list(self.tags, limit=MAX_TAGS)
        self.purpose = self.purpose.strip()
        self.audience_hint = self.audience_hint.strip()
        self.success_criteria = self.success_criteria.strip()
        self.risks = _clean_str_list(self.risks)
        normalized_contexts: List[IdeaContext] = []
        for context in self.contexts:
            if isinstance(context, IdeaContext):
                normalized_contexts.append(IdeaContext.from_dict(context.to_dict()))
            else:
                normalized_contexts.append(IdeaContext.from_dict(context))
        self.contexts = normalized_contexts[:MAX_CONTEXTS]
        self.test_instructions = self.test_instructions.strip()
        self.next_test_context = self.next_test_context.strip()
        self.priority = _normalise_choice(self.priority, PRIORITIES, PRIORITIES[0])
        normalized_runs: List[TestRun] = []
        for run in self.test_runs:
            if isinstance(run, TestRun):
                normalized_runs.append(TestRun.from_dict(run.to_dict()))
            else:
                normalized_runs.append(TestRun.from_dict(run))
        self.test_runs = normalized_runs
        self.decision = _normalise_choice(self.decision, IDEA_DECISIONS, IDEA_DECISIONS[0])
        self.rationale = self.rationale.strip()
        self.next_actions = _clean_str_list(self.next_actions, limit=MAX_NEXT_ACTIONS)
        if not isinstance(self.best_of, IdeaBestOf):
            self.best_of = IdeaBestOf.from_dict(self.best_of)
        else:
            self.best_of = IdeaBestOf.from_dict(self.best_of.to_dict())
        if not isinstance(self.files, IdeaFiles):
            self.files = IdeaFiles.from_dict(self.files)
        else:
            self.files = IdeaFiles.from_dict(self.files.to_dict())
        self.version = max(1, _clamp_int(self.version, 1, 10_000, default=1))
        self.variant_of = self.variant_of.strip()
        self.changelog = _clean_str_list(self.changelog) or ["Création de l'idée."]
        if not isinstance(self.folder, Path):
            self.folder = Path(self.folder)
