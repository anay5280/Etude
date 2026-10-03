#!/usr/bin/env python3
"""Learn a piece: the full lesson flow.

    Phase 1  DEMONSTRATE  — hear the piece played.
    Phase 2  GUIDED       — learn it note-by-note; play each note back to advance.
    Phase 3  PRACTICE     — play the whole piece and get graded.

    python learn.py twinkle                 # real microphone (needs sounddevice)
    python learn.py ode_to_joy --phrase 4   # phrase length for the guided phase
    python learn.py twinkle --simulate      # no mic: walk through the flow on synth

Teaching is note-by-note, so it uses the monophonic melody pieces (see --list).
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

from piano_tutor.pieces import get_piece, PIECES, CHORD_PIECES
from piano_tutor.lesson import GuidedLesson, TeachEvent
from piano_tutor.follower import ScoreFollower, NoteSegmenter
from piano_tutor.pitch import detect_f0
from piano_tutor.session import PracticeSession, format_feedback, iter_frames
from piano_tutor.synth import render_notes, tone
from piano_tutor.notes import name_to_midi, midi_to_freq

SR = 22050
FRAME = 2048
HOP = 512

_GREEN = "\033[92m"
_RED = "\033[91m"
_CYAN = "\033[96m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


def banner(text: str) -> None:
    print(f"\n{_BOLD}{_CYAN}=== {text} ==={_RESET}\n")


def show_event(ev: TeachEvent) -> None:
    color = {"prompt": _CYAN, "correct": _GREEN, "phrase_done": _GREEN,
             "lesson_done": _GREEN, "retry": _RED}.get(ev.kind, "")
    print(f"{color}{ev.message}{_RESET}")


def reference_tone(note_name: str) -> np.ndarray:
    return tone(midi_to_freq(name_to_midi(note_name)), 0.6, SR)


# ---------------------------------------------------------------------------
# Simulated run (no microphone) — proves the whole flow end to end.
# ---------------------------------------------------------------------------

def run_simulated(piece, phrase_size: int) -> int:
    print(f"Piece: {piece.title}  (SIMULATED — no microphone)")

    banner("Phase 1 · Demonstrate")
    print("Playing the piece for you to hear:")
    print("  " + " ".join(piece.notes))

    banner("Phase 2 · Guided — note by note")
    lesson = GuidedLesson(piece.notes, phrase_size=phrase_size)
    last_phrase = -1
    while not lesson.finished:
        prompt = lesson.prompt()
        if prompt.phrase_index != last_phrase:
            phrase_notes = lesson.current_phrase_notes()
            print(f"\n-- Phrase {prompt.phrase_index + 1}: {' '.join(phrase_notes)} --")
            last_phrase = prompt.phrase_index
        show_event(prompt)
        # A learner who plays the right note (simulated).
        ev = lesson.feed(name_to_midi(prompt.target_name))
        show_event(ev)
    print(f"\nGuided phase complete: {lesson.correct_count} notes learned.")

    banner("Phase 3 · Practice — full piece, graded")
    audio = render_notes(piece.notes, SR)
    follower = ScoreFollower(piece.notes, advance_on_wrong=True)
    session = PracticeSession(follower=follower, sr=SR)
    session.run_frames(iter_frames(audio, FRAME, HOP),
                       on_feedback=lambda fb: print(format_feedback(fb)))
    total = len(piece.notes)
    print(f"\nFinal score: {follower.correct_count}/{total} correct.")
    return 0


# ---------------------------------------------------------------------------
# Real microphone run.
# ---------------------------------------------------------------------------

def _listen_for_note(mic, segmenter: NoteSegmenter) -> int:
    """Block until the mic commits one stable note; return its MIDI number."""
    for frame in mic.frames():
        result = detect_f0(frame, mic.sr)
        midi = result.pitch.midi if result.pitch is not None else None
        committed = segmenter.feed(midi)
        if committed is not None:
            return committed
    raise RuntimeError("mic stream ended")  # frames() is infinite in practice


def run_with_mic(piece, phrase_size: int) -> int:
    from piano_tutor.miclisten import MicPiano, MicUnavailableError
    try:
        mic_cm = MicPiano(SR, FRAME, HOP)
    except MicUnavailableError as exc:
        print(exc)
        print("Tip: try  python learn.py", piece.key, "--simulate  to see the flow.")
        return 1

    print(f"Piece: {piece.title}")
    with mic_cm as mic:
        banner("Phase 1 · Demonstrate")
        print("Listen to the whole piece...")
        mic.play(render_notes(piece.notes, SR))

        banner("Phase 2 · Guided — play each note back")
        lesson = GuidedLesson(piece.notes, phrase_size=phrase_size)
        last_phrase = -1
        while not lesson.finished:
            prompt = lesson.prompt()
            if prompt.phrase_index != last_phrase:
                phrase_notes = lesson.current_phrase_notes()
                print(f"\n-- Phrase {prompt.phrase_index + 1}: {' '.join(phrase_notes)} --")
                print("Listen to the phrase...")
                start, end = lesson.phrases[prompt.phrase_index]
                mic.play(render_notes(piece.notes[start:end], SR))
                last_phrase = prompt.phrase_index

            show_event(prompt)
            mic.play(reference_tone(prompt.target_name))  # demo the single note
            mic.flush()                                    # ignore that playback
            segmenter = NoteSegmenter()
            while True:
                played = _listen_for_note(mic, segmenter)
                ev = lesson.feed(played)
                show_event(ev)
                if ev.kind != "retry":
                    break
        print(f"\nGuided phase complete: {lesson.correct_count} notes learned.")

        banner("Phase 3 · Practice — play the whole piece")
        print("Play it through. Ctrl+C to stop.\n")
        follower = ScoreFollower(piece.notes, advance_on_wrong=False)
        session = PracticeSession(follower=follower, sr=SR)
        try:
            for frame in mic.frames():
                fb = session.process_frame(frame)
                if fb is not None:
                    print(format_feedback(fb))
                if follower.finished:
                    break
        except KeyboardInterrupt:
            print("\nStopped.")
        total = len(piece.notes)
        print(f"\nFinal score: {follower.correct_count}/{total} correct, "
              f"{follower.wrong_count} wrong.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Learn a piano piece step by step.")
    parser.add_argument("piece", nargs="?", default="twinkle")
    parser.add_argument("--phrase", type=int, default=4,
                        help="notes per phrase in the guided phase (default 4)")
    parser.add_argument("--simulate", action="store_true",
                        help="no microphone: walk through the flow on synthesized audio")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        print("Melody pieces you can learn:")
        for key, piece in PIECES.items():
            print(f"  {key:16s} {piece.title} ({len(piece.notes)} notes)")
        return 0

    # A piece can be a built-in key or a path to a MIDI/MusicXML file.
    if os.path.exists(args.piece):
        from piano_tutor.importer import to_piece
        try:
            piece = to_piece(args.piece)
        except Exception as exc:  # noqa: BLE001
            print(f"Could not import '{args.piece}': {exc}")
            return 2
        print(f"Imported {len(piece.notes)}-note melody from {args.piece}")
    elif args.piece in CHORD_PIECES:
        print(f"'{args.piece}' is a chord piece. Guided teaching is note-by-note, "
              f"so pick a melody piece (see --list).")
        return 2
    elif args.piece not in PIECES:
        print(f"Unknown piece '{args.piece}'. Try --list, or pass a .mid/.musicxml file.")
        return 2
    else:
        piece = get_piece(args.piece)
    if args.simulate:
        return run_simulated(piece, args.phrase)
    return run_with_mic(piece, args.phrase)


if __name__ == "__main__":
    raise SystemExit(main())
