"""Tiny audio synthesizer used by the demo and tests.

Generates simple tones for note sequences so the full pipeline can be
exercised without a microphone or audio files.
"""

from __future__ import annotations

import numpy as np

from .notes import name_to_midi, midi_to_freq


def tone(freq: float, duration: float, sr: int, amplitude: float = 0.3) -> np.ndarray:
    """A decaying tone with a few harmonics — vaguely piano-like, enough to
    give the pitch detector a clear fundamental."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    wave = (
        1.0 * np.sin(2 * np.pi * freq * t)
        + 0.35 * np.sin(2 * np.pi * 2 * freq * t)
        + 0.15 * np.sin(2 * np.pi * 3 * freq * t)
    )
    envelope = np.exp(-3.0 * t / max(duration, 1e-6))
    return (amplitude * wave * envelope).astype(np.float64)


def silence(duration: float, sr: int) -> np.ndarray:
    return np.zeros(int(sr * duration), dtype=np.float64)


def render_notes(
    note_names: list[str],
    sr: int,
    note_dur: float = 0.4,
    gap_dur: float = 0.12,
) -> np.ndarray:
    """Render a sequence of note names to one audio signal, with gaps between."""
    parts: list[np.ndarray] = []
    for name in note_names:
        freq = midi_to_freq(name_to_midi(name))
        parts.append(tone(freq, note_dur, sr))
        parts.append(silence(gap_dur, sr))
    return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float64)


def chord_tone(note_names: list[str], duration: float, sr: int,
               amplitude: float = 0.3) -> np.ndarray:
    """Sum several note tones into one chord, scaled to avoid clipping."""
    if not note_names:
        return silence(duration, sr)
    mix = np.zeros(int(sr * duration), dtype=np.float64)
    for name in note_names:
        freq = midi_to_freq(name_to_midi(name))
        mix += tone(freq, duration, sr, amplitude=amplitude)
    return mix / len(note_names)


def render_chords(
    chords: list[list[str]],
    sr: int,
    chord_dur: float = 0.5,
    gap_dur: float = 0.15,
) -> np.ndarray:
    """Render a sequence of chords (each a list of note names) to one signal."""
    parts: list[np.ndarray] = []
    for chord in chords:
        parts.append(chord_tone(chord, chord_dur, sr))
        parts.append(silence(gap_dur, sr))
    return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float64)
