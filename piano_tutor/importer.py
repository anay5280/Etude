"""Import real songs from MIDI and MusicXML files — no third-party deps.

Turns a `.mid`/`.midi`, `.xml`/`.musicxml`, or compressed `.mxl` file into the
project's piece formats:

    * a monophonic melody (top note of each onset)  -> for learn.py / live.py
    * a chord sequence (all notes of each onset)     -> for the polyphonic path

Everything here uses only the Python standard library (struct, xml, zipfile),
so imported songs work even in the numpy-only environment.
"""

from __future__ import annotations

import os
import struct
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass

from .notes import midi_to_name
from .pieces import Piece, ChordPiece

_STEP_TO_SEMITONE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_DEFAULT_TEMPO = 500000  # microseconds per quarter note (120 bpm)


@dataclass(frozen=True)
class TimedNote:
    start: float        # seconds
    duration: float     # seconds
    midi: int
    velocity: int = 80

    @property
    def name(self) -> str:
        return midi_to_name(self.midi)


# ---------------------------------------------------------------------------
# MIDI parsing (Standard MIDI File)
# ---------------------------------------------------------------------------

def _read_vlq(data: bytes, i: int) -> tuple[int, int]:
    """Read a MIDI variable-length quantity; return (value, next_index)."""
    value = 0
    while True:
        byte = data[i]
        i += 1
        value = (value << 7) | (byte & 0x7F)
        if not (byte & 0x80):
            return value, i


def _parse_midi_track(data: bytes):
    """Yield (absolute_tick, kind, *args) for one track's events."""
    i = 0
    tick = 0
    status = 0
    n = len(data)
    while i < n:
        delta, i = _read_vlq(data, i)
        tick += delta
        byte = data[i]
        if byte & 0x80:
            status = byte
            i += 1
        # else: running status — reuse previous status byte

        if status == 0xFF:  # meta event
            meta_type = data[i]; i += 1
            length, i = _read_vlq(data, i)
            payload = data[i:i + length]; i += length
            if meta_type == 0x51 and length == 3:  # set tempo
                yield tick, "tempo", struct.unpack(">I", b"\x00" + payload)[0]
            # other meta events ignored
        elif status in (0xF0, 0xF7):  # sysex
            length, i = _read_vlq(data, i)
            i += length
        else:
            hi = status & 0xF0
            if hi in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
                d1 = data[i]; d2 = data[i + 1]; i += 2
                if hi == 0x90 and d2 > 0:
                    yield tick, "on", d1, d2
                elif hi == 0x80 or (hi == 0x90 and d2 == 0):
                    yield tick, "off", d1
            elif hi in (0xC0, 0xD0):
                i += 1  # program change / channel pressure: one data byte


def parse_midi(path: str) -> list[TimedNote]:
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"MThd":
        raise ValueError("not a Standard MIDI File (missing MThd)")
    fmt, ntracks, division = struct.unpack(">HHH", data[8:14])
    if division & 0x8000:
        raise ValueError("SMPTE time division is not supported")
    ticks_per_beat = division

    # Collect all events across tracks with absolute ticks.
    events: list[tuple] = []
    pos = 14
    for _ in range(ntracks):
        if data[pos:pos + 4] != b"MTrk":
            break
        track_len = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        start = pos + 8
        chunk = data[start:start + track_len]
        events.extend(_parse_midi_track(chunk))
        pos = start + track_len

    events.sort(key=lambda e: e[0])

    # Build a tick->seconds map from tempo changes.
    tempo_changes = sorted((tk, rest[0]) for (tk, kind, *rest) in events
                           if kind == "tempo")
    if not tempo_changes or tempo_changes[0][0] != 0:
        tempo_changes.insert(0, (0, _DEFAULT_TEMPO))

    def tick_to_seconds(target_tick: int) -> float:
        seconds = 0.0
        last_tick = 0
        tempo = tempo_changes[0][1]
        for change_tick, change_tempo in tempo_changes:
            if change_tick >= target_tick:
                break
            seconds += (change_tick - last_tick) / ticks_per_beat * (tempo / 1e6)
            last_tick = change_tick
            tempo = change_tempo
        seconds += (target_tick - last_tick) / ticks_per_beat * (tempo / 1e6)
        return seconds

    # Pair note-on with the next matching note-off.
    open_notes: dict[int, list[tuple[int, int]]] = {}
    notes: list[TimedNote] = []
    for tick, kind, *args in events:
        if kind == "on":
            midi, vel = args
            open_notes.setdefault(midi, []).append((tick, vel))
        elif kind == "off":
            midi = args[0]
            stack = open_notes.get(midi)
            if stack:
                on_tick, vel = stack.pop(0)
                start = tick_to_seconds(on_tick)
                end = tick_to_seconds(tick)
                notes.append(TimedNote(start=start, duration=max(0.0, end - start),
                                       midi=midi, velocity=vel))
    notes.sort(key=lambda x: (x.start, x.midi))
    return notes


# ---------------------------------------------------------------------------
# MusicXML parsing (.xml / .musicxml / .mxl)
# ---------------------------------------------------------------------------

def _read_musicxml_bytes(path: str) -> bytes:
    if path.lower().endswith(".mxl"):
        with zipfile.ZipFile(path) as zf:
            root_name = None
            if "META-INF/container.xml" in zf.namelist():
                container = ET.fromstring(zf.read("META-INF/container.xml"))
                rf = container.find(".//{*}rootfile")
                if rf is not None:
                    root_name = rf.get("full-path")
            if root_name is None:
                root_name = next((n for n in zf.namelist()
                                  if n.lower().endswith((".xml", ".musicxml"))
                                  and not n.startswith("META-INF")), None)
            if root_name is None:
                raise ValueError("no score xml found inside .mxl archive")
            return zf.read(root_name)
    with open(path, "rb") as f:
        return f.read()


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _pitch_to_midi(pitch_el: ET.Element) -> int:
    step = pitch_el.findtext("{*}step") or pitch_el.findtext("step")
    octave = pitch_el.findtext("{*}octave") or pitch_el.findtext("octave")
    alter_txt = pitch_el.findtext("{*}alter") or pitch_el.findtext("alter") or "0"
    semitone = _STEP_TO_SEMITONE[step.strip().upper()]
    return (int(octave) + 1) * 12 + semitone + int(float(alter_txt))


def parse_musicxml(path: str) -> list[TimedNote]:
    raw = _read_musicxml_bytes(path)
    root = ET.fromstring(raw)
    if _strip_ns(root.tag) == "score-timewise":
        raise ValueError("score-timewise MusicXML is not supported; use score-partwise")

    notes: list[TimedNote] = []
    for part in root.iter():
        if _strip_ns(part.tag) != "part":
            continue
        divisions = 1
        position = 0            # in divisions
        prev_onset = 0
        prev_duration = 0
        seconds_per_division = 0.5  # assume 120bpm, quarter=0.5s; divisions set below

        for measure in part:
            if _strip_ns(measure.tag) != "measure":
                continue
            for el in measure:
                tag = _strip_ns(el.tag)
                if tag == "attributes":
                    div_txt = el.findtext("{*}divisions") or el.findtext("divisions")
                    if div_txt:
                        divisions = int(div_txt)
                        seconds_per_division = 0.5 / divisions  # quarter = 0.5s @120bpm
                elif tag == "note":
                    dur_txt = (el.findtext("{*}duration") or el.findtext("duration") or "0")
                    duration = int(dur_txt)
                    is_chord = (el.find("{*}chord") is not None
                                or el.find("chord") is not None)
                    is_rest = (el.find("{*}rest") is not None
                               or el.find("rest") is not None)
                    pitch_el = el.find("{*}pitch")
                    if pitch_el is None:
                        pitch_el = el.find("pitch")

                    if is_chord:
                        onset = prev_onset   # shares the previous note's onset
                    else:
                        onset = position
                        position += duration

                    if not is_rest and pitch_el is not None:
                        notes.append(TimedNote(
                            start=onset * seconds_per_division,
                            duration=duration * seconds_per_division,
                            midi=_pitch_to_midi(pitch_el),
                        ))
                    prev_onset = onset
                    prev_duration = duration
                elif tag == "backup":
                    dur = int(el.findtext("{*}duration") or el.findtext("duration") or "0")
                    position -= dur
                elif tag == "forward":
                    dur = int(el.findtext("{*}duration") or el.findtext("duration") or "0")
                    position += dur

    notes.sort(key=lambda x: (x.start, x.midi))
    return notes


# ---------------------------------------------------------------------------
# Dispatch + conversion to pieces
# ---------------------------------------------------------------------------

def load_notes(path: str) -> list[TimedNote]:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".mid", ".midi"):
        return parse_midi(path)
    if ext in (".xml", ".musicxml", ".mxl"):
        return parse_musicxml(path)
    raise ValueError(f"unsupported file type: {ext} (use .mid/.midi/.xml/.musicxml/.mxl)")


def _group_onsets(notes: list[TimedNote], onset_tolerance: float = 0.03):
    """Group notes that start together into onset clusters."""
    if not notes:
        return []
    groups: list[list[TimedNote]] = [[notes[0]]]
    for note in notes[1:]:
        if note.start - groups[-1][0].start <= onset_tolerance:
            groups[-1].append(note)
        else:
            groups.append([note])
    return groups


def to_chords(notes: list[TimedNote], onset_tolerance: float = 0.03) -> list[list[str]]:
    """Group into a chord-per-onset sequence (all notes of each onset)."""
    chords = []
    for group in _group_onsets(notes, onset_tolerance):
        names = [midi_to_name(m) for m in sorted({n.midi for n in group})]
        chords.append(names)
    return chords


def to_melody(notes: list[TimedNote], onset_tolerance: float = 0.03) -> list[str]:
    """Extract a monophonic melody: the highest note of each onset."""
    melody = []
    for group in _group_onsets(notes, onset_tolerance):
        top = max(group, key=lambda n: n.midi)
        melody.append(midi_to_name(top.midi))
    return melody


def to_piece(path: str, title: str | None = None, key: str | None = None) -> Piece:
    notes = load_notes(path)
    melody = to_melody(notes)
    base = os.path.splitext(os.path.basename(path))[0]
    return Piece(key=key or base, title=title or base, notes=melody)


def to_chord_piece(path: str, title: str | None = None, key: str | None = None) -> ChordPiece:
    notes = load_notes(path)
    chords = to_chords(notes)
    base = os.path.splitext(os.path.basename(path))[0]
    return ChordPiece(key=key or base, title=title or base, chords=chords)
