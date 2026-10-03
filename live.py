#!/usr/bin/env python3
"""Real-time practice from your microphone.

Play the chosen piece on a real piano (or keyboard) into your mic; the tutor
prints a line each time it commits a note, flagging wrong notes and how to fix
them.

    python live.py                 # defaults to Twinkle
    python live.py fur_elise
    python live.py --list

Requires the `sounddevice` package (see requirements.txt). Everything else in
the project runs without it.
"""

from __future__ import annotations

import argparse
import queue
import sys

import numpy as np

from piano_tutor.pieces import get_piece, get_chord_piece, PIECES, CHORD_PIECES
from piano_tutor.follower import ScoreFollower, PolyScoreFollower
from piano_tutor.session import PracticeSession, PolyPracticeSession, format_feedback

SR = 22050
# Monophonic melodies use a small frame for low latency; chords need a larger
# frame for enough low-frequency resolution.
MONO_FRAME, MONO_HOP = 2048, 512
POLY_FRAME, POLY_HOP = 8192, 2048


def list_pieces() -> None:
    print("Melody pieces (one note at a time):")
    for key, piece in PIECES.items():
        print(f"  {key:16s} {piece.title} ({len(piece.notes)} notes)")
    print("\nChord pieces (polyphonic):")
    for key, piece in CHORD_PIECES.items():
        print(f"  {key:16s} {piece.title} ({len(piece.chords)} chords)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Real-time piano note tutor.")
    parser.add_argument("piece", nargs="?", default="twinkle")
    parser.add_argument("--list", action="store_true", help="list pieces and exit")
    args = parser.parse_args()

    if args.list:
        list_pieces()
        return 0

    is_chords = args.piece in CHORD_PIECES
    if args.piece not in PIECES and not is_chords:
        print(f"Unknown piece '{args.piece}'.")
        list_pieces()
        return 2

    try:
        import sounddevice as sd
    except Exception as exc:  # noqa: BLE001
        print("The live microphone mode needs the 'sounddevice' package.")
        print(f"  pip install sounddevice   (import failed: {exc})")
        print("You can still run the no-mic demos:  python demo.py / demo_poly.py")
        return 1

    if is_chords:
        piece = get_chord_piece(args.piece)
        follower = PolyScoreFollower(piece.chords, advance_on_wrong=True)
        session = PolyPracticeSession(follower=follower, sr=SR)
        frame_size, hop, total, unit = POLY_FRAME, POLY_HOP, len(piece.chords), "chords"
        print(f"Piece: {piece.title} — {total} chords")
        print("Listening... play each chord. Ctrl+C to stop.\n")
    else:
        piece = get_piece(args.piece)
        follower = ScoreFollower(piece.notes, advance_on_wrong=False)
        session = PracticeSession(follower=follower, sr=SR)
        frame_size, hop, total, unit = MONO_FRAME, MONO_HOP, len(piece.notes), "notes"
        print(f"Piece: {piece.title} — {total} notes")
        print("Listening... play the melody. Ctrl+C to stop.\n")

    audio_q: "queue.Queue[np.ndarray]" = queue.Queue()

    def callback(indata, frames, time_info, status):  # noqa: ANN001
        if status:
            print(status, file=sys.stderr)
        audio_q.put(indata[:, 0].copy())

    buffer = np.zeros(0, dtype=np.float64)
    try:
        with sd.InputStream(samplerate=SR, channels=1, dtype="float32",
                            blocksize=hop, callback=callback):
            while not follower.finished:
                chunk = audio_q.get()
                buffer = np.concatenate([buffer, chunk.astype(np.float64)])
                while len(buffer) >= frame_size:
                    frame = buffer[:frame_size]
                    buffer = buffer[hop:]
                    fb = session.process_frame(frame)
                    if fb is not None:
                        print(format_feedback(fb))
    except KeyboardInterrupt:
        print("\nStopped.")

    print(f"\nSummary: {follower.correct_count}/{total} {unit} correct, "
          f"{follower.wrong_count} wrong.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
