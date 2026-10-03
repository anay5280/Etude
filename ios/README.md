# Etude for iOS (Swift / SwiftUI scaffold)

The native iOS app skeleton — the first real step toward the App Store. It
reuses the same "brain" as the Python and web versions, now written in Swift and
running **on-device**.

```
ios/
├── Package.swift              # EtudeCore Swift package (the portable brain)
├── Sources/EtudeCore/         # Notes, PitchDetector, Pieces, ScoreFollower, GuidedLesson, Importer
├── Sources/EtudeVerify/       # dependency-free checker (runs without Xcode)
├── Tests/EtudeCoreTests/      # XCTest suite (runs under full Xcode)
├── App/                       # the SwiftUI iOS app (links EtudeCore)
│   ├── EtudeApp.swift         # @main
│   ├── ContentView.swift      # the UI (mirrors the Etude web design)
│   ├── PianoKeyboardView.swift
│   ├── SessionModel.swift     # drives the 3 modes
│   ├── AudioEngine.swift      # AVAudioEngine mic capture -> PitchDetector
│   ├── AudioRecorder.swift    # records audio for neural transcription
│   ├── NeuralTranscriber.swift# basic-pitch Core ML transcription
│   ├── TonePlayer.swift       # note / chord playback
│   ├── OnboardingView.swift   # first-launch intro
│   └── Assets.xcassets/       # app icon (brass treble clef)
└── project.yml                # XcodeGen spec -> Etude.xcodeproj
```

## What's verified vs. what isn't

**`EtudeCore` is real, compiled, and tested** — the note math, pitch detection
(the voice-rejecting NSDF detector from the web fix), score follower and lesson
state machine. It has no UIKit/AVFoundation dependency, so it builds with just
the Command Line Tools:

```bash
cd ios
swift run EtudeVerify     # 35 checks: detection, follower, lesson, chords, import, streak  -> "35 passed"
```

**The SwiftUI app has been built and launched in the iOS Simulator** (Xcode 26,
iOS 17) — it compiles, bundles the Core ML model (`nmp.mlmodelc`), and renders
the keyboard/lesson UI. See the build recipe below.

## Build & run the app

Needs **Xcode** (not just Command Line Tools) and **XcodeGen**. The simplest path:

```bash
brew install xcodegen           # one time
cd ios
xcodegen generate               # creates Etude.xcodeproj
open Etude.xcodeproj            # then pick a simulator / device and Run
```

This project has been **built and run in the iOS Simulator** with this recipe
(Xcode 26, iOS 17 target). If your active developer dir points at the Command
Line Tools, prefix commands with `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer`
(or `sudo xcode-select -s` it once). Headless build + run without opening Xcode:

```bash
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
xcodegen generate
xcodebuild -project Etude.xcodeproj -target Etude -sdk iphonesimulator \
           -configuration Debug CODE_SIGNING_ALLOWED=NO build      # -> ** BUILD SUCCEEDED **
xcrun simctl boot "iPhone 16 Pro"
xcrun simctl install booted build/Debug-iphonesimulator/Etude.app
xcrun simctl launch booted com.example.etude
```

(No XcodeGen? Create a new iOS App in Xcode, drag in `App/` and add `Package.swift`
as a local package dependency, and set the microphone usage string — below.)

The app needs the microphone permission string `NSMicrophoneUsageDescription`
(XcodeGen sets it from `project.yml`). Mic capture only works on a real device or
a simulator with an input source.

## How it maps to the other versions

| Concept | Python | Web (JS) | iOS (Swift) |
| --- | --- | --- | --- |
| Note math | `notes.py` | inline | `Notes.swift` |
| Live pitch detection | `pitch.py` (YIN) | `detectPitch` (NSDF) | `PitchDetector.swift` (NSDF) |
| Wrong-note + hints | `follower.py` | inline | `ScoreFollower.swift` |
| Chord follow (poly) | `follower.py` | inline | `PolyScoreFollower.swift` |
| Teaching flow | `lesson.py` | inline | `GuidedLesson.swift` + `SessionModel` |
| Song import | `importer.py` | — | `Importer.swift` (MIDI/MusicXML/MXL) |
| UI | terminal | `web/index.html` | SwiftUI `ContentView` |

The Swift `PitchDetector` is a line-for-line port of the detector we tuned and
verified in the browser, so talking is rejected and fast playing keeps up — now
compiled and unit-checked in Swift too.

## Core ML — polyphonic transcription (basic-pitch)

Live monophonic detection runs natively via `PitchDetector`. For full
**polyphonic** transcription (chords), the app uses Spotify's basic-pitch
**Core ML** model. This is wired up:

- **The model is in the project:** [App/Models/nmp.mlpackage](App/Models/nmp.mlpackage).
  XcodeGen bundles it; Xcode compiles it to `nmp.mlmodelc` at build time.
- **The transcriber is written:** [App/NeuralTranscriber.swift](App/NeuralTranscriber.swift)
  loads the model, windows audio into the model's 43844-sample (~2 s @ 22050 Hz)
  input, runs inference, and reads the note/onset outputs — producing EtudeCore
  `TimedNote`s that feed `Importer.toMelody` / `toChords` just like an imported file.

The model's I/O and this code were **verified against the real model** (in
Python): `input_2` [1,43844,1] → `Identity_1` note / `Identity_2` onset
[1,172,88], key bin `k` → MIDI `21+k`. Running the exact extraction logic on the
model's output for a C4→E4→G4 recording recovers `["C4","E4","G4"]` with correct
timings.

Because Xcode isn't on this machine, the model can't be compiled/run here — that
happens on your Xcode build. To finish:
1. `xcodegen generate && open Etude.xcodeproj` (the model is already in the target).
2. Add a record button that feeds captured audio to `NeuralTranscriber.transcribe(...)`.
3. For chord practice, port `poly.py`'s chord follower, or use `Importer.toChords`
   on the transcription — the shared `TimedNote` type makes it a drop-in.

Same fast-native-for-live / neural-for-accuracy split as the desktop version,
running offline on-device.

## Status & next steps toward the App Store

- [x] Portable core in Swift, compiled + verified
- [x] SwiftUI app scaffold (keyboard, 3 modes, mic capture)
- [ ] Build/run in Xcode on a device (needs Xcode on your machine)
- [x] MIDI/MusicXML/MXL import ported to `Importer.swift` (verified against fixtures)
- [x] Import wired into the UI (`.fileImporter` document picker → `SessionModel.importSong`)
- [x] Core ML model bundled + `NeuralTranscriber` written (I/O verified vs. the real model)
- [x] **Built and launched in the iOS Simulator** (compiles, model bundled, UI renders)
- [x] Record → `NeuralTranscriber` button (record, transcribe, becomes a piece)
- [x] **Polyphonic chord practice** — `PolyScoreFollower` + chord pieces, tap-to-build-a-chord input, Demonstrate/Learn/Practice (built & rendered in the sim)
- [x] **App icon** (brass treble clef) and **first-launch onboarding** (built; icon shows on the home screen)
- [x] **Daily practice streak** — flame badge in the header; completing a Learn/Practice session each day builds/keeps the streak (logic in `EtudeCore/Streak.swift`, verified)
- [ ] iCloud/Files song library, real-device testing, Apple Developer enrollment + App Review

See **[RELEASE.md](RELEASE.md)** for the step-by-step App Store submission checklist
(signing, privacy manifest, screenshots, App Review notes).
- [ ] Apple Developer Program enrollment ($99/yr) + App Review submission
