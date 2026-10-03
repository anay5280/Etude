# Piano Note Tutor (Python prototype)

**Teaches** you a piano piece step by step, then listens as you play, detects
each note, and tells you **which note is wrong, what you played, and how to fix
it.**

This is the **prototype brain** — the data-science / AI core — built in Python
so the concept can be proven fast. It is *not* the App Store app yet; see
[Road to the App Store](#road-to-the-app-store) below for how this becomes one.

> **What this is vs. Shazam.** Shazam *identifies* an unknown song by
> fingerprint-matching against a database. This app instead already knows the
> piece and does **real-time pitch detection + score-following**: it tracks
> which note you're on and flags deviations. Different, and more useful for
> practice.

---

## Quick start (no microphone or piano needed)

```bash
cd piano_tutor
python3 -m venv .venv
source .venv/bin/activate
pip install numpy            # the whole core runs on just numpy

python demo.py               # synthesizes a piece with one planted wrong note
python demo.py ode_to_joy    # try another built-in piece
```

The demo synthesizes a performance that is perfect except for one deliberately
wrong note, runs the full pipeline, and prints per-note feedback like:

```
[5/42] ✗ Wrong note: you played A#4, but note 5 should be A4. You're 1 semitone
        too high. Move down 1 key on the keyboard to reach A4. A4 is a white key.
```

## Import real songs (MIDI / MusicXML)

Don't want to hand-type melodies? Import any `.mid`, `.midi`, `.xml`,
`.musicxml`, or compressed `.mxl` file. Parsing uses **only the Python standard
library** — no extra dependencies.

```bash
python import_song.py song.mid            # melody + chord summary
python import_song.py song.musicxml --chords
python learn.py song.mid --simulate       # learn an imported song (file path works anywhere a piece key does)
```

`piano_tutor/importer.py` converts a file into either a **melody** (top note of
each onset, for the note-by-note lesson) or a **chord sequence** (all notes of
each onset, for the polyphonic path).

> **Melody-extraction limit (honest):** the melody is taken as the highest note
> at each onset. That's exact for monophonic files and lead sheets, and for
> arrangements where the melody sits above aligned chords. For dense multi-voice
> pieces where an inner/bass voice has its own offbeat onsets, the extracted top
> line can pick up a stray note — use the `--chords` view, or a melody-only
> track, for those. Proper voice separation is a future upgrade.

## Visual UI (web) — "Etude"

A polished, self-contained web interface: a piano keyboard and a note-track that
light up **green (correct) / red (wrong)** as you play, with the same three
modes (Demonstrate / Learn / Practice) as the Python engine.

```bash
cd web
python3 -m http.server 8777      # then open http://localhost:8777
```

- **Two input methods:** click the keys with the mouse (works anywhere), or turn
  on **Mic** for live pitch detection (a JS port of the detection approach —
  serve over `localhost` so the browser grants microphone access).
- **Learn mode** prompts each note, glows the target key in brass, and on a miss
  shows the correction ("You're 2 semitones too high — move down 2 keys to C4").
- Light + dark themes, fully responsive, no dependencies (single HTML file).

This UI doubles as the **design reference for the eventual iOS app**. Live at
[web/index.html](web/index.html).

## Learn a piece (the lesson flow)

Teaching comes first. `learn.py` walks you through a piece in three phases:

1. **Demonstrate** — the piece is played so you hear it.
2. **Guided** — note-by-note call-and-response: it shows and plays the next
   note, waits for you to play it back, and only advances when you're right
   (with a correction hint on a miss). Taught phrase by phrase.
3. **Practice** — you play the whole piece and get graded.

```bash
python learn.py twinkle --simulate    # walk through the whole flow, NO mic needed
python learn.py twinkle               # the real lesson (needs a mic + sounddevice)
python learn.py ode_to_joy --phrase 4 # notes per phrase in the guided phase
python learn.py --list                # pieces you can learn
```

The `--simulate` run prints exactly what a learner would see and do:

```
=== Phase 2 · Guided — note by note ===
-- Phrase 1: C4 C4 G4 G4 --
Play C4 (a white key).
Correct — C4!
...
Nice — G4! Phrase 1 complete.
```

### Chords too (polyphonic)

```bash
python demo_poly.py                  # a chord progression with one wrong note
python demo_poly.py pop_progression
```

Detects **multiple notes at once** and pinpoints the wrong note *inside* a chord:

```
[3/8] ✗ Wrong chord 3: expected A3 C4 E4, you played A3 C4 F4.
       F4 → You're 1 semitone too high. Move down 1 key to reach E4.
```

## Run the tests

```bash
python -m unittest discover -s tests -v
```

## Practice live from your microphone

```bash
pip install sounddevice      # only needed for live mode
python live.py               # defaults to Twinkle
python live.py fur_elise
python live.py --list        # see all pieces
```

Play the melody one note at a time on a real (or digital) piano near your mic.

## Analyze a recording (offline)

Two engines are available for recordings:

```bash
# Classical DSP (numpy only) — fast, good on clean audio:
python analyze_file.py my_recording.wav twinkle

# Neural model (Spotify basic-pitch) — accurate on REAL piano recordings:
.venv310/bin/python analyze_neural.py my_recording.wav canon
.venv310/bin/python analyze_neural.py my_recording.wav twinkle --raw   # just the transcription
```

### The neural engine (basic-pitch)

`analyze_neural.py` uses [**basic-pitch**](https://github.com/spotify/basic-pitch),
Spotify's open-source neural transcriber — the production-grade path for real
recordings (it handles piano timbre, reverb and pedal far better than classical
DSP). It transcribes the whole file into time-stamped notes, which
`piano_tutor/neural.py` groups into chords/onsets and follows against the piece.

It needs a neural runtime (ONNX/CoreML/TensorFlow), which lacks wheels for the
newest Python. Install it under Python 3.10:

```bash
python3.10 -m venv .venv310
.venv310/bin/pip install -r requirements-neural.txt
.venv310/bin/python analyze_neural.py my_recording.wav canon
```

The rest of the app is unaffected and still runs on numpy alone.

> **Live vs. recorded, by design.** basic-pitch is offline (it needs the whole
> recording), so it powers *recording analysis*. The classical YIN/`poly.py`
> detectors stay for *low-latency live* feedback. This mono-vs-neural split is
> the same architecture you'd ship: fast on-device detection for real-time,
> heavier model for detailed after-the-fact review.

---

## How it works

```
mic / wav / synth  ─►  YIN pitch detection  ─►  note segmenter  ─►  score follower  ─►  feedback
   (audio frames)      (freq → nearest note)    (debounce onsets)   (compare to piece)   (correction)
```

| Module | Role |
| --- | --- |
| `piano_tutor/notes.py` | Frequency ↔ MIDI ↔ note-name math (A4 = 440 Hz). |
| `piano_tutor/pitch.py` | **YIN** monophonic fundamental-frequency detector, in NumPy. |
| `piano_tutor/poly.py` | **Polyphonic** chord detector: harmonic salience + iterative subtraction. |
| `piano_tutor/neural.py` | **Neural** transcription adapter (Spotify basic-pitch) for real recordings. |
| `piano_tutor/pieces.py` | Built-in melodies and chord progressions. |
| `piano_tutor/follower.py` | Judges played notes/chords against the score, with correction hints. |
| `piano_tutor/lesson.py` | The teaching state machine (demonstrate → guided → practice). |
| `piano_tutor/importer.py` | MIDI + MusicXML import (standard library only). |
| `piano_tutor/miclisten.py` | Mic capture + tone playback helper (sounddevice). |
| `piano_tutor/session.py` | Wires the pipeline together; shared by all entry points. |
| `piano_tutor/synth.py` | Tiny tone/chord synth so the whole thing is testable without hardware. |

### How polyphonic detection works

`poly.py` estimates the *set* of notes in a frame with classical DSP (no ML):

1. Take the magnitude spectrum (FFT).
2. Score each candidate piano note by the energy along its harmonic series,
   weighted toward the fundamental.
3. Only allow candidates that have real energy at their **own fundamental** and
   are a local spectral peak — this kills the octave/sub-harmonic ghosts that
   wreck naive methods.
4. Pick the strongest note, subtract its harmonics, repeat.

### Scope and honesty about limits

* **Monophonic melodies** (YIN) are accurate and low-latency.
* **Polyphonic chords** (`poly.py`) work well on clean tones across the C3–C5
  register — see the demo — but classical DSP is inherently sensitive to timbre,
  reverb and noise on real recordings, and still makes some errors when two
  notes are exactly an octave apart (one masks the other's harmonics).
* The production-grade "AI" upgrade is a **neural transcriber** (Spotify
  **basic-pitch**, Google Magenta **Onsets & Frames**) exposed through the same
  `detect_chord()` interface. `poly.py` proves the pipeline and integration; the
  neural model swaps in for accuracy on real audio.

---

## Where the AI / data science grows next

1. **Polyphonic transcription.** ✅ Done two ways: a classical detector
   (`poly.py`) for live chords, and the **neural basic-pitch** model
   (`neural.py`, via `analyze_neural.py`) for accurate transcription of real
   recordings. Next accuracy step: run the neural model on short rolling buffers
   for *real-time* polyphony, or fine-tune it on piano-only data.
2. **Robust score-following / alignment.** Replace the simple in-order follower
   with online DTW (dynamic time warping) so it survives skipped notes, wrong
   rhythm, and repeats.
3. **Rhythm & timing feedback**, not just pitch — detect notes played early/late
   or held too short.
4. **A library of real pieces** imported from MusicXML / MIDI instead of
   hand-typed note lists.

## Road to the App Store

**The iOS app scaffold now exists** — see [ios/](ios/). The portable "brain" is
ported to a Swift package (`EtudeCore`) that is compiled and unit-verified
(`cd ios && swift run EtudeVerify` → 17 checks pass), with a SwiftUI +
AVAudioEngine app layer on top and an XcodeGen spec to generate the Xcode
project. See [ios/README.md](ios/README.md) for build steps and the Core ML plan.

Python can't ship directly to the iOS App Store, so the usual path is:

1. **Prototype the brain in Python** ✅ *(this repo)* — prove detection + feedback.
2. **Train / choose the model**, then export it to **Core ML** (Apple's on-device
   ML format) so it runs offline on iPhone with low latency. Conveniently,
   basic-pitch already ships a **Core ML** version of its model — a ready bridge
   to iOS.
3. **Build the iOS app in Swift** — capture mic audio with **AVAudioEngine**, run
   pitch/transcription on-device, render sheet music and live feedback.
   (AudioKit is a helpful Swift audio library.)
4. **Design the UX**: pick a song → see the score → play → notes light up green
   (correct) / red (wrong) with the fix, plus a progress score.
5. **Submit**: enroll in the Apple Developer Program ($99/yr), pass App Review.

> Reusing the exact Python at runtime on iOS is possible (e.g. Kivy/BeeWare) but
> not recommended for real-time audio — native Swift + Core ML is the reliable
> route. The Python here stays valuable as the reference implementation and for
> training/validating the model.

## Project layout

```
piano_tutor/
├── README.md
├── requirements.txt
├── web/index.html     # VISUAL UI — interactive keyboard + note-track (Etude)
├── import_song.py     # import + inspect a MIDI/MusicXML file
├── learn.py           # LESSON flow: demonstrate → guided → practice
├── demo.py            # no-mic melody demo (start here)
├── demo_poly.py       # no-mic chord (polyphonic) demo
├── live.py            # real-time microphone practice (melodies and chords)
├── analyze_file.py    # analyze a recorded WAV (classical DSP)
├── analyze_neural.py  # analyze a recorded WAV (neural basic-pitch)
├── requirements-neural.txt
├── piano_tutor/       # the package (importable core)
├── ios/               # native iOS app scaffold (Swift/SwiftUI + EtudeCore)
└── tests/             # unit tests
```
