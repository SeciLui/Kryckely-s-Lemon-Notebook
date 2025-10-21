"""Support services for long-running or external operations."""

from __future__ import annotations

import datetime as dt
import shutil
import subprocess
import threading
import wave
from pathlib import Path
from textwrap import indent
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from . import config
from .models import Idea, IdeaContext, TestRun
from .storage import read_text

try:  # Optional dependency loaded lazily to provide nicer error messages
    import sounddevice as sd  # type: ignore[import-not-found]
except (ImportError, OSError):  # pragma: no cover - handled at runtime
    sd = None  # type: ignore[assignment]


class AudioRecordingError(RuntimeError):
    """Raised when an audio recording cannot be completed."""


def apply_analysis_payload(idea: Idea, payload: Dict[str, Any]) -> List[str]:
    """Merge a GPT analysis *payload* into *idea*.

    The expected schema is a JSON object structured as::

        {
            "idea": {
                "title": "…",
                "one_liner": "…",
                "category": "…",
                "tags": ["…"],
                "purpose": "…",
                "audience_hint": "…",
                "success_criteria": "…",
                "risks": ["…"],
                "contexts": [
                    {"label": "…", "channel": "IRL", "constraints": "…"},
                    …
                ],
                "test_instructions": "…",
                "next_test_context": "…",
                "priority": "low|med|high",
                "decision": "Keep|Tweak|Kill",
                "rationale": "…",
                "next_actions": ["…"],
                "best_of": {
                    "final_wording": "…",
                    "delivery_tips": ["…"],
                    "do_use_when": ["…"],
                    "avoid_when": ["…"],
                    "example_dialogues": ["…"]
                }
            },
            "tests": [
                {
                    "date": "2024-05-01",
                    "mode": "live (IRL)",
                    "context_ref": "…",
                    "partner_profile": "…",
                    "version_used": "A",
                    "outcome_score": 4,
                    "signals": {"smile": 1, "fluidite": 3},
                    "notes": "…",
                    "micro_tweaks": ["…"],
                    "evidence": ["…"],
                    "run_decision": "keep|tweak|kill"
                },
                …
            ]
        }

    The top-level ``"idea"`` object may also expose the recognised fields directly.
    Unknown or invalid fields are ignored and warnings describing the reason are
    returned. When no warnings are produced, the payload was applied fully.
    """

    warnings: List[str] = []

    if not isinstance(payload, dict):
        return ["Analyse JSON ignorée (objet attendu)."]

    def _first_string_from_sources(
        keys: Iterable[str],
        *sources: Dict[str, Any] | None,
        field_label: str,
    ) -> str | None:
        for source in sources:
            if not isinstance(source, dict):
                continue
            for key in keys:
                if key not in source:
                    continue
                value = source.get(key)
                if isinstance(value, str):
                    text = value.strip()
                    if text:
                        return text
                elif value is not None:
                    warnings.append(
                        f"Champ '{field_label}' ignoré (texte attendu)."
                    )
                    return None
        return None

    def _extract_list_from_sources(
        keys: Iterable[str],
        *sources: Dict[str, Any] | None,
        field_label: str,
    ) -> List[str] | None:
        for source in sources:
            if not isinstance(source, dict):
                continue
            for key in keys:
                if key not in source:
                    continue
                value = source.get(key)
                if isinstance(value, list):
                    return [
                        str(item).strip() for item in value if str(item).strip()
                    ]
                if isinstance(value, str):
                    return [
                        line.strip() for line in value.splitlines() if line.strip()
                    ]
                warnings.append(
                    f"Champ '{field_label}' ignoré (liste ou texte attendus)."
                )
                return None
        return None

    idea_section: Dict[str, Any] = {}
    if isinstance(payload.get("idea"), dict):
        idea_section = payload["idea"]  # type: ignore[assignment]
    elif isinstance(payload.get("idea_summary"), dict):
        idea_section = payload["idea_summary"]  # type: ignore[assignment]
    else:
        idea_section = {
            key: value
            for key, value in payload.items()
            if key not in {"tests", "test_runs", "experiments"}
        }

    best_of_section = idea_section.get("best_of")
    if not isinstance(best_of_section, dict):
        fallback = idea_section.get("bestOf")
        best_of_section = fallback if isinstance(fallback, dict) else None

    string_fields = {
        "title": ("title", "name"),
        "one_liner": ("one_liner", "one-liner", "pitch"),
        "category": ("category",),
        "purpose": ("purpose", "objectif"),
        "audience_hint": ("audience_hint", "audience", "cible"),
        "success_criteria": ("success_criteria", "success"),
        "test_instructions": ("test_instructions", "instructions"),
        "next_test_context": ("next_test_context", "next_context"),
        "priority": ("priority",),
        "decision": ("decision", "idea_decision"),
        "rationale": ("rationale", "analysis", "summary"),
        "variant_of": ("variant_of",),
    }

    for attribute, keys in string_fields.items():
        value = _first_string_from_sources(keys, idea_section, field_label=attribute)
        if value is not None:
            setattr(idea, attribute, value)

    best_of_string_fields = {
        "final_wording": ("final_wording", "best_of_final_wording"),
    }
    for attribute, keys in best_of_string_fields.items():
        value = _first_string_from_sources(
            keys,
            idea_section,
            best_of_section,
            field_label=f"best_of.{attribute}",
        )
        if value is not None:
            setattr(idea.best_of, attribute, value)

    list_fields = {
        "tags": ("tags",),
        "risks": ("risks", "dangers"),
        "next_actions": ("next_actions", "actions"),
        "changelog": ("changelog",),
    }

    for attribute, keys in list_fields.items():
        items = _extract_list_from_sources(
            keys, idea_section, field_label=attribute
        )
        if items is not None:
            setattr(idea, attribute, items)

    best_of_list_fields = {
        "delivery_tips": ("delivery_tips", "best_of_delivery_tips"),
        "do_use_when": ("do_use_when", "best_of_do_use_when"),
        "avoid_when": ("avoid_when", "best_of_avoid_when"),
        "example_dialogues": (
            "example_dialogues",
            "best_of_example_dialogues",
        ),
    }

    for attribute, keys in best_of_list_fields.items():
        items = _extract_list_from_sources(
            keys,
            idea_section,
            best_of_section,
            field_label=f"best_of.{attribute}",
        )
        if items is not None:
            setattr(idea.best_of, attribute, items)

    contexts_payload = None
    for key in ("contexts", "contextes"):
        if key in idea_section:
            contexts_payload = idea_section.get(key)
            break
    if contexts_payload is not None:
        if isinstance(contexts_payload, list):
            contexts: List[IdeaContext] = []
            for entry in contexts_payload:
                if isinstance(entry, dict):
                    contexts.append(IdeaContext.from_dict(entry))
                else:
                    warnings.append(
                        "Contexte ignoré (dictionnaire attendu)."
                    )
            if contexts:
                idea.contexts = contexts
        else:
            warnings.append("Champ 'contexts' ignoré (liste attendue).")

    tests_payload = None
    for key in ("tests", "test_runs", "experiments"):
        if key in payload:
            tests_payload = payload.get(key)
            break
    if tests_payload is None:
        for key in ("tests", "test_runs", "experiments"):
            if key in idea_section:
                tests_payload = idea_section.get(key)
                break
    if tests_payload is not None:
        if isinstance(tests_payload, list):
            runs: List[TestRun] = []
            for entry in tests_payload:
                if not isinstance(entry, dict):
                    warnings.append(
                        "Exécution de test ignorée (objet attendu)."
                    )
                    continue
                run_payload: Dict[str, Any] = {
                    "date": entry.get("date") or entry.get("when"),
                    "mode": entry.get("mode"),
                    "context_ref": entry.get("context_ref")
                    or entry.get("context"),
                    "partner_profile": entry.get("partner_profile")
                    or entry.get("partner"),
                    "version_used": entry.get("version_used")
                    or entry.get("version"),
                    "outcome_score": entry.get("outcome_score")
                    or entry.get("score"),
                    "signals": entry.get("signals"),
                    "notes": entry.get("notes"),
                    "evidence": entry.get("evidence") or [],
                    "micro_tweaks": entry.get("micro_tweaks")
                    or entry.get("tweaks")
                    or [],
                    "run_decision": entry.get("run_decision")
                    or entry.get("decision"),
                }
                runs.append(TestRun.from_dict(run_payload))
            if runs:
                idea.test_runs = runs
        else:
            warnings.append("Section 'tests' ignorée (liste attendue).")

    return warnings


def record_audio_until_stop(
    destination: Path,
    stop_signal: threading.Event,
    *,
    sample_rate: int = 44_100,
    channels: int = 1,
    chunk_frames: int = 1_024,
) -> Path:
    """Record audio until *stop_signal* is set and persist it as a WAV file."""

    if sd is None:
        raise AudioRecordingError(
            "La bibliothèque sounddevice n'est pas installée."
        )

    if chunk_frames <= 0:
        raise AudioRecordingError("La taille des blocs d'enregistrement doit être positive.")

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover - filesystem errors
        raise AudioRecordingError(
            f"Impossible de préparer le dossier d'enregistrement: {exc}"
        ) from exc

    try:
        with wave.open(str(destination), "wb") as handle:
            handle.setnchannels(channels)
            handle.setsampwidth(2)  # 16-bit samples
            handle.setframerate(sample_rate)

            try:
                with sd.InputStream(  # type: ignore[attr-defined]
                    samplerate=sample_rate,
                    channels=channels,
                    dtype="int16",
                ) as stream:
                    while not stop_signal.is_set():
                        data, _ = stream.read(chunk_frames)
                        handle.writeframes(data.tobytes())
            except Exception as exc:  # pragma: no cover - interacts with hardware
                raise AudioRecordingError(str(exc)) from exc
    except AudioRecordingError:
        if destination.exists():
            try:
                destination.unlink()
            except OSError:
                pass
        raise
    except Exception as exc:  # pragma: no cover - filesystem errors
        if destination.exists():
            try:
                destination.unlink()
            except OSError:
                pass
        raise AudioRecordingError(
            f"Impossible d'écrire le fichier audio: {exc}"
        ) from exc

    return destination


def record_audio_to_file(
    destination: Path,
    duration_seconds: float,
    *,
    sample_rate: int = 44_100,
    channels: int = 1,
    chunk_frames: int = 1_024,
) -> Path:
    """Record audio for a fixed duration and persist it as a WAV file."""

    if duration_seconds <= 0:
        raise AudioRecordingError("La durée doit être positive.")

    stop_signal = threading.Event()
    timer = threading.Timer(duration_seconds, stop_signal.set)
    timer.start()
    try:
        return record_audio_until_stop(
            destination,
            stop_signal,
            sample_rate=sample_rate,
            channels=channels,
            chunk_frames=chunk_frames,
        )
    finally:
        timer.cancel()


def run_subprocess(command: Sequence[str]) -> Tuple[int, str, str]:
    """Execute *command* and return ``(returncode, stdout, stderr)``."""

    try:
        process = subprocess.Popen(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
    except FileNotFoundError as exc:
        return 127, "", f"Commande introuvable: {exc.filename}"
    except Exception as exc:  # pragma: no cover - defensive fallback
        return 1, "", str(exc)

    stdout, stderr = process.communicate()
    return process.returncode, stdout, stderr


def transcribe_audio(audio_path: Path, transcript_out: Path) -> Tuple[bool, str]:
    """Transcribe *audio_path* using the configured CLI template."""

    command = [part.format(input=str(audio_path), output=str(transcript_out)) for part in config.TRANSCRIBE_COMMAND_TEMPLATE]
    code, stdout, stderr = run_subprocess(command)
    if code != 0:
        message = stderr.strip() or stdout.strip() or "Erreur de transcription."
        return False, message

    if not transcript_out.exists():
        # Some tools create the transcript next to the audio file. Try to recover it.
        for candidate in _candidate_transcripts(audio_path):
            shutil.copy(candidate, transcript_out)
            if transcript_out.exists():
                break

    if transcript_out.exists():
        message = stdout.strip() or "Transcription terminée."
        return True, message
    return False, f"Impossible de trouver {transcript_out}"


def _candidate_transcripts(audio_path: Path) -> Iterable[Path]:
    """Yield possible transcript files created next to *audio_path*."""

    directory = audio_path.parent
    if not directory.exists():
        return []
    return (
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() == ".txt"
    )


def _parse_test_date(raw: str) -> dt.datetime:
    """Return a datetime usable for sorting test runs."""

    if not raw:
        return dt.datetime.min
    for fmt in (None, "%Y-%m-%d", "%d/%m/%Y"):
        try:
            if fmt is None:
                return dt.datetime.fromisoformat(raw)
            return dt.datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return dt.datetime.min


def _format_list(items: Iterable[str], *, bullet: str = "- ") -> str:
    """Return a bullet list joined with new lines or a placeholder."""

    cleaned = [str(item).strip() for item in items if str(item).strip()]
    return "\n".join(f"{bullet}{entry}" for entry in cleaned) if cleaned else "—"


def build_analysis_prompt(idea: Idea) -> str:
    """Return a rich prompt aggregating the context of *idea* for analysis."""

    transcript = read_text(idea.transcript_path()).strip()
    analysis = read_text(idea.analysis_path()).strip()

    contexts_lines = []
    for context in idea.contexts:
        details = [context.label or "(sans label)", context.channel]
        if context.constraints:
            details.append(context.constraints)
        contexts_lines.append(" | ".join(details))
    contexts_block = _format_list(contexts_lines)

    risks_block = _format_list(idea.risks)
    next_actions_block = _format_list(idea.next_actions)
    changelog_block = _format_list(idea.changelog)

    best_of_lines = []
    if idea.best_of.final_wording:
        best_of_lines.append(f"Formulation finale: {idea.best_of.final_wording}")
    if idea.best_of.delivery_tips:
        best_of_lines.append(
            "Delivery tips:\n" + indent(_format_list(idea.best_of.delivery_tips).replace("—", ""), "  ")
        )
    if idea.best_of.do_use_when:
        best_of_lines.append(
            "À utiliser quand:\n" + indent(_format_list(idea.best_of.do_use_when).replace("—", ""), "  ")
        )
    if idea.best_of.avoid_when:
        best_of_lines.append(
            "À éviter quand:\n" + indent(_format_list(idea.best_of.avoid_when).replace("—", ""), "  ")
        )
    if idea.best_of.example_dialogues:
        best_of_lines.append(
            "Dialogues exemple:\n"
            + indent(_format_list(idea.best_of.example_dialogues).replace("—", ""), "  ")
        )
    best_of_block = "\n".join(line for line in best_of_lines if line.strip()) or "—"

    tests_sorted = sorted(idea.test_runs, key=lambda run: _parse_test_date(run.date), reverse=True)
    tests_block_lines = []
    for run in tests_sorted[:5]:
        signals = run.signals
        header = (
            f"- {run.date or '—'} | mode={run.mode} | contexte={run.context_ref or '—'} | "
            f"profil={run.partner_profile or '—'} | version={run.version_used or '—'} | "
            f"score={run.outcome_score}/5 | décision={run.run_decision}"
        )
        signals_text = (
            f"Signaux: 😊{signals.smile} 😂{signals.laugh} ↩️{signals.relance} "
            f"🎚️{signals.fluidite} 😬{signals.awkward}"
        )
        extra_details = []
        if run.notes:
            extra_details.append(f"Notes: {run.notes}")
        if run.micro_tweaks:
            extra_details.append("Micro-tweaks: " + ", ".join(run.micro_tweaks))
        if run.evidence:
            extra_details.append("Evidence: " + ", ".join(run.evidence))
        block = header + "\n  " + signals_text
        if extra_details:
            block += "\n  " + "\n  ".join(extra_details)
        tests_block_lines.append(block)
    tests_block = "\n".join(tests_block_lines) if tests_block_lines else "Aucun test enregistré."

    transcript_block = transcript or "Aucune transcription disponible."
    analysis_block = analysis or "Aucune analyse précédente."

    json_template = """{{
  "summary": "",
  "decision": "keep|tweak|kill",
  "confidence": "low|medium|high",
  "key_strengths": [],
  "key_risks": [],
  "recommended_actions": [],
  "suggested_tests": []
}}"""

    prompt = (
        "SYSTEM:\n"
        "Tu es un expert conversationnel qui aide à analyser des idées de conversations.\n"
        "Fais une lecture critique, identifie les risques et propose des actions concrètes.\n\n"
        "FORMAT:\n"
        "Réponds UNIQUEMENT avec un JSON valide correspondant strictement au modèle ci-dessous:\n"
        f"{json_template}\n\n"
        "USER:\n"
        "Analyse l'idée suivante et prépare des recommandations actionnables.\n\n"
        f"Titre: {idea.title}\n"
        f"Statut: {idea.status} | Priorité: {idea.priority} | Décision actuelle: {idea.decision}\n"
        f"One-liner: {idea.one_liner or '—'}\n"
        f"Catégorie: {idea.category or '—'}\n"
        f"Tags: {', '.join(idea.tags) if idea.tags else '—'}\n"
        f"Intention: {idea.purpose or '—'}\n"
        f"Audience: {idea.audience_hint or '—'}\n"
        f"Succès attendu: {idea.success_criteria or '—'}\n\n"
        "Risques identifiés:\n"
        f"{risks_block}\n\n"
        "Contexts idéaux:\n"
        f"{contexts_block}\n\n"
        "Prochain contexte de test: "
        f"{idea.next_test_context or '—'}\n\n"
        "Plan de test:\n"
        f"{idea.test_instructions or '—'}\n\n"
        "Tests récents:\n"
        f"{tests_block}\n\n"
        "Synthèse précédente:\n"
        f"{analysis_block}\n\n"
        "Transcription récente:\n"
        f"{transcript_block}\n\n"
        "Best-of actuel:\n"
        f"{best_of_block}\n\n"
        "Prochaines actions envisagées:\n"
        f"{next_actions_block}\n\n"
        "Changelog:\n"
        f"{changelog_block}\n"
    )

    return prompt
