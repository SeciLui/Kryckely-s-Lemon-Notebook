"""Support services for long-running or external operations."""

from __future__ import annotations

import datetime as dt
import shutil
import subprocess
import wave
from pathlib import Path
from textwrap import indent
from typing import Iterable, Sequence, Tuple

from . import config
from .models import Idea
from .storage import read_text

try:  # Optional dependency loaded lazily to provide nicer error messages
    import sounddevice as sd  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - handled at runtime
    sd = None  # type: ignore[assignment]


class AudioRecordingError(RuntimeError):
    """Raised when an audio recording cannot be completed."""


def record_audio_to_file(
    destination: Path,
    duration_seconds: float,
    *,
    sample_rate: int = 44_100,
    channels: int = 1,
) -> Path:
    """Record audio from the default input and write a WAV file.

    Parameters
    ----------
    destination:
        Target file path where the recording should be written.
    duration_seconds:
        Maximum duration of the recording in seconds.
    sample_rate:
        Sampling rate used for the capture (defaults to 44.1 kHz).
    channels:
        Number of channels to record. ``1`` captures mono audio.

    Returns
    -------
    pathlib.Path
        The *destination* path once the file has been created.
    """

    if duration_seconds <= 0:
        raise AudioRecordingError("La durée doit être positive.")

    if sd is None:
        raise AudioRecordingError(
            "La bibliothèque sounddevice n'est pas installée."
        )

    frames = int(duration_seconds * sample_rate)

    try:
        recording = sd.rec(  # type: ignore[call-arg]
            frames,
            samplerate=sample_rate,
            channels=channels,
            dtype="int16",
        )
        sd.wait()  # type: ignore[call-arg]
    except Exception as exc:  # pragma: no cover - interacts with hardware
        raise AudioRecordingError(str(exc)) from exc

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(destination), "wb") as handle:
            handle.setnchannels(channels)
            handle.setsampwidth(2)  # 16-bit samples
            handle.setframerate(sample_rate)
            handle.writeframes(recording.tobytes())
    except Exception as exc:  # pragma: no cover - filesystem errors
        raise AudioRecordingError(
            f"Impossible d'écrire le fichier audio: {exc}"
        ) from exc

    return destination


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
