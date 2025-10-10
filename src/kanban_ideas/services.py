"""Support services for long-running or external operations."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Sequence, Tuple

from . import config


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
