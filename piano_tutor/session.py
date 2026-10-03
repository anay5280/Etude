"""Glue that runs an audio stream through detection, segmentation and
following — shared by the live-mic loop, the file analyzer and the demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import numpy as np

from .follower import (
    ChordFeedback, ChordSegmenter, Feedback, NoteSegmenter,
    PolyScoreFollower, ScoreFollower,
)
from .pitch import detect_f0
from .poly import detect_chord, midi_set


# ANSI colors for terminal feedback (harmless if the terminal ignores them).
_GREEN = "\033[92m"
_RED = "\033[91m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def format_feedback(fb, color: bool = True) -> str:
    """Format either monophonic Feedback or polyphonic ChordFeedback."""
    tag = {"correct": "✓", "wrong": "✗", "done": "★"}.get(fb.status, "?")
    body = f"[{fb.position + 1}/{fb.total}] {tag} {fb.message}"
    if not color:
        return body
    c = {"correct": _GREEN, "wrong": _RED, "done": _GREEN}.get(fb.status, "")
    return f"{c}{body}{_RESET}"


@dataclass
class PracticeSession:
    """Runs frames through the full pipeline for one reference piece."""

    follower: ScoreFollower
    sr: int
    segmenter: NoteSegmenter = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.segmenter is None:
            self.segmenter = NoteSegmenter()

    def process_frame(self, frame: np.ndarray) -> Feedback | None:
        """Feed one audio frame; return Feedback when a note is committed."""
        result = detect_f0(frame, self.sr)
        midi = result.pitch.midi if result.pitch is not None else None
        committed = self.segmenter.feed(midi)
        if committed is None:
            return None
        return self.follower.on_note(committed)

    def run_frames(
        self,
        frames: Iterable[np.ndarray],
        on_feedback: Callable[[Feedback], None],
    ) -> None:
        """Process an iterable of frames, calling `on_feedback` per committed note."""
        for frame in frames:
            fb = self.process_frame(frame)
            if fb is not None:
                on_feedback(fb)
                if fb.status == "done" or self.follower.finished:
                    break


@dataclass
class PolyPracticeSession:
    """Polyphonic counterpart of PracticeSession — detects chords per frame."""

    follower: PolyScoreFollower
    sr: int
    segmenter: ChordSegmenter = None  # type: ignore[assignment]
    max_notes: int = 6

    def __post_init__(self):
        if self.segmenter is None:
            self.segmenter = ChordSegmenter()

    def process_frame(self, frame: np.ndarray) -> ChordFeedback | None:
        pitches = detect_chord(frame, self.sr, max_notes=self.max_notes)
        committed = self.segmenter.feed(midi_set(pitches))
        if committed is None:
            return None
        return self.follower.on_chord(committed)

    def run_frames(self, frames, on_feedback: Callable[[ChordFeedback], None]) -> None:
        for frame in frames:
            fb = self.process_frame(frame)
            if fb is not None:
                on_feedback(fb)
                if fb.status == "done" or self.follower.finished:
                    break


def iter_frames(signal: np.ndarray, frame_size: int, hop: int):
    """Yield overlapping frames from a 1-D signal."""
    n = len(signal)
    i = 0
    while i + frame_size <= n:
        yield signal[i:i + frame_size]
        i += hop
