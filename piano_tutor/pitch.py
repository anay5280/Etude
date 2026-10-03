"""Monophonic pitch (fundamental frequency) detection.

Implements the YIN algorithm [de Cheveigne & Kawahara, 2002] in NumPy.
YIN is a strong, low-latency choice for single-note (monophonic) audio such as
a melody line, which is exactly the MVP scope. For full polyphonic piano
(chords) you would swap this out for an ML transcription model — see README.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .notes import nearest_note, Pitch


@dataclass
class PitchResult:
    """Outcome of analysing one audio frame."""

    pitch: Pitch | None   # None when the frame is silence or unvoiced
    rms: float            # loudness of the frame (root-mean-square amplitude)
    confidence: float     # 0..1, higher is more certain the pitch is real


def rms(frame: np.ndarray) -> float:
    """Root-mean-square amplitude of a frame — a simple loudness measure."""
    if frame.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(frame, dtype=np.float64))))


def _difference_function(x: np.ndarray, max_tau: int) -> np.ndarray:
    """YIN step 1: squared difference d(tau) for each lag tau."""
    d = np.empty(max_tau, dtype=np.float64)
    d[0] = 0.0
    window = x[:max_tau]
    for tau in range(1, max_tau):
        diff = window - x[tau:tau + max_tau]
        d[tau] = np.dot(diff, diff)
    return d


def _cumulative_mean_normalized(d: np.ndarray) -> np.ndarray:
    """YIN step 2: cumulative mean normalized difference d'(tau)."""
    cmnd = np.ones_like(d)
    running = 0.0
    for tau in range(1, len(d)):
        running += d[tau]
        cmnd[tau] = d[tau] * tau / running if running > 0 else 1.0
    return cmnd


def _parabolic_interpolation(cmnd: np.ndarray, tau: int) -> float:
    """Refine the integer lag `tau` to sub-sample precision."""
    if tau <= 0 or tau >= len(cmnd) - 1:
        return float(tau)
    a, b, c = cmnd[tau - 1], cmnd[tau], cmnd[tau + 1]
    denom = a + c - 2.0 * b
    if denom == 0:
        return float(tau)
    return tau + 0.5 * (a - c) / denom


def detect_f0(
    frame: np.ndarray,
    sr: int,
    fmin: float = 55.0,
    fmax: float = 2000.0,
    threshold: float = 0.15,
    rms_gate: float = 0.005,
) -> PitchResult:
    """Estimate the fundamental frequency of one audio frame.

    Returns a PitchResult; `pitch` is None if the frame is too quiet (below
    `rms_gate`) or no confident periodicity is found.
    """
    frame = np.asarray(frame, dtype=np.float64).ravel()
    loudness = rms(frame)
    if loudness < rms_gate:
        return PitchResult(pitch=None, rms=loudness, confidence=0.0)

    max_tau = len(frame) // 2
    min_tau = max(2, int(sr / fmax))
    max_tau = min(max_tau, int(sr / fmin))
    if max_tau <= min_tau + 2:
        return PitchResult(pitch=None, rms=loudness, confidence=0.0)

    d = _difference_function(frame, max_tau)
    cmnd = _cumulative_mean_normalized(d)

    # Absolute-threshold search: first dip below `threshold`, walking to its
    # local minimum. Falls back to the global minimum of the searched range.
    tau = -1
    t = min_tau
    while t < max_tau:
        if cmnd[t] < threshold:
            while t + 1 < max_tau and cmnd[t + 1] < cmnd[t]:
                t += 1
            tau = t
            break
        t += 1

    if tau == -1:
        candidate = int(np.argmin(cmnd[min_tau:max_tau])) + min_tau
        # No clear period found — treat as unvoiced/noisy.
        if cmnd[candidate] >= 0.6:
            return PitchResult(pitch=None, rms=loudness, confidence=0.0)
        tau = candidate

    refined_tau = _parabolic_interpolation(cmnd, tau)
    freq = sr / refined_tau
    if not (fmin <= freq <= fmax):
        return PitchResult(pitch=None, rms=loudness, confidence=0.0)

    confidence = float(max(0.0, 1.0 - cmnd[tau]))
    return PitchResult(pitch=nearest_note(freq), rms=loudness, confidence=confidence)
