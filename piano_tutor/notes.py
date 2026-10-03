"""Conversions between frequency, MIDI note number, and note names.

Uses the standard equal-tempered scale with A4 = 440 Hz = MIDI 69.
Middle C (C4) = MIDI 60. Note names use sharps (C#, D#, ...).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

A4_FREQ = 440.0
A4_MIDI = 69

# Index 0..11 map to the twelve pitch classes starting at C.
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Which pitch classes are black keys on a piano (the sharps).
_BLACK_KEYS = {1, 3, 6, 8, 10}


def freq_to_midi(freq: float) -> float:
    """Frequency in Hz -> (fractional) MIDI note number."""
    if freq <= 0:
        raise ValueError("frequency must be positive")
    return A4_MIDI + 12.0 * math.log2(freq / A4_FREQ)


def midi_to_freq(midi: float) -> float:
    """MIDI note number -> frequency in Hz."""
    return A4_FREQ * (2.0 ** ((midi - A4_MIDI) / 12.0))


def midi_to_name(midi: int) -> str:
    """Rounded MIDI note number -> name with octave, e.g. 60 -> 'C4'."""
    midi = int(round(midi))
    pitch_class = midi % 12
    octave = midi // 12 - 1
    return f"{NOTE_NAMES[pitch_class]}{octave}"


def name_to_midi(name: str) -> int:
    """Note name like 'C4' or 'F#3' -> MIDI note number."""
    name = name.strip()
    # Split trailing octave (may be negative, though rare for piano).
    i = 0
    while i < len(name) and not (name[i].isdigit() or name[i] == "-"):
        i += 1
    pitch = name[:i]
    octave_str = name[i:]
    if pitch not in NOTE_NAMES:
        raise ValueError(f"unknown note name: {name!r}")
    if octave_str == "":
        raise ValueError(f"missing octave in note name: {name!r}")
    octave = int(octave_str)
    return NOTE_NAMES.index(pitch) + (octave + 1) * 12


def is_black_key(midi: int) -> bool:
    """True if the note is a black key (sharp) on the piano keyboard."""
    return (int(round(midi)) % 12) in _BLACK_KEYS


def cents_off(freq: float, midi: int) -> float:
    """How far `freq` is from the exact pitch of `midi`, in cents.

    Positive means sharp (too high), negative means flat (too low).
    100 cents = one semitone.
    """
    return 1200.0 * math.log2(freq / midi_to_freq(midi))


@dataclass(frozen=True)
class Pitch:
    """A detected pitch resolved to the nearest piano note."""

    freq: float          # detected fundamental frequency, Hz
    midi: int            # nearest MIDI note number
    name: str            # e.g. "G4"
    cents: float         # deviation from the nearest note, in cents

    @property
    def in_tune(self) -> bool:
        return abs(self.cents) <= 25.0


def nearest_note(freq: float) -> Pitch:
    """Resolve a frequency to the nearest equal-tempered piano note."""
    midi_float = freq_to_midi(freq)
    midi = int(round(midi_float))
    return Pitch(
        freq=freq,
        midi=midi,
        name=midi_to_name(midi),
        cents=cents_off(freq, midi),
    )
