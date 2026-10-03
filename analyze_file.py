#!/usr/bin/env python3
"""Analyze a recorded WAV file against a reference piece (offline, no mic).

    python analyze_file.py path/to/recording.wav twinkle

Accepts 16-bit PCM mono/stereo WAV via the standard-library `wave` module, so
no extra audio dependencies are needed.
"""

from __future__ import annotations

import sys
import wave

import numpy as np

from piano_tutor.pieces import get_piece, PIECES
from piano_tutor.follower import ScoreFollower
from piano_tutor.session import PracticeSession, format_feedback, iter_frames

FRAME = 2048
HOP = 512


def load_wav(path: str) -> tuple[np.ndarray, int]:
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        raw = wf.readframes(wf.getnframes())

    if sampwidth == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    elif sampwidth == 4:
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float64) / 2147483648.0
    elif sampwidth == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128) / 128.0
    else:
        raise ValueError(f"unsupported sample width: {sampwidth} bytes")

    if n_channels > 1:
        data = data.reshape(-1, n_channels).mean(axis=1)
    return data, sr


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python analyze_file.py <recording.wav> [piece]")
        print(f"pieces: {', '.join(sorted(PIECES))}")
        return 2

    path = sys.argv[1]
    key = sys.argv[2] if len(sys.argv) > 2 else "twinkle"
    if key not in PIECES:
        print(f"Unknown piece '{key}'. Available: {', '.join(sorted(PIECES))}")
        return 2

    piece = get_piece(key)
    audio, sr = load_wav(path)
    print(f"Loaded {path}: {len(audio)/sr:.1f}s @ {sr} Hz")
    print(f"Piece: {piece.title}\n")

    follower = ScoreFollower(piece.notes, advance_on_wrong=True)
    session = PracticeSession(follower=follower, sr=sr)
    session.run_frames(iter_frames(audio, FRAME, HOP),
                       on_feedback=lambda fb: print(format_feedback(fb)))

    total = len(piece.notes)
    print(f"\nSummary: {follower.correct_count}/{total} correct, "
          f"{follower.wrong_count} wrong.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
