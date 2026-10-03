"""Neural transcription via Spotify's basic-pitch — the accurate, production
path for real recordings.

Unlike the classical detectors (`pitch.py`, `poly.py`) which run per-frame for
low-latency *live* feedback, basic-pitch is a neural model that transcribes a
whole recording into time-stamped note events. It is far more robust on real
piano audio (timbre, reverb, pedal). The trade-off is that it's offline, so we
use it to analyse recordings rather than for real-time monitoring.

basic-pitch is an optional dependency and needs a neural runtime (ONNX /
CoreML / TensorFlow), which does not support the newest Python versions. Install
it in a compatible environment (Python 3.10 works well):

    python3.10 -m venv .venv310
    .venv310/bin/pip install "basic-pitch[onnx]" numpy

Everything else in the project runs without any of this.
"""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import wave
from dataclasses import dataclass

import numpy as np

from .notes import midi_to_name

# Detect availability without importing the heavy model at import time.
try:
    import basic_pitch  # noqa: F401
    NEURAL_AVAILABLE = True
except Exception:  # noqa: BLE001
    NEURAL_AVAILABLE = False


class NeuralUnavailableError(RuntimeError):
    """Raised when the neural backend isn't installed."""

    def __init__(self) -> None:
        super().__init__(
            "basic-pitch is not installed in this environment.\n"
            "Install it under a compatible Python (3.10 recommended):\n"
            '    python3.10 -m venv .venv310\n'
            '    .venv310/bin/pip install "basic-pitch[onnx]" numpy\n'
            "then run this script with .venv310/bin/python."
        )


@dataclass(frozen=True)
class NoteEvent:
    """One transcribed note."""

    start: float       # seconds
    end: float         # seconds
    midi: int
    amplitude: float

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def name(self) -> str:
        return midi_to_name(self.midi)


@dataclass(frozen=True)
class Onset:
    """A group of notes that begin together — a chord (or a single melody note)."""

    time: float
    midis: frozenset[int]

    @property
    def names(self) -> list[str]:
        return [midi_to_name(m) for m in sorted(self.midis)]


def _write_temp_wav(audio: np.ndarray, sr: int) -> str:
    pcm = (np.clip(np.asarray(audio, dtype=np.float64), -1.0, 1.0) * 32767).astype("<i2")
    fd, path = tempfile.mkstemp(suffix=".wav", dir=tempfile.gettempdir())
    os.close(fd)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


def transcribe_wav(
    path: str,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
    minimum_note_length_ms: float = 120.0,
) -> list[NoteEvent]:
    """Run basic-pitch on a WAV file and return note events sorted by start time."""
    if not NEURAL_AVAILABLE:
        raise NeuralUnavailableError()

    from basic_pitch.inference import predict

    # basic-pitch prints progress/debug to stdout; keep our output clean.
    with contextlib.redirect_stdout(io.StringIO()):
        _model_output, _midi_data, note_events = predict(
            path,
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
            minimum_note_length=minimum_note_length_ms,
        )

    events = [
        NoteEvent(start=float(e[0]), end=float(e[1]),
                  midi=int(e[2]), amplitude=float(e[3]))
        for e in note_events
    ]
    events.sort(key=lambda ev: (ev.start, ev.midi))
    return events


def transcribe_array(audio: np.ndarray, sr: int, **kwargs) -> list[NoteEvent]:
    """Transcribe an in-memory audio array (writes a temporary WAV for the model)."""
    path = _write_temp_wav(audio, sr)
    try:
        return transcribe_wav(path, **kwargs)
    finally:
        with contextlib.suppress(OSError):
            os.remove(path)


def group_into_onsets(
    events: list[NoteEvent],
    onset_tolerance: float = 0.12,
    min_amplitude: float = 0.3,
    duration_fraction: float = 0.4,
) -> list[Onset]:
    """Cluster note events that start together into chords, dropping ghost notes.

    Notes whose start times fall within `onset_tolerance` seconds form one
    onset. Within each onset, short spurious notes are removed: a note is kept
    only if its duration is at least `duration_fraction` of the group's longest
    note (basic-pitch's false positives are typically brief), and its amplitude
    clears `min_amplitude`.
    """
    if not events:
        return []

    groups: list[list[NoteEvent]] = []
    current: list[NoteEvent] = [events[0]]
    group_start = events[0].start
    for ev in events[1:]:
        if ev.start - group_start <= onset_tolerance:
            current.append(ev)
        else:
            groups.append(current)
            current = [ev]
            group_start = ev.start
    groups.append(current)

    onsets: list[Onset] = []
    for group in groups:
        longest = max(ev.duration for ev in group)
        kept = {
            ev.midi
            for ev in group
            if ev.duration >= duration_fraction * longest
            and ev.amplitude >= min_amplitude
        }
        if kept:
            onsets.append(Onset(time=min(ev.start for ev in group),
                                midis=frozenset(kept)))
    return onsets


def to_note_stream(onsets: list[Onset]) -> list[int]:
    """Collapse onsets to a single-note-per-onset melody (lowest of each onset).

    Useful for following a monophonic reference against a possibly noisy
    transcription — takes the most likely melody note.
    """
    return [min(o.midis) for o in onsets if o.midis]
