"""Tests for MIDI / MusicXML import, validated against known fixtures."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from piano_tutor.importer import (  # noqa: E402
    parse_midi, parse_musicxml, load_notes, to_melody, to_chords,
    to_piece, to_chord_piece,
)

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


class TestMidiImport(unittest.TestCase):
    def test_scale_melody(self):
        notes = parse_midi(os.path.join(FIX, "scale.mid"))
        self.assertEqual(to_melody(notes), ["C4", "D4", "E4", "F4", "G4"])

    def test_scale_is_ordered_in_time(self):
        notes = parse_midi(os.path.join(FIX, "scale.mid"))
        starts = [n.start for n in notes]
        self.assertEqual(starts, sorted(starts))
        # 120 bpm, quarter notes -> 0.5s apart.
        self.assertAlmostEqual(notes[1].start - notes[0].start, 0.5, places=2)

    def test_chords(self):
        notes = parse_midi(os.path.join(FIX, "chords.mid"))
        self.assertEqual(to_chords(notes), [["C4", "E4", "G4"], ["G3", "B3", "D4"]])


class TestMusicXmlImport(unittest.TestCase):
    def test_melody_with_sharp_and_chord(self):
        notes = parse_musicxml(os.path.join(FIX, "melody.musicxml"))
        # F#4 comes from <alter>1</alter>; last melody note is the top of the chord.
        self.assertEqual(to_melody(notes), ["C4", "D4", "E4", "F#4", "G4"])

    def test_chord_grouping(self):
        notes = parse_musicxml(os.path.join(FIX, "melody.musicxml"))
        chords = to_chords(notes)
        self.assertEqual(chords[-1], ["C4", "E4", "G4"])  # the <chord/> onset

    def test_mxl_zip_matches_plain(self):
        plain = to_melody(parse_musicxml(os.path.join(FIX, "melody.musicxml")))
        zipped = to_melody(load_notes(os.path.join(FIX, "melody.mxl")))
        self.assertEqual(plain, zipped)


class TestDispatchAndPieces(unittest.TestCase):
    def test_load_notes_dispatch(self):
        self.assertTrue(load_notes(os.path.join(FIX, "scale.mid")))
        self.assertTrue(load_notes(os.path.join(FIX, "melody.musicxml")))

    def test_unsupported_extension(self):
        with self.assertRaises(ValueError):
            load_notes("song.txt")

    def test_to_piece(self):
        piece = to_piece(os.path.join(FIX, "scale.mid"))
        self.assertEqual(piece.notes, ["C4", "D4", "E4", "F4", "G4"])
        self.assertEqual(piece.key, "scale")

    def test_to_chord_piece(self):
        cp = to_chord_piece(os.path.join(FIX, "chords.mid"))
        self.assertEqual(cp.chords, [["C4", "E4", "G4"], ["G3", "B3", "D4"]])


if __name__ == "__main__":
    unittest.main()
