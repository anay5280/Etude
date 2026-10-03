"""The teaching state machine — the "learn the piece" experience.

A lesson has three phases:

    1. DEMONSTRATE   — the piece is played so the learner hears it.
    2. GUIDED        — note-by-note call-and-response: the app shows and plays
                       the next note, waits for the learner to play it back, and
                       only advances when it's correct (with a hint on a miss).
                       Taught phrase by phrase so it's digestible.
    3. PRACTICE      — the learner plays the whole piece and is graded.

This module holds only the *logic* (which note is next, is it right, when a
phrase or phase ends). Audio in/out lives in the entry point so this stays
pure and unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass

from .notes import name_to_midi, midi_to_name, is_black_key
from .follower import _correction_hint


def make_phrases(n_notes: int, phrase_size: int) -> list[tuple[int, int]]:
    """Split a piece of `n_notes` into (start, end) phrase spans."""
    if phrase_size < 1:
        raise ValueError("phrase_size must be >= 1")
    return [(i, min(i + phrase_size, n_notes)) for i in range(0, n_notes, phrase_size)]


def describe_target(midi: int) -> str:
    """A short, learner-friendly description of a note to play."""
    kind = "black" if is_black_key(midi) else "white"
    return f"{midi_to_name(midi)} (a {kind} key)"


@dataclass
class TeachEvent:
    """Something the lesson wants to tell the learner during the guided phase."""

    kind: str            # "prompt" | "correct" | "retry" | "phrase_done" | "lesson_done"
    phrase_index: int
    note_index: int      # position within the whole piece
    total_notes: int
    target_name: str | None
    played_name: str | None
    message: str


class GuidedLesson:
    """Note-by-note teaching over one piece, one phrase at a time.

    Usage: call `prompt()` to get the next thing to show/play, then feed the
    learner's played note to `feed(midi)`; it returns the resulting event and
    advances internally when the note is correct.
    """

    def __init__(self, notes: list[str], phrase_size: int = 4):
        if not notes:
            raise ValueError("piece has no notes")
        self.notes = list(notes)
        self.midi = [name_to_midi(n) for n in notes]
        self.phrase_size = phrase_size
        self.phrases = make_phrases(len(notes), phrase_size)
        self.pos = 0
        self.attempts = 0     # attempts on the current note
        self.total_attempts = 0
        self.correct_count = 0

    @property
    def finished(self) -> bool:
        return self.pos >= len(self.notes)

    @property
    def phrase_index(self) -> int:
        return self.pos // self.phrase_size

    def current_phrase_notes(self) -> list[str]:
        start, end = self.phrases[self.phrase_index]
        return self.notes[start:end]

    def prompt(self) -> TeachEvent:
        """The instruction to show/play for the current note."""
        target_midi = self.midi[self.pos]
        return TeachEvent(
            kind="prompt",
            phrase_index=self.phrase_index,
            note_index=self.pos,
            total_notes=len(self.notes),
            target_name=self.notes[self.pos],
            played_name=None,
            message=f"Play {describe_target(target_midi)}.",
        )

    def feed(self, played_midi: int) -> TeachEvent:
        """Judge a played note; advance on success. Returns the event."""
        target_midi = self.midi[self.pos]
        target_name = self.notes[self.pos]
        played_name = midi_to_name(played_midi)
        self.attempts += 1
        self.total_attempts += 1

        if played_midi != target_midi:
            return TeachEvent(
                kind="retry",
                phrase_index=self.phrase_index,
                note_index=self.pos,
                total_notes=len(self.notes),
                target_name=target_name,
                played_name=played_name,
                message=("Not quite — " + _correction_hint(played_midi, target_midi)
                         + " Try again."),
            )

        # Correct.
        self.correct_count += 1
        phrase_before = self.phrase_index
        self.pos += 1
        self.attempts = 0

        if self.finished:
            return TeachEvent(
                kind="lesson_done",
                phrase_index=phrase_before,
                note_index=self.pos - 1,
                total_notes=len(self.notes),
                target_name=target_name,
                played_name=played_name,
                message=(f"Great — {target_name}! You've learned the whole piece "
                         f"({self.correct_count} notes)."),
            )

        crossed_phrase = self.phrase_index != phrase_before
        if crossed_phrase:
            return TeachEvent(
                kind="phrase_done",
                phrase_index=phrase_before,
                note_index=self.pos - 1,
                total_notes=len(self.notes),
                target_name=target_name,
                played_name=played_name,
                message=f"Nice — {target_name}! Phrase {phrase_before + 1} complete.",
            )

        return TeachEvent(
            kind="correct",
            phrase_index=self.phrase_index,
            note_index=self.pos - 1,
            total_notes=len(self.notes),
            target_name=target_name,
            played_name=played_name,
            message=f"Correct — {target_name}!",
        )
