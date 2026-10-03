"""Tests for the neural (basic-pitch) integration.

The onset-grouping / ghost-filtering logic is pure and always tested. The actual
transcription test runs only where basic-pitch is installed (e.g. the .venv310
environment); elsewhere it's skipped.
"""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from piano_tutor.neural import (  # noqa: E402
    NoteEvent, Onset, group_into_onsets, to_note_stream, NEURAL_AVAILABLE,
)
from piano_tutor.notes import name_to_midi, midi_to_name  # noqa: E402


class TestOnsetGrouping(unittest.TestCase):
    def test_groups_by_onset_and_drops_ghosts(self):
        # A C-major chord at t=0 with a short ghost note, then A-minor at t=1.
        events = [
            NoteEvent(0.00, 0.80, name_to_midi("C4"), 0.7),
            NoteEvent(0.01, 0.79, name_to_midi("E4"), 0.7),
            NoteEvent(0.01, 0.78, name_to_midi("G4"), 0.6),
            NoteEvent(0.02, 0.20, name_to_midi("D6"), 0.3),   # short ghost -> dropped
            NoteEvent(1.00, 1.80, name_to_midi("A3"), 0.5),
            NoteEvent(1.01, 1.79, name_to_midi("C4"), 0.7),
            NoteEvent(1.01, 1.78, name_to_midi("E4"), 0.7),
        ]
        onsets = group_into_onsets(events)
        self.assertEqual(len(onsets), 2)
        self.assertEqual(onsets[0].names, ["C4", "E4", "G4"])
        self.assertEqual(onsets[1].names, ["A3", "C4", "E4"])

    def test_note_stream(self):
        events = [
            NoteEvent(0.0, 0.4, name_to_midi("E4"), 0.7),
            NoteEvent(0.5, 0.9, name_to_midi("D4"), 0.7),
            NoteEvent(1.0, 1.4, name_to_midi("C4"), 0.7),
        ]
        stream = to_note_stream(group_into_onsets(events))
        self.assertEqual([midi_to_name(m) for m in stream], ["E4", "D4", "C4"])

    def test_empty(self):
        self.assertEqual(group_into_onsets([]), [])


@unittest.skipUnless(NEURAL_AVAILABLE, "basic-pitch not installed in this environment")
class TestNeuralTranscription(unittest.TestCase):
    def test_transcribes_a_chord(self):
        from piano_tutor.synth import render_chords
        from piano_tutor.neural import transcribe_array

        sr = 22050
        audio = render_chords([["C4", "E4", "G4"]], sr, chord_dur=0.9, gap_dur=0.2)
        events = transcribe_array(audio, sr)
        onsets = group_into_onsets(events)
        self.assertGreaterEqual(len(onsets), 1)
        # The strongest onset should contain the C-major triad.
        detected = set()
        for o in onsets:
            detected |= o.midis
        for note in ["C4", "E4", "G4"]:
            self.assertIn(name_to_midi(note), detected, f"missing {note}")


if __name__ == "__main__":
    unittest.main()
