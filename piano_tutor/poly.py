"""Polyphonic pitch detection — estimate the set of notes in a chord.

Classical DSP approach (no ML dependencies): harmonic-salience estimation with
iterative spectral subtraction, in the spirit of Klapuri's multi-pitch method.

    1. Take the magnitude spectrum of the frame.
    2. For every candidate piano note, score how much spectral energy sits at
       its harmonic series (weighted toward the fundamental).
    3. Pick the strongest candidate, record it, and subtract (zero out) its
       harmonics from the spectrum so it can't be re-picked as an octave.
    4. Repeat until the next-best note is too weak, or a note limit is hit.

Honest limits: this works well on clean tones/chords and is great for proving
the pipeline, but it is sensitive to timbre, reverb and noise on real
recordings, and can still make octave/fifth errors. The production upgrade is a
neural transcriber (Spotify basic-pitch, Magenta Onsets & Frames) exposed
through this exact `detect_chord` interface. See README.
"""

from __future__ import annotations

import numpy as np

from .notes import midi_to_freq, midi_to_name, nearest_note, Pitch
from .pitch import rms

# Candidate range: C2 (36) .. C7 (96) covers the vast majority of piano melody
# and chord voicings while keeping the search cheap.
MIN_MIDI = 36
MAX_MIDI = 96
N_HARMONICS = 8


def _spectrum(frame: np.ndarray, sr: int, zero_pad: int = 4):
    """Windowed magnitude spectrum and its frequency-bin spacing."""
    n = len(frame)
    windowed = frame * np.hanning(n)
    nfft = int(2 ** np.ceil(np.log2(max(n * zero_pad, 1))))
    spec = np.abs(np.fft.rfft(windowed, nfft))
    df = sr / nfft
    return spec, df


def _mag_near(spec: np.ndarray, center_bin: int, half: int = 2) -> float:
    """Peak magnitude in a small window around a bin (tolerates leakage)."""
    lo = max(0, center_bin - half)
    hi = min(len(spec), center_bin + half + 1)
    if lo >= hi:
        return 0.0
    return float(spec[lo:hi].max())


def _salience(spec: np.ndarray, df: float, f0: float,
              n_harmonics: int = N_HARMONICS) -> float:
    """Weighted sum of spectral energy along a note's harmonic series.

    The 1/h weighting favors the true fundamental over its sub-octave (which
    would otherwise share the upper harmonics).
    """
    total = 0.0
    for h in range(1, n_harmonics + 1):
        b = int(round(h * f0 / df))
        if b >= len(spec):
            break
        total += _mag_near(spec, b) / h
    return total


def _subtract_harmonics(spec: np.ndarray, df: float, f0: float,
                        n_harmonics: int = N_HARMONICS, half: int = 2) -> None:
    """Zero out the harmonics of f0 so it can't be re-selected."""
    for h in range(1, n_harmonics + 1):
        b = int(round(h * f0 / df))
        if b >= len(spec):
            break
        lo = max(0, b - half)
        hi = min(len(spec), b + half + 1)
        spec[lo:hi] = 0.0


def detect_chord(
    frame: np.ndarray,
    sr: int,
    max_notes: int = 6,
    rel_threshold: float = 0.12,
    rms_gate: float = 0.005,
    fundamental_floor: float = 0.1,
) -> list[Pitch]:
    """Estimate the set of notes sounding in one audio frame.

    Returns a list of Pitch objects (possibly empty), sorted low to high.

    A candidate is only eligible if it has real energy at its own fundamental
    (checked against the original spectrum). This suppresses the octave /
    sub-harmonic ghosts that plague naive harmonic-salience methods.
    """
    frame = np.asarray(frame, dtype=np.float64).ravel()
    if rms(frame) < rms_gate:
        return []

    orig, df = _spectrum(frame, sr)
    spec = orig.copy()
    peak = float(orig.max()) if orig.size else 0.0
    if peak <= 0.0:
        return []

    def fundamental_present(f0: float) -> bool:
        center = _mag_near(orig, int(round(f0 / df)), half=1)
        if center < fundamental_floor * peak:
            return False
        # Must be a local maximum vs. its one-semitone neighbours, so the
        # spectral skirt of a strong note doesn't register as its own pitch.
        down = _mag_near(orig, int(round(f0 * 2 ** (-1 / 12) / df)), half=0)
        up = _mag_near(orig, int(round(f0 * 2 ** (1 / 12) / df)), half=0)
        return center >= down and center >= up

    candidates = [(m, midi_to_freq(m)) for m in range(MIN_MIDI, MAX_MIDI + 1)
                  if fundamental_present(midi_to_freq(m))]
    picked: list[int] = []
    first_salience: float | None = None

    for _ in range(max_notes):
        best_midi, best_sal = None, 0.0
        for midi, f0 in candidates:
            if midi in picked:
                continue
            sal = _salience(spec, df, f0)
            if sal > best_sal:
                best_sal, best_midi = sal, midi

        if best_midi is None or best_sal <= 0.0:
            break
        if first_salience is None:
            first_salience = best_sal
        elif best_sal < rel_threshold * first_salience:
            break

        picked.append(best_midi)
        _subtract_harmonics(spec, df, midi_to_freq(best_midi))

    return [nearest_note(midi_to_freq(m)) for m in sorted(picked)]


def midi_set(pitches: list[Pitch]) -> frozenset[int]:
    """Convenience: the set of MIDI note numbers from a detected chord."""
    return frozenset(p.midi for p in pitches)
