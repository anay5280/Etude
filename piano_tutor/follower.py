"""Turn a stream of per-frame pitch estimates into note events, then follow
them against a reference piece and judge each note.

Two pieces:
  * NoteSegmenter — debounces the noisy per-frame pitch stream into discrete,
    stable note onsets (so a single held key doesn't fire dozens of times, and
    a repeated key fires twice).
  * ScoreFollower — compares each committed note to the expected note and
    produces human-readable feedback with a correction.
"""

from __future__ import annotations

from dataclasses import dataclass

from .notes import name_to_midi, midi_to_name, is_black_key


# ---------------------------------------------------------------------------
# Segmentation: per-frame pitches -> discrete note onsets
# ---------------------------------------------------------------------------


class NoteSegmenter:
    """Debounce a per-frame MIDI stream into stable note onsets.

    Call `feed(midi)` once per audio frame (`midi` is None for silence). It
    returns a committed MIDI note number when a new, stable note begins, else
    None. A note must be held for `min_stable_frames` frames to commit. A gap
    of `min_gap_frames` silent frames lets the *same* pitch commit again (so
    repeated notes are counted).
    """

    def __init__(self, min_stable_frames: int = 3, min_gap_frames: int = 2):
        self.min_stable_frames = min_stable_frames
        self.min_gap_frames = min_gap_frames
        self._candidate: int | None = None
        self._candidate_count = 0
        self._committed: int | None = None
        self._silence_count = 0

    def feed(self, midi: int | None) -> int | None:
        if midi is None:
            self._silence_count += 1
            if self._silence_count >= self.min_gap_frames:
                # A real gap ended the current note; allow a repeat to re-fire.
                self._committed = None
                self._candidate = None
                self._candidate_count = 0
            return None

        self._silence_count = 0
        if midi == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate = midi
            self._candidate_count = 1

        stable = self._candidate_count >= self.min_stable_frames
        if stable and self._candidate != self._committed:
            self._committed = self._candidate
            return self._candidate
        return None


# ---------------------------------------------------------------------------
# Following: committed notes -> judged feedback
# ---------------------------------------------------------------------------


@dataclass
class Feedback:
    status: str            # "correct" | "wrong" | "done"
    position: int          # index in the piece this feedback concerns
    total: int             # total notes in the piece
    expected_name: str | None
    played_name: str | None
    semitones: int         # signed distance played->expected (0 when correct)
    message: str


def _correction_hint(played_midi: int, expected_midi: int) -> str:
    """Plain-language guidance to get from the played note to the right one."""
    semitones = expected_midi - played_midi
    if semitones == 0:
        return "That's the right note."

    direction = "up" if semitones > 0 else "down"
    steps = abs(semitones)
    key_word = "key" if steps == 1 else "keys"
    hint = (
        f"You're {steps} semitone{'s' if steps > 1 else ''} too "
        f"{'low' if semitones > 0 else 'high'}. "
        f"Move {direction} {steps} {key_word} on the keyboard "
        f"(counting black and white keys) to reach {midi_to_name(expected_midi)}."
    )
    target_kind = "black" if is_black_key(expected_midi) else "white"
    hint += f" {midi_to_name(expected_midi)} is a {target_kind} key."
    return hint


class ScoreFollower:
    """Follow committed notes against a reference piece and judge each one.

    Monophonic, in-order following: it expects the next note of the piece. On a
    wrong note it stays on the same position and waits for the correct note, so
    the learner can retry. Set `advance_on_wrong=True` to move on regardless.
    """

    def __init__(self, expected_notes: list[str], advance_on_wrong: bool = False):
        if not expected_notes:
            raise ValueError("piece has no notes")
        self.expected_names = list(expected_notes)
        self.expected_midi = [name_to_midi(n) for n in expected_notes]
        self.advance_on_wrong = advance_on_wrong
        self.pos = 0
        self.correct_count = 0
        self.wrong_count = 0

    @property
    def finished(self) -> bool:
        return self.pos >= len(self.expected_midi)

    def on_note(self, played_midi: int) -> Feedback:
        total = len(self.expected_midi)
        if self.finished:
            return Feedback("done", total, total, None,
                            midi_to_name(played_midi), 0, "The piece is complete.")

        expected_midi = self.expected_midi[self.pos]
        expected_name = self.expected_names[self.pos]
        played_name = midi_to_name(played_midi)

        if played_midi == expected_midi:
            self.correct_count += 1
            pos = self.pos
            self.pos += 1
            msg = f"Correct — {expected_name}."
            if self.finished:
                msg += f"  Piece complete! {self.correct_count}/{total} notes correct."
            return Feedback("correct", pos, total, expected_name,
                            played_name, 0, msg)

        # Wrong note.
        self.wrong_count += 1
        semitones = expected_midi - played_midi
        message = (
            f"Wrong note: you played {played_name}, but note "
            f"{self.pos + 1} should be {expected_name}. "
            + _correction_hint(played_midi, expected_midi)
        )
        pos = self.pos
        if self.advance_on_wrong:
            self.pos += 1
        return Feedback("wrong", pos, total, expected_name,
                        played_name, semitones, message)


# ---------------------------------------------------------------------------
# Polyphonic (chord) segmentation and following
# ---------------------------------------------------------------------------


class ChordSegmenter:
    """Debounce a per-frame stream of note *sets* into stable chord onsets.

    Call `feed(midi_set)` once per frame (an empty/None set means silence).
    Returns a committed frozenset when a new, stable chord begins, else None.
    """

    def __init__(self, min_stable_frames: int = 3, min_gap_frames: int = 2):
        self.min_stable_frames = min_stable_frames
        self.min_gap_frames = min_gap_frames
        self._candidate: frozenset[int] | None = None
        self._candidate_count = 0
        self._committed: frozenset[int] | None = None
        self._silence_count = 0

    def feed(self, midi_set) -> frozenset[int] | None:
        current = frozenset(midi_set) if midi_set else frozenset()
        if not current:
            self._silence_count += 1
            if self._silence_count >= self.min_gap_frames:
                self._committed = None
                self._candidate = None
                self._candidate_count = 0
            return None

        self._silence_count = 0
        if current == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate = current
            self._candidate_count = 1

        stable = self._candidate_count >= self.min_stable_frames
        if stable and self._candidate != self._committed:
            self._committed = self._candidate
            return self._candidate
        return None


@dataclass
class ChordFeedback:
    status: str                  # "correct" | "wrong" | "done"
    position: int
    total: int
    expected_names: list[str]
    played_names: list[str]
    missing_names: list[str]     # expected but not played
    extra_names: list[str]       # played but not in the chord
    message: str


def _chord_name_list(midis) -> list[str]:
    return [midi_to_name(m) for m in sorted(midis)]


def _pair_corrections(missing: set[int], extra: set[int]) -> list[str]:
    """Pair each wrong extra note to the nearest missing note as a suggestion."""
    hints: list[str] = []
    remaining = set(missing)
    for played in sorted(extra):
        if not remaining:
            hints.append(f"{midi_to_name(played)} is not part of this chord — lift it.")
            continue
        target = min(remaining, key=lambda m: abs(m - played))
        remaining.discard(target)
        hints.append(
            f"{midi_to_name(played)} → {_correction_hint(played, target)}"
        )
    for still_missing in sorted(remaining):
        hints.append(f"You're missing {midi_to_name(still_missing)} — add it.")
    return hints


class PolyScoreFollower:
    """Follow committed chords against a reference progression and judge each.

    Each expected entry is a chord (a list of note names). A played chord is
    correct when its set of notes exactly matches the expected set.
    """

    def __init__(self, expected_chords: list[list[str]], advance_on_wrong: bool = True):
        if not expected_chords:
            raise ValueError("piece has no chords")
        self.expected_names = [list(ch) for ch in expected_chords]
        self.expected_sets = [frozenset(name_to_midi(n) for n in ch)
                              for ch in expected_chords]
        self.advance_on_wrong = advance_on_wrong
        self.pos = 0
        self.correct_count = 0
        self.wrong_count = 0

    @property
    def finished(self) -> bool:
        return self.pos >= len(self.expected_sets)

    def on_chord(self, played) -> ChordFeedback:
        played = frozenset(played)
        total = len(self.expected_sets)
        if self.finished:
            return ChordFeedback("done", total, total, [],
                                 _chord_name_list(played), [], [],
                                 "The piece is complete.")

        expected = self.expected_sets[self.pos]
        expected_names = self.expected_names[self.pos]
        played_names = _chord_name_list(played)
        pos = self.pos

        if played == expected:
            self.correct_count += 1
            self.pos += 1
            msg = f"Correct — chord {' '.join(expected_names)}."
            if self.finished:
                msg += f"  Piece complete! {self.correct_count}/{total} chords correct."
            return ChordFeedback("correct", pos, total, expected_names,
                                 played_names, [], [], msg)

        self.wrong_count += 1
        missing = set(expected) - set(played)
        extra = set(played) - set(expected)
        hints = _pair_corrections(missing, extra)
        msg = (f"Wrong chord {pos + 1}: expected {' '.join(expected_names)}, "
               f"you played {' '.join(played_names) or '(nothing)'}. "
               + " ".join(hints))
        if self.advance_on_wrong:
            self.pos += 1
        return ChordFeedback("wrong", pos, total, expected_names, played_names,
                             _chord_name_list(missing), _chord_name_list(extra), msg)
