"""Built-in reference pieces (monophonic melodies).

Each piece is a list of note names in performance order. Durations are omitted
for the MVP — the score follower tracks *which* note you're on, not rhythm.
Repeated notes (e.g. two C4s in a row) are two separate entries.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Piece:
    key: str
    title: str
    notes: list[str] = field(default_factory=list)


PIECES: dict[str, Piece] = {
    "twinkle": Piece(
        key="twinkle",
        title="Twinkle, Twinkle, Little Star",
        notes=[
            "C4", "C4", "G4", "G4", "A4", "A4", "G4",
            "F4", "F4", "E4", "E4", "D4", "D4", "C4",
            "G4", "G4", "F4", "F4", "E4", "E4", "D4",
            "G4", "G4", "F4", "F4", "E4", "E4", "D4",
            "C4", "C4", "G4", "G4", "A4", "A4", "G4",
            "F4", "F4", "E4", "E4", "D4", "D4", "C4",
        ],
    ),
    "ode_to_joy": Piece(
        key="ode_to_joy",
        title="Ode to Joy (Beethoven)",
        notes=[
            "E4", "E4", "F4", "G4", "G4", "F4", "E4", "D4",
            "C4", "C4", "D4", "E4", "E4", "D4", "D4",
            "E4", "E4", "F4", "G4", "G4", "F4", "E4", "D4",
            "C4", "C4", "D4", "E4", "D4", "C4", "C4",
        ],
    ),
    "mary": Piece(
        key="mary",
        title="Mary Had a Little Lamb",
        notes=[
            "E4", "D4", "C4", "D4", "E4", "E4", "E4",
            "D4", "D4", "D4", "E4", "G4", "G4",
            "E4", "D4", "C4", "D4", "E4", "E4", "E4",
            "E4", "D4", "D4", "E4", "D4", "C4",
        ],
    ),
    "fur_elise": Piece(
        key="fur_elise",
        title="Für Elise — main theme (Beethoven)",
        notes=[
            "E5", "D#5", "E5", "D#5", "E5", "B4", "D5", "C5", "A4",
            "C4", "E4", "A4", "B4",
            "E4", "G#4", "B4", "C5",
            "E4", "E5", "D#5", "E5", "D#5", "E5", "B4", "D5", "C5", "A4",
        ],
    ),
}


def get_piece(key: str) -> Piece:
    try:
        return PIECES[key]
    except KeyError:
        available = ", ".join(sorted(PIECES))
        raise KeyError(f"unknown piece {key!r}; available: {available}") from None


@dataclass(frozen=True)
class ChordPiece:
    """A polyphonic reference piece: an ordered list of chords."""

    key: str
    title: str
    chords: list[list[str]] = field(default_factory=list)


# Kept in the C3–C5 register where the classical detector is reliable.
CHORD_PIECES: dict[str, ChordPiece] = {
    "canon": ChordPiece(
        key="canon",
        title="Pachelbel's Canon — chord progression (triads)",
        chords=[
            ["C4", "E4", "G4"],   # C
            ["G3", "B3", "D4"],   # G
            ["A3", "C4", "E4"],   # Am
            ["E4", "G4", "B4"],   # Em
            ["F3", "A3", "C4"],   # F
            ["C4", "E4", "G4"],   # C
            ["F3", "A3", "C4"],   # F
            ["G3", "B3", "D4"],   # G
        ],
    ),
    "pop_progression": ChordPiece(
        key="pop_progression",
        title="I–V–vi–IV progression in C (four chords)",
        chords=[
            ["C4", "E4", "G4"],   # C
            ["G3", "B3", "D4"],   # G
            ["A3", "C4", "E4"],   # Am
            ["F3", "A3", "C4"],   # F
        ],
    ),
}


def get_chord_piece(key: str) -> ChordPiece:
    try:
        return CHORD_PIECES[key]
    except KeyError:
        available = ", ".join(sorted(CHORD_PIECES))
        raise KeyError(f"unknown chord piece {key!r}; available: {available}") from None
