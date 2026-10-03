import EtudeCore
import Foundation

// A tiny dependency-free check harness so the ported core can be verified with
// only the Command Line Tools (no Xcode / XCTest). Mirrors EtudeCoreTests.

var passed = 0
var failed = 0

func check(_ condition: Bool, _ label: String) {
    if condition {
        passed += 1
        print("  ok   \(label)")
    } else {
        failed += 1
        print("  FAIL \(label)")
    }
}

func tone(_ freq: Double, _ n: Int, _ sr: Double) -> [Float] {
    (0..<n).map { i in
        let t = Double(i) / sr
        return Float(0.5 * (sin(2 * .pi * freq * t)
                            + 0.3 * sin(2 * .pi * 2 * freq * t)
                            + 0.15 * sin(2 * .pi * 3 * freq * t)))
    }
}

let sr = 44100.0

print("Notes:")
check((21...108).allSatisfy { Notes.nameToMidi(Notes.midiToName($0)) == $0 }, "name<->midi round trip (full piano)")
check(Notes.nameToMidi("C4") == 60 && Notes.nameToMidi("F#3") == 54, "nameToMidi C4/F#3")
check(abs(Notes.midiToFreq(69) - 440.0) < 1e-9, "A4 = 440 Hz")

print("Pitch detection:")
let detector = PitchDetector()
for name in ["C4", "E4", "A4", "C5", "E5"] {
    let midi = Notes.nameToMidi(name)!
    let r = detector.detect(tone(Notes.midiToFreq(Double(midi)), 1024, sr), sampleRate: sr)
    check(r.detected && r.midi == midi && r.clarity > 0.9, "detects \(name) (got \(r.midi.map(Notes.midiToName) ?? "none"), clarity \(String(format: "%.2f", r.clarity)))")
}
check(!detector.detect(tone(130, 1024, sr), sampleRate: sr).detected, "rejects male-voice-range 130 Hz")
check(!detector.detect([Float](repeating: 0, count: 1024), sampleRate: sr).detected, "rejects silence")

print("Segmenter:")
let seg = NoteSegmenter()
var committed: [Int] = []
for m in [60, 60, 60, nil, nil, 60, 60, 60] as [Int?] {
    if let c = seg.feed(m) { committed.append(c) }
}
check(committed == [60, 60], "commits once, repeats after a gap")

print("Score follower:")
let follower = ScoreFollower(["C4", "D4"], advanceOnWrong: false)
let wrong = follower.onNote(Notes.nameToMidi("C#4")!)
check(wrong.status == .wrong && wrong.expectedName == "C4" && follower.pos == 0, "flags wrong note and waits")
check(follower.onNote(Notes.nameToMidi("C4")!).status == .correct && follower.pos == 1, "advances on correct")

print("Guided lesson:")
let lesson = GuidedLesson(["C4", "D4", "E4", "F4"], phraseSize: 2)
check(lesson.prompt().targetName == "C4", "prompts first note")
check(lesson.feed(Notes.nameToMidi("C4")!).kind == .correct, "correct advances")
check(lesson.feed(Notes.nameToMidi("D4")!).kind == .phraseDone, "phrase boundary")
_ = lesson.feed(Notes.nameToMidi("E4")!)
check(lesson.feed(Notes.nameToMidi("F4")!).kind == .lessonDone && lesson.finished, "lesson completes")

print("Chord pieces & follower:")
func midis(_ names: [String]) -> Set<Int> { Set(names.compactMap(Notes.nameToMidi)) }
check(Chords.by("canon")?.chords.first == ["C4", "E4", "G4"], "built-in chord piece")
let poly = PolyScoreFollower(Chords.by("pop_progression")!.chords)
check(poly.onChord(midis(["C4", "E4", "G4"])).status == .correct, "correct chord advances")
check(poly.onChord(midis(["G3", "B3", "D4"])).status == .correct, "second chord correct")
let badChord = poly.onChord(midis(["A3", "C4", "F4"]))   // expected A3 C4 E4
check(badChord.status == .wrong && badChord.missingNames == ["E4"] && badChord.extraNames == ["F4"],
      "wrong chord reports missing E4 / extra F4")

print("Streak:")
var st = StreakState()
st = Streak.recording(st, today: 100)          // first practice
check(st.current == 1 && st.best == 1, "first practice starts streak at 1")
st = Streak.recording(st, today: 100)          // same day again
check(st.current == 1, "same-day practice doesn't double-count")
st = Streak.recording(st, today: 101)          // next day
check(st.current == 2 && st.best == 2, "consecutive day extends streak")
st = Streak.recording(st, today: 103)          // skipped day 102
check(st.current == 1 && st.best == 2, "a gap resets current, keeps best")
check(Streak.displayCurrent(st, today: 103) == 1, "display shows streak on the practice day")
check(Streak.displayCurrent(st, today: 104) == 1, "display still valid the next day")
check(Streak.displayCurrent(st, today: 105) == 0, "display shows 0 once the streak is broken")
let d0 = Streak.dayIndex(Date())
let d1 = Streak.dayIndex(Date().addingTimeInterval(86400))
check(d1 == d0 + 1, "dayIndex advances by 1 across a day")

print("Importer (MIDI / MusicXML / MXL):")
// Fixtures live in ../tests/fixtures relative to the package root.
let fixtures = URL(fileURLWithPath: #filePath)
    .deletingLastPathComponent()   // EtudeVerify
    .deletingLastPathComponent()   // Sources
    .deletingLastPathComponent()   // ios
    .deletingLastPathComponent()   // piano_tutor
    .appendingPathComponent("tests/fixtures")
func melody(_ file: String) -> [String] {
    (try? Importer.toMelody(Importer.loadNotes(path: fixtures.appendingPathComponent(file).path))) ?? []
}
func chords(_ file: String) -> [[String]] {
    (try? Importer.toChords(Importer.loadNotes(path: fixtures.appendingPathComponent(file).path))) ?? []
}
check(melody("scale.mid") == ["C4", "D4", "E4", "F4", "G4"], "MIDI melody (scale.mid)")
check(chords("chords.mid") == [["C4", "E4", "G4"], ["G3", "B3", "D4"]], "MIDI chords (chords.mid)")
check(melody("melody.musicxml") == ["C4", "D4", "E4", "F#4", "G4"], "MusicXML melody + sharp")
check(chords("melody.musicxml").last == ["C4", "E4", "G4"], "MusicXML chord grouping")
check(melody("melody.mxl") == melody("melody.musicxml"), "MXL (zip) matches plain MusicXML")
// The exact path the app's document picker uses: load from Data + extension.
if let data = try? Data(contentsOf: fixtures.appendingPathComponent("melody.mxl")),
   let notes = try? Importer.loadNotes(data: data, ext: "mxl") {
    check(Importer.toMelody(notes) == ["C4", "D4", "E4", "F#4", "G4"], "loadNotes(data:ext:) — the UI import path")
} else {
    check(false, "loadNotes(data:ext:) — the UI import path")
}

print("\n\(passed) passed, \(failed) failed")
exit(failed == 0 ? 0 : 1)
