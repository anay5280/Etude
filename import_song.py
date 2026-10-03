#!/usr/bin/env python3
"""Import a real song from MIDI or MusicXML and inspect it.

    python import_song.py song.mid                 # melody + chord summary
    python import_song.py song.musicxml --chords    # show the chord sequence
    python import_song.py song.mxl --melody         # show the melody line

Supported: .mid, .midi, .xml, .musicxml, .mxl  (standard library only).

Once imported, you can learn or practice the song directly, e.g.:
    python learn.py song.mid --simulate
"""

from __future__ import annotations

import argparse
import os

from piano_tutor.importer import load_notes, to_melody, to_chords


def main() -> int:
    parser = argparse.ArgumentParser(description="Import and inspect a MIDI/MusicXML song.")
    parser.add_argument("file", help="path to a .mid/.midi/.xml/.musicxml/.mxl file")
    parser.add_argument("--melody", action="store_true", help="print the melody line")
    parser.add_argument("--chords", action="store_true", help="print the chord sequence")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"File not found: {args.file}")
        return 2

    try:
        notes = load_notes(args.file)
    except Exception as exc:  # noqa: BLE001
        print(f"Could not import: {exc}")
        return 2

    melody = to_melody(notes)
    chords = to_chords(notes)
    duration = max((n.start + n.duration for n in notes), default=0.0)

    print(f"Imported: {os.path.basename(args.file)}")
    print(f"  {len(notes)} notes, {len(chords)} onsets, ~{duration:.1f}s")
    print(f"  polyphony: {'chords present' if any(len(c) > 1 for c in chords) else 'monophonic'}")

    show_melody = args.melody or not args.chords
    show_chords = args.chords or not args.melody

    if show_melody:
        print(f"\nMelody ({len(melody)} notes):")
        print("  " + " ".join(melody))
    if show_chords:
        print(f"\nChords ({len(chords)} onsets):")
        print("  " + "  ".join("+".join(c) for c in chords))

    print("\nLearn it:   python learn.py", args.file, "--simulate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
