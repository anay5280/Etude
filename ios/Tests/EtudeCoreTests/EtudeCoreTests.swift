import XCTest
@testable import EtudeCore

final class EtudeCoreTests: XCTestCase {

    // Piano-like tone with a few harmonics.
    private func tone(_ freq: Double, _ n: Int, _ sr: Double) -> [Float] {
        (0..<n).map { i in
            let t = Double(i) / sr
            let v = 0.5 * (sin(2 * .pi * freq * t)
                           + 0.3 * sin(2 * .pi * 2 * freq * t)
                           + 0.15 * sin(2 * .pi * 3 * freq * t))
            return Float(v)
        }
    }

    // MARK: Notes

    func testNoteRoundTrip() {
        for m in 21...108 {
            XCTAssertEqual(Notes.nameToMidi(Notes.midiToName(m)), m)
        }
        XCTAssertEqual(Notes.nameToMidi("C4"), 60)
        XCTAssertEqual(Notes.nameToMidi("F#3"), 54)
        XCTAssertEqual(Notes.midiToName(69), "A4")
    }

    func testFreqConversion() {
        XCTAssertEqual(Notes.midiToFreq(69), 440.0, accuracy: 1e-9)
        XCTAssertEqual(Notes.freqToMidi(440.0), 69.0, accuracy: 1e-9)
    }

    // MARK: Pitch detection (the fix we shipped in the web UI, ported)

    func testDetectsPianoNotes() {
        let sr = 44100.0
        let detector = PitchDetector()
        for name in ["C4", "E4", "A4", "C5", "E5"] {
            let midi = Notes.nameToMidi(name)!
            let buf = tone(Notes.midiToFreq(Double(midi)), 1024, sr)
            let result = detector.detect(buf, sampleRate: sr)
            XCTAssertTrue(result.detected, "should detect \(name)")
            XCTAssertEqual(result.midi, midi, "wrong note for \(name)")
            XCTAssertGreaterThan(result.clarity, 0.9)
        }
    }

    func testRejectsVoiceAndSilence() {
        let sr = 44100.0
        let detector = PitchDetector()
        // Male-voice-range fundamental sits below the keyboard band -> rejected.
        let lowVoice = tone(130, 1024, sr)
        XCTAssertFalse(detector.detect(lowVoice, sampleRate: sr).detected)
        // Silence -> rejected.
        let silence = [Float](repeating: 0, count: 1024)
        XCTAssertFalse(detector.detect(silence, sampleRate: sr).detected)
    }

    func testSegmenterCommitsOnceThenRepeatsAfterGap() {
        let seg = NoteSegmenter()
        var out: [Int] = []
        for m in [60, 60, 60, nil, nil, 60, 60, 60] as [Int?] {
            if let c = seg.feed(m) { out.append(c) }
        }
        XCTAssertEqual(out, [60, 60])
    }

    // MARK: Score follower

    func testFollowerCorrectAndWrong() {
        let f = ScoreFollower(["C4", "D4"], advanceOnWrong: false)
        let wrong = f.onNote(Notes.nameToMidi("C#4")!)
        XCTAssertEqual(wrong.status, .wrong)
        XCTAssertEqual(wrong.expectedName, "C4")
        XCTAssertEqual(f.pos, 0)  // waits for the correct note
        let right = f.onNote(Notes.nameToMidi("C4")!)
        XCTAssertEqual(right.status, .correct)
        XCTAssertEqual(f.pos, 1)
    }

    // MARK: Guided lesson

    func testLessonAdvancesAndCompletes() {
        let lesson = GuidedLesson(["C4", "D4", "E4", "F4"], phraseSize: 2)
        XCTAssertEqual(lesson.prompt().targetName, "C4")
        XCTAssertEqual(lesson.feed(Notes.nameToMidi("C4")!).kind, .correct)
        XCTAssertEqual(lesson.feed(Notes.nameToMidi("D4")!).kind, .phraseDone)
        _ = lesson.feed(Notes.nameToMidi("E4")!)
        let last = lesson.feed(Notes.nameToMidi("F4")!)
        XCTAssertEqual(last.kind, .lessonDone)
        XCTAssertTrue(lesson.finished)
        XCTAssertEqual(lesson.correctCount, 4)
    }

    // MARK: Importer (validated against the same fixtures as the Python version)

    private var fixtures: URL {
        URL(fileURLWithPath: #filePath)          // EtudeCoreTests.swift
            .deletingLastPathComponent()          // EtudeCoreTests
            .deletingLastPathComponent()          // Tests
            .deletingLastPathComponent()          // ios
            .deletingLastPathComponent()          // piano_tutor
            .appendingPathComponent("tests/fixtures")
    }

    func testImportMidiMelody() throws {
        let notes = try Importer.loadNotes(path: fixtures.appendingPathComponent("scale.mid").path)
        XCTAssertEqual(Importer.toMelody(notes), ["C4", "D4", "E4", "F4", "G4"])
    }

    func testImportMidiChords() throws {
        let notes = try Importer.loadNotes(path: fixtures.appendingPathComponent("chords.mid").path)
        XCTAssertEqual(Importer.toChords(notes), [["C4", "E4", "G4"], ["G3", "B3", "D4"]])
    }

    func testImportMusicXML() throws {
        let notes = try Importer.loadNotes(path: fixtures.appendingPathComponent("melody.musicxml").path)
        XCTAssertEqual(Importer.toMelody(notes), ["C4", "D4", "E4", "F#4", "G4"])
        XCTAssertEqual(Importer.toChords(notes).last, ["C4", "E4", "G4"])
    }

    func testImportMXLZip() throws {
        let plain = Importer.toMelody(try Importer.loadNotes(path: fixtures.appendingPathComponent("melody.musicxml").path))
        let zipped = Importer.toMelody(try Importer.loadNotes(path: fixtures.appendingPathComponent("melody.mxl").path))
        XCTAssertEqual(plain, zipped)
    }
}
