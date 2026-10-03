"""Microphone + speaker helper built on `sounddevice`.

Provides a small context-managed object that streams mic audio as analysis
frames and can play reference tones back to the learner. sounddevice is imported
lazily so the rest of the project keeps working without it.
"""

from __future__ import annotations

import queue

import numpy as np


class MicUnavailableError(RuntimeError):
    def __init__(self, detail: str = "") -> None:
        super().__init__(
            "Microphone mode needs the 'sounddevice' package.\n"
            "  pip install sounddevice\n"
            + (f"(import failed: {detail})" if detail else "")
        )


class MicPiano:
    """Stream mic audio as frames and play tones. Use as a context manager.

        with MicPiano(sr) as mic:
            mic.play(reference_audio)
            for frame in mic.frames():
                ...
    """

    def __init__(self, sr: int = 22050, frame: int = 2048, hop: int = 512):
        try:
            import sounddevice as sd
        except Exception as exc:  # noqa: BLE001
            raise MicUnavailableError(str(exc)) from exc
        self._sd = sd
        self.sr = sr
        self.frame = frame
        self.hop = hop
        self._q: "queue.Queue[np.ndarray]" = queue.Queue()
        self._buf = np.zeros(0, dtype=np.float64)
        self._stream = None

    def __enter__(self) -> "MicPiano":
        def callback(indata, frames, time_info, status):  # noqa: ANN001
            self._q.put(indata[:, 0].copy())

        self._stream = self._sd.InputStream(
            samplerate=self.sr, channels=1, dtype="float32",
            blocksize=self.hop, callback=callback,
        )
        self._stream.start()
        return self

    def __exit__(self, *exc) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()

    def play(self, audio: np.ndarray) -> None:
        """Play audio through the speakers and block until it finishes."""
        self._sd.play(np.asarray(audio, dtype=np.float32), self.sr)
        self._sd.wait()

    def flush(self) -> None:
        """Discard buffered/pending audio (e.g. after playing a reference tone),
        so the learner's own playing is what gets analysed next."""
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass
        self._buf = np.zeros(0, dtype=np.float64)

    def frames(self):
        """Yield fixed-size analysis frames from the live mic stream."""
        while True:
            chunk = self._q.get()
            self._buf = np.concatenate([self._buf, chunk.astype(np.float64)])
            while len(self._buf) >= self.frame:
                yield self._buf[:self.frame]
                self._buf = self._buf[self.hop:]
