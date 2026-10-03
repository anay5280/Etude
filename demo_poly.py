#!/usr/bin/env python3
"""End-to-end POLYPHONIC (chord) demo — no microphone required.

Synthesizes a chord progression, deliberately flubs one note inside one chord,
runs the full polyphonic pipeline (chord detection -> segmentation -> chord
following), and prints the tutor's feedback.

    python demo_poly.py                  # Canon progression
    python demo_poly.py pop_progression
"""

from __future__ import annotations

import sys

from piano_tutor.pieces import get_chord_piece, CHORD_PIECES
from piano_tutor.follower import PolyScoreFollower
from piano_tutor.session import PolyPracticeSession, format_feedback, iter_frames
from piano_tutor.synth import render_chords
from piano_tutor.notes import name_to_midi, midi_to_name

SR = 22050
# Chords need more low-frequency resolution than a single melody note, so use a
# larger analysis frame than the monophonic path.
FRAME = 8192
HOP = 2048


def main() -> int:
    key = sys.argv[1] if len(sys.argv) > 1 else "canon"
    if key not in CHORD_PIECES:
        print(f"Unknown piece '{key}'. Available: {', '.join(sorted(CHORD_PIECES))}")
        return 2

    piece = get_chord_piece(key)

    # Flub one note inside one chord (shift it up a semitone).
    wrong_chord = min(2, len(piece.chords) - 1)
    played = [list(ch) for ch in piece.chords]
    original = played[wrong_chord][-1]
    played[wrong_chord][-1] = midi_to_name(name_to_midi(original) + 1)

    print(f"Piece: {piece.title}")
    print(f"Simulated performance: chord {wrong_chord + 1} has a wrong note "
          f"({played[wrong_chord][-1]} instead of {original}).\n")

    audio = render_chords(played, SR, chord_dur=0.7, gap_dur=0.2)

    follower = PolyScoreFollower(piece.chords, advance_on_wrong=True)
    session = PolyPracticeSession(follower=follower, sr=SR)

    feedbacks = []
    session.run_frames(
        iter_frames(audio, FRAME, HOP),
        on_feedback=lambda fb: (feedbacks.append(fb), print(format_feedback(fb)))[1],
    )

    total = len(piece.chords)
    print(f"\nSummary: {follower.correct_count}/{total} chords correct, "
          f"{follower.wrong_count} wrong.")
    wrong_positions = [fb.position for fb in feedbacks if fb.status == "wrong"]
    ok = wrong_positions == [wrong_chord]
    print("Self-check:",
          "PASS — detected exactly the planted wrong chord."
          if ok else f"reported wrong at {wrong_positions} (expected [{wrong_chord}]).")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
