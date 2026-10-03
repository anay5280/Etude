"""Tests for the teaching state machine (GuidedLesson)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from piano_tutor.lesson import GuidedLesson, make_phrases, describe_target  # noqa: E402
from piano_tutor.notes import name_to_midi  # noqa: E402


class TestPhrases(unittest.TestCase):
    def test_even_split(self):
        self.assertEqual(make_phrases(8, 4), [(0, 4), (4, 8)])

    def test_uneven_split(self):
        self.assertEqual(make_phrases(7, 3), [(0, 3), (3, 6), (6, 7)])

    def test_describe_target(self):
        self.assertIn("white", describe_target(name_to_midi("C4")))
        self.assertIn("black", describe_target(name_to_midi("C#4")))


class TestGuidedLesson(unittest.TestCase):
    def test_advances_on_correct(self):
        lesson = GuidedLesson(["C4", "D4", "E4"], phrase_size=4)
        self.assertEqual(lesson.prompt().target_name, "C4")
        ev = lesson.feed(name_to_midi("C4"))
        self.assertEqual(ev.kind, "correct")
        self.assertEqual(lesson.prompt().target_name, "D4")

    def test_retry_then_correct(self):
        lesson = GuidedLesson(["C4", "D4"], phrase_size=4)
        ev = lesson.feed(name_to_midi("C#4"))  # wrong
        self.assertEqual(ev.kind, "retry")
        self.assertEqual(lesson.pos, 0)         # did not advance
        self.assertIn("Try again", ev.message)
        ev = lesson.feed(name_to_midi("C4"))   # right
        self.assertEqual(ev.kind, "correct")
        self.assertEqual(lesson.pos, 1)

    def test_phrase_boundary(self):
        lesson = GuidedLesson(["C4", "D4", "E4", "F4"], phrase_size=2)
        lesson.feed(name_to_midi("C4"))
        ev = lesson.feed(name_to_midi("D4"))   # completes phrase 1
        self.assertEqual(ev.kind, "phrase_done")
        self.assertEqual(ev.phrase_index, 0)

    def test_lesson_done(self):
        notes = ["C4", "D4"]
        lesson = GuidedLesson(notes, phrase_size=4)
        lesson.feed(name_to_midi("C4"))
        ev = lesson.feed(name_to_midi("D4"))
        self.assertEqual(ev.kind, "lesson_done")
        self.assertTrue(lesson.finished)
        self.assertEqual(lesson.correct_count, 2)

    def test_full_walkthrough_counts_attempts(self):
        lesson = GuidedLesson(["C4", "D4", "E4"], phrase_size=4)
        # miss D4 once
        for played in ["C4", "C4", "D4", "E4"]:  # C4 ok, C4 (wrong for D4), D4 ok, E4 ok
            lesson.feed(name_to_midi(played))
        self.assertTrue(lesson.finished)
        self.assertEqual(lesson.correct_count, 3)
        self.assertEqual(lesson.total_attempts, 4)


if __name__ == "__main__":
    unittest.main()
