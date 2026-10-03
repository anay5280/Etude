#!/usr/bin/env python3
"""End-to-end demo with NO microphone required.

Synthesizes a reference piece as audio, deliberately plays one note wrong, runs
the whole pipeline (pitch detection -> segmentation -> score following), and
prints the tutor's feedback. This proves the concept using only NumPy.

    python demo.py                # Twinkle, with a planted wrong note
    python demo.py ode_to_joy     # a different built-in piece
"""

from __future__ import annotations

import sys

import numpy as np

from piano_tutor.pieces import get_piece, PIECES
from piano_tutor.follower import ScoreFollower
from piano_tutor.session import PracticeSession, format_feedback, iter_frames
from piano_tutor.synth import render_notes
from piano_tutor.notes import name_to_midi, midi_to_name

SR = 22050
FRAME = 2048
HOP = 512


def plant_wrong_note(notes: list[str], index: int, semitone_shift: int) -> tuple[list[str], int]:
    """Return a copy of `notes` with one note shifted out of tune, plus its index."""
    played = list(notes)
    if 0 <= index < len(played):
        played[index] = midi_to_name(name_to_midi(played[index]) + semitone_shift)
    return played, index


def main() -> int:
    key = sys.argv[1] if len(sys.argv) > 1 else "twinkle"
    if key not in PIECES:
        print(f"Unknown piece '{key}'. Available: {', '.join(sorted(PIECES))}")
        return 2

    piece = get_piece(key)
    # Simulate a learner who nails the piece except for one flubbed note.
    wrong_index = min(4, len(piece.notes) - 1)
    played_notes, wrong_index = plant_wrong_note(piece.notes, wrong_index, semitone_shift=+1)

    print(f"Piece: {piece.title}")
    print(f"Simulated performance: correct except note {wrong_index + 1} "
          f"(played {played_notes[wrong_index]} instead of {piece.notes[wrong_index]}).\n")

    audio = render_notes(played_notes, SR)

    follower = ScoreFollower(piece.notes, advance_on_wrong=True)
    session = PracticeSession(follower=follower, sr=SR)

    feedbacks = []
    session.run_frames(
        iter_frames(audio, FRAME, HOP),
        on_feedback=lambda fb: (feedbacks.append(fb), print(format_feedback(fb)))[1],
    )

    total = len(piece.notes)
    print(f"\nSummary: {follower.correct_count}/{total} correct, "
          f"{follower.wrong_count} wrong.")
    # The demo is "working" if it detected exactly the planted mistake.
    wrong_positions = [fb.position for fb in feedbacks if fb.status == "wrong"]
    ok = wrong_positions == [wrong_index]
    print("Self-check:",
          "PASS — detected exactly the planted wrong note."
          if ok else f"reported wrong at positions {wrong_positions} (expected [{wrong_index}]).")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
