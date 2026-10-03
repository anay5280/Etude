"""Unit tests for the note math, pitch detection and score follower."""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from piano_tutor.notes import (  # noqa: E402
    freq_to_midi, midi_to_freq, midi_to_name, name_to_midi, cents_off, nearest_note,
)
from piano_tutor.pitch import detect_f0  # noqa: E402
from piano_tutor.follower import (  # noqa: E402
    NoteSegmenter, ScoreFollower, ChordSegmenter, PolyScoreFollower,
)
from piano_tutor.poly import detect_chord, midi_set  # noqa: E402
from piano_tutor.synth import tone, chord_tone  # noqa: E402

SR = 22050


class TestNotes(unittest.TestCase):
    def test_a4_roundtrip(self):
        self.assertAlmostEqual(midi_to_freq(69), 440.0)
        self.assertAlmostEqual(freq_to_midi(440.0), 69.0)

    def test_names(self):
        self.assertEqual(midi_to_name(60), "C4")
        self.assertEqual(midi_to_name(69), "A4")
        self.assertEqual(name_to_midi("C4"), 60)
        self.assertEqual(name_to_midi("F#3"), 54)
        self.assertEqual(name_to_midi("E5"), 76)

    def test_name_roundtrip(self):
        for m in range(21, 108):  # full piano range
            self.assertEqual(name_to_midi(midi_to_name(m)), m)

    def test_cents(self):
        self.assertAlmostEqual(cents_off(440.0, 69), 0.0, places=6)
        self.assertGreater(cents_off(445.0, 69), 0)  # sharp
        self.assertLess(cents_off(435.0, 69), 0)     # flat

    def test_nearest_note(self):
        p = nearest_note(261.63)  # ~C4
        self.assertEqual(p.name, "C4")
        self.assertTrue(p.in_tune)


class TestPitch(unittest.TestCase):
    def test_detects_known_tones(self):
        for name in ["C4", "E4", "G4", "A4", "C5"]:
            midi = name_to_midi(name)
            freq = midi_to_freq(midi)
            frame = tone(freq, 0.2, SR)[:2048]
            result = detect_f0(frame, SR)
            self.assertIsNotNone(result.pitch, f"no pitch for {name}")
            self.assertEqual(result.pitch.name, name)

    def test_silence_is_none(self):
        frame = np.zeros(2048)
        self.assertIsNone(detect_f0(frame, SR).pitch)


class TestSegmenter(unittest.TestCase):
    def test_stable_note_commits_once(self):
        seg = NoteSegmenter(min_stable_frames=3, min_gap_frames=2)
        commits = [seg.feed(60) for _ in range(10)]
        self.assertEqual([c for c in commits if c is not None], [60])

    def test_repeated_note_after_gap(self):
        seg = NoteSegmenter(min_stable_frames=3, min_gap_frames=2)
        out = []
        for m in [60, 60, 60, None, None, 60, 60, 60]:
            out.append(seg.feed(m))
        self.assertEqual([c for c in out if c is not None], [60, 60])


class TestFollower(unittest.TestCase):
    def test_all_correct(self):
        f = ScoreFollower(["C4", "D4", "E4"])
        for name in ["C4", "D4", "E4"]:
            fb = f.on_note(name_to_midi(name))
            self.assertEqual(fb.status, "correct")
        self.assertTrue(f.finished)
        self.assertEqual(f.correct_count, 3)

    def test_wrong_note_reported_and_waits(self):
        f = ScoreFollower(["C4", "D4"], advance_on_wrong=False)
        fb = f.on_note(name_to_midi("C#4"))  # one semitone high vs C4
        self.assertEqual(fb.status, "wrong")
        self.assertEqual(fb.expected_name, "C4")
        self.assertEqual(fb.played_name, "C#4")
        self.assertEqual(fb.semitones, -1)  # expected is 1 below played
        self.assertEqual(f.pos, 0)  # did not advance
        # Now play it right.
        fb = f.on_note(name_to_midi("C4"))
        self.assertEqual(fb.status, "correct")
        self.assertEqual(f.pos, 1)


class TestPolyDetection(unittest.TestCase):
    POLY_SR = 22050
    POLY_FRAME = 8192

    def _detect_names(self, note_names):
        audio = chord_tone(note_names, 0.6, self.POLY_SR)
        frame = audio[self.POLY_FRAME:2 * self.POLY_FRAME]
        return sorted(midi_to_name(m) for m in midi_set(detect_chord(frame, self.POLY_SR)))

    def test_major_triad(self):
        self.assertEqual(self._detect_names(["C4", "E4", "G4"]), ["C4", "E4", "G4"])

    def test_minor_triad(self):
        self.assertEqual(self._detect_names(["A3", "C4", "E4"]), ["A3", "C4", "E4"])

    def test_inversion(self):
        self.assertEqual(self._detect_names(["E4", "G4", "C5"]), ["C5", "E4", "G4"])

    def test_single_note_as_chord(self):
        self.assertEqual(self._detect_names(["C4"]), ["C4"])

    def test_silence(self):
        self.assertEqual(detect_chord(np.zeros(self.POLY_FRAME), self.POLY_SR), [])


class TestChordSegmenter(unittest.TestCase):
    def test_stable_chord_commits_once(self):
        seg = ChordSegmenter(min_stable_frames=3, min_gap_frames=2)
        chord = {60, 64, 67}
        commits = [seg.feed(chord) for _ in range(8)]
        fired = [c for c in commits if c is not None]
        self.assertEqual(fired, [frozenset(chord)])


class TestPolyFollower(unittest.TestCase):
    def test_correct_progression(self):
        f = PolyScoreFollower([["C4", "E4", "G4"], ["G3", "B3", "D4"]])
        fb = f.on_chord({name_to_midi(n) for n in ["C4", "E4", "G4"]})
        self.assertEqual(fb.status, "correct")
        fb = f.on_chord({name_to_midi(n) for n in ["G3", "B3", "D4"]})
        self.assertEqual(fb.status, "correct")
        self.assertTrue(f.finished)

    def test_wrong_note_in_chord(self):
        f = PolyScoreFollower([["A3", "C4", "E4"]])
        # Played F4 instead of E4.
        fb = f.on_chord({name_to_midi(n) for n in ["A3", "C4", "F4"]})
        self.assertEqual(fb.status, "wrong")
        self.assertEqual(fb.missing_names, ["E4"])
        self.assertEqual(fb.extra_names, ["F4"])


if __name__ == "__main__":
    unittest.main()
