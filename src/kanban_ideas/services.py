"""Support services for long-running or external operations."""

from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path
from typing import Iterable, Sequence, Tuple

from . import config

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
