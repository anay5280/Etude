#!/usr/bin/env python3
"""Analyze a recording with the NEURAL model (Spotify basic-pitch).

This is the accurate, production path for real piano recordings. It transcribes
the whole WAV with a neural network, groups the notes into chords/onsets, and
follows them against a reference piece.

    .venv310/bin/python analyze_neural.py recording.wav canon
    .venv310/bin/python analyze_neural.py recording.wav twinkle --raw

Requires basic-pitch (see piano_tutor/neural.py for install notes). Run it with
the Python that has basic-pitch installed (e.g. the .venv310 environment).
"""

from __future__ import annotations

import argparse
import sys
import wave

import numpy as np

from piano_tutor.pieces import get_piece, get_chord_piece, PIECES, CHORD_PIECES
from piano_tutor.follower import ScoreFollower, PolyScoreFollower
from piano_tutor.session import format_feedback
from piano_tutor.neural import (
    NEURAL_AVAILABLE, NeuralUnavailableError,
    transcribe_wav, group_into_onsets, to_note_stream,
)


def load_wav_meta(path: str) -> float:
    with wave.open(path, "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def main() -> int:
    parser = argparse.ArgumentParser(description="Neural (basic-pitch) recording analysis.")
    parser.add_argument("wav", help="path to a WAV recording")
    parser.add_argument("piece", nargs="?", default="twinkle")
    parser.add_argument("--raw", action="store_true",
                        help="just print the transcription, don't score against a piece")
    args = parser.parse_args()

    if not NEURAL_AVAILABLE:
        print(NeuralUnavailableError())
        return 1

    print(f"Transcribing {args.wav} with basic-pitch (neural)...")
    try:
        events = transcribe_wav(args.wav)
    except FileNotFoundError:
        print(f"File not found: {args.wav}")
        return 2

    onsets = group_into_onsets(events)
    print(f"Duration {load_wav_meta(args.wav):.1f}s — "
          f"{len(events)} raw notes, {len(onsets)} onsets after grouping.\n")

    if args.raw:
        for o in onsets:
            print(f"  t={o.time:5.2f}s  {' '.join(o.names)}")
        return 0

    is_chords = args.piece in CHORD_PIECES
    if args.piece not in PIECES and not is_chords:
        print(f"Unknown piece '{args.piece}'. "
              f"Melodies: {', '.join(sorted(PIECES))}. "
              f"Chords: {', '.join(sorted(CHORD_PIECES))}.")
        return 2

    if is_chords:
        piece = get_chord_piece(args.piece)
        follower = PolyScoreFollower(piece.chords, advance_on_wrong=True)
        print(f"Piece: {piece.title}\n")
        for o in onsets:
            fb = follower.on_chord(o.midis)
            print(format_feedback(fb))
            if follower.finished:
                break
        total = len(piece.chords)
        unit = "chords"
    else:
        piece = get_piece(args.piece)
        follower = ScoreFollower(piece.notes, advance_on_wrong=True)
        print(f"Piece: {piece.title}\n")
        for midi in to_note_stream(onsets):
            fb = follower.on_note(midi)
            print(format_feedback(fb))
            if follower.finished:
                break
        total = len(piece.notes)
        unit = "notes"

    print(f"\nSummary: {follower.correct_count}/{total} {unit} correct, "
          f"{follower.wrong_count} wrong.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
