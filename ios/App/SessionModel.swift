import Foundation
import SwiftUI
import Combine
import AVFoundation
import EtudeCore

/// Drives the lesson experience for the SwiftUI views. Handles both monophonic
/// melodies (`GuidedLesson` / `ScoreFollower`) and polyphonic chord pieces
/// (`PolyScoreFollower`), routing played notes from key taps or the mic.
@MainActor
final class SessionModel: ObservableObject {
    enum Mode: String, CaseIterable, Identifiable {
        case demonstrate = "Demonstrate", learn = "Learn", practice = "Practice"
        var id: String { rawValue }
    }
    enum StatusKind { case neutral, correct, wrong, target }
    struct Flash: Equatable { let midi: Int; let correct: Bool }

    /// A selectable program: a monophonic melody or a chord progression.
    enum Program: Hashable, Identifiable {
        case melody(Piece)
        case chords(ChordPiece)

        var id: String {
            switch self { case .melody(let p): return p.id; case .chords(let c): return c.id }
        }
        var title: String {
            switch self {
            case .melody(let p): return p.title
            case .chords(let c): return "\(c.title) · chords"
            }
        }
        var isChords: Bool { if case .chords = self { return true }; return false }
        var notes: [String] { if case .melody(let p) = self { return p.notes }; return [] }
        var chords: [[String]] { if case .chords(let c) = self { return c.chords }; return [] }
        var count: Int { isChords ? chords.count : notes.count }
    }

    @Published var programs: [Program] =
        Pieces.all.map(Program.melody) + Chords.all.map(Program.chords)
    @Published var program: Program = .melody(Pieces.all[0])
    @Published var mode: Mode = .learn
    @Published var running = false

    @Published var importMessage: String?
    @Published var isRecording = false
    @Published var isTranscribing = false

    @Published var eyebrow = "Learn · ready"
    @Published var status = "Press Start to begin the lesson."
    @Published var detail = "Tap the keys, or turn on the mic."
    @Published var statusKind: StatusKind = .neutral

    /// Keys to glow (target). One note in melody mode, a chord in chord mode.
    @Published var targets: Set<Int> = []
    /// Keys tapped into the current pending chord (chord mode).
    @Published var armed: Set<Int> = []
    @Published var flash: Flash?
    @Published var pos = 0
    @Published var correct = 0
    @Published var wrong = 0
    @Published var chipResults: [Int: Bool] = [:]

    private var lesson: GuidedLesson?
    private var follower: ScoreFollower?
    private var chordFollower: PolyScoreFollower?
    private var demoTask: Task<Void, Never>?
    private var chordCommitTask: Task<Void, Never>?

    private let recorder = AudioRecorder()
    private lazy var transcriber: NeuralTranscriber? = try? NeuralTranscriber()
    let tone = TonePlayer()

    /// Called when a Learn or Practice session is completed (used for the streak).
    var onPracticeCompleted: (() -> Void)?

    var total: Int { program.count }
    var isChords: Bool { program.isChords }
    var ribbonItems: [String] {
        isChords ? program.chords.map { $0.joined(separator: " ") } : program.notes
    }
    private func midis(_ names: [String]) -> [Int] { names.compactMap(Notes.nameToMidi) }

    // MARK: Selection

    func select(program: Program) { self.program = program; reset() }
    func select(mode: Mode) { self.mode = mode; reset() }

    func reset() {
        demoTask?.cancel(); demoTask = nil
        chordCommitTask?.cancel(); chordCommitTask = nil
        running = false; pos = 0; correct = 0; wrong = 0
        targets = []; armed = []; flash = nil; chipResults = [:]
        statusKind = .neutral
        eyebrow = "\(mode.rawValue) · ready"
        detail = ""
        status = switch mode {
        case .demonstrate: "Press Start to hear it."
        case .learn: isChords ? "Press Start to learn the chords." : "Press Start to learn it note by note."
        case .practice: "Press Start, then play the whole piece."
        }
    }

    // MARK: Lifecycle

    func startOrRestart() {
        reset()
        running = true
        if isChords {
            switch mode {
            case .demonstrate: runDemonstrateChords()
            case .learn: chordFollower = PolyScoreFollower(program.chords, advanceOnWrong: false); promptChordLearn()
            case .practice: chordFollower = PolyScoreFollower(program.chords, advanceOnWrong: true); promptChordPractice()
            }
        } else {
            switch mode {
            case .demonstrate: runDemonstrate()
            case .learn: lesson = GuidedLesson(program.notes); promptLearn()
            case .practice: follower = ScoreFollower(program.notes, advanceOnWrong: true); promptPractice()
            }
        }
    }

    /// A note was played, from a key tap (`fromTap`) or the microphone.
    func play(_ midi: Int, fromTap: Bool) {
        if fromTap { tone.play(midi: midi) }
        guard running, mode != .demonstrate else { return }
        if isChords {
            armed.insert(midi)
            scheduleChordCommit()
        } else if mode == .learn {
            handleLearn(midi)
        } else {
            handlePractice(midi)
        }
    }

    // MARK: Melody · Demonstrate

    private func runDemonstrate() {
        eyebrow = "Demonstrate · listen"; status = "Listen to the melody."; detail = "Watch the keys."
        demoTask = Task { [weak self] in
            guard let self else { return }
            for (i, name) in self.program.notes.enumerated() {
                if Task.isCancelled { return }
                let midi = Notes.nameToMidi(name) ?? 60
                self.targets = [midi]; self.tone.play(midi: midi)
                self.chipResults[i] = true; self.pos = i + 1
                try? await Task.sleep(nanoseconds: 560_000_000)
            }
            self.finishDemo("Switch to Learn to play it yourself.")
        }
    }

    // MARK: Melody · Learn

    private func promptLearn() {
        guard let lesson, !lesson.finished else {
            targets = []
            eyebrow = "Learn · complete"; status = "You learned the whole piece!"
            detail = "Correct on \(correct) of \(total) tries."
            statusKind = .correct; running = false
            onPracticeCompleted?(); return
        }
        let event = lesson.prompt()
        let midi = Notes.nameToMidi(event.targetName ?? "") ?? 60
        targets = [midi]
        eyebrow = "Learn · note \(lesson.pos + 1) of \(total)"
        status = event.message; detail = "The glowing key."; statusKind = .target
        tone.play(midi: midi)
    }

    private func handleLearn(_ midi: Int) {
        guard let lesson else { return }
        let event = lesson.feed(midi)
        if event.kind == .retry {
            wrong += 1; flashKey(midi, correct: false)
            eyebrow = "Learn · try again"; status = "You played \(Notes.midiToName(midi))"
            detail = event.message; statusKind = .wrong
        } else {
            correct += 1; chipResults[event.noteIndex] = true; flashKey(midi, correct: true)
            status = event.message; statusKind = .correct; pos = lesson.pos
            promptLearn()
        }
    }

    // MARK: Melody · Practice

    private func promptPractice() {
        eyebrow = "Practice · playing"; status = "Play the piece from the top."
        detail = "Each note is graded."
        targets = [Notes.nameToMidi(program.notes.first ?? "") ?? 60]
    }

    private func handlePractice(_ midi: Int) {
        guard let follower, !follower.finished else { return }
        let index = follower.pos
        let feedback = follower.onNote(midi)
        chipResults[index] = (feedback.status == .correct)
        flashKey(midi, correct: feedback.status == .correct)
        correct = follower.correctCount; wrong = follower.wrongCount; pos = follower.pos
        status = feedback.message
        statusKind = (feedback.status == .correct) ? .correct : .wrong
        eyebrow = "Practice · note \(index + 1)"
        if follower.finished {
            targets = []
            let pct = Int(Double(correct) / Double(total) * 100)
            status = "Score: \(correct) / \(total) (\(pct)%)"
            detail = wrong == 0 ? "Flawless run!" : "Switch to Learn to drill the misses."
            running = false
            onPracticeCompleted?()
        } else {
            targets = [Notes.nameToMidi(program.notes[follower.pos]) ?? 60]
        }
    }

    // MARK: Chords · shared

    /// Tapped notes accumulate into a pending chord; after a short pause with no
    /// new tap, the set is committed and graded (so a chord "submits" together).
    private func scheduleChordCommit() {
        chordCommitTask?.cancel()
        chordCommitTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 800_000_000)
            if Task.isCancelled { return }
            self?.commitChord()
        }
    }

    private func commitChord() {
        let played = Set(armed)
        armed = []
        guard running, !played.isEmpty else { return }
        if mode == .learn { handleChordLearn(played) } else { handleChordPractice(played) }
    }

    // MARK: Chords · Demonstrate

    private func runDemonstrateChords() {
        eyebrow = "Demonstrate · listen"; status = "Listen to the chords."; detail = "Watch the keys."
        demoTask = Task { [weak self] in
            guard let self else { return }
            for (i, chord) in self.program.chords.enumerated() {
                if Task.isCancelled { return }
                let ms = self.midis(chord)
                self.targets = Set(ms); self.tone.playChord(ms)
                self.chipResults[i] = true; self.pos = i + 1
                try? await Task.sleep(nanoseconds: 750_000_000)
            }
            self.finishDemo("Switch to Learn to play the chords yourself.")
        }
    }

    // MARK: Chords · Learn

    private func promptChordLearn() {
        guard let cf = chordFollower, !cf.finished else {
            targets = []; armed = []
            eyebrow = "Learn · complete"; status = "You learned the progression!"
            detail = "Correct on \(correct) chords."; statusKind = .correct; running = false
            onPracticeCompleted?(); return
        }
        let chord = program.chords[cf.pos]
        let ms = midis(chord)
        targets = Set(ms); armed = []
        eyebrow = "Learn · chord \(cf.pos + 1) of \(total)"
        status = "Play the chord: \(chord.joined(separator: " "))"
        detail = "All \(ms.count) notes together — the glowing keys."
        statusKind = .target
        tone.playChord(ms)
        pos = cf.pos
    }

    private func handleChordLearn(_ played: Set<Int>) {
        guard let cf = chordFollower else { return }
        let feedback = cf.onChord(played)   // advanceOnWrong = false
        if feedback.status == .correct {
            correct = cf.correctCount; chipResults[feedback.position] = true
            for m in played { flashKey(m, correct: true) }
            status = feedback.message; statusKind = .correct; pos = cf.pos
            promptChordLearn()
        } else {
            wrong = cf.wrongCount
            for name in feedback.extraNames { if let m = Notes.nameToMidi(name) { flashKey(m, correct: false) } }
            status = feedback.message; statusKind = .wrong
            detail = "Try the whole chord again."
        }
    }

    // MARK: Chords · Practice

    private func promptChordPractice() {
        eyebrow = "Practice · playing"; status = "Play each chord in order."
        detail = "Tap all the notes; they submit together."
        targets = Set(midis(program.chords.first ?? []))
    }

    private func handleChordPractice(_ played: Set<Int>) {
        guard let cf = chordFollower, !cf.finished else { return }
        let index = cf.pos
        let feedback = cf.onChord(played)   // advanceOnWrong = true
        chipResults[index] = (feedback.status == .correct)
        if feedback.status == .correct {
            for m in played { flashKey(m, correct: true) }
        } else {
            for name in feedback.extraNames { if let m = Notes.nameToMidi(name) { flashKey(m, correct: false) } }
        }
        correct = cf.correctCount; wrong = cf.wrongCount; pos = cf.pos
        status = feedback.message
        statusKind = (feedback.status == .correct) ? .correct : .wrong
        eyebrow = "Practice · chord \(index + 1)"
        if cf.finished {
            targets = []
            let pct = Int(Double(correct) / Double(total) * 100)
            status = "Score: \(correct) / \(total) chords (\(pct)%)"
            detail = wrong == 0 ? "Flawless run!" : "Switch to Learn to drill the misses."
            running = false
            onPracticeCompleted?()
        } else {
            targets = Set(midis(program.chords[cf.pos]))
        }
    }

    // MARK: Import

    func importSong(from url: URL) {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        do {
            let data = try Data(contentsOf: url)
            let notes = try Importer.loadNotes(data: data, ext: url.pathExtension.lowercased())
            let melody = Importer.toMelody(notes)
            guard !melody.isEmpty else {
                importMessage = "No notes found in \(url.lastPathComponent)."; return
            }
            let base = url.deletingPathExtension().lastPathComponent
            let piece = Piece(id: "import-\(base)-\(UUID().uuidString.prefix(4))",
                              title: base, notes: melody)
            let prog = Program.melody(piece)
            programs.append(prog)
            importMessage = "Imported \(melody.count) notes from \(url.lastPathComponent)."
            select(program: prog)
        } catch {
            importMessage = "Couldn't import \(url.lastPathComponent)."
        }
    }

    // MARK: Record → neural transcription

    func toggleRecording() {
        if isRecording {
            isRecording = false
            let captured = recorder.stop()
            transcribe(samples: captured.samples, sampleRate: captured.sampleRate)
            return
        }
        AVAudioApplication.requestRecordPermission { [weak self] granted in
            Task { @MainActor in
                guard let self else { return }
                guard granted else { self.importMessage = "Microphone access denied."; return }
                do {
                    try self.recorder.start()
                    self.isRecording = true
                    self.importMessage = "Recording… play, then tap Stop."
                } catch {
                    self.importMessage = "Couldn't start recording."
                }
            }
        }
    }

    private func transcribe(samples: [Float], sampleRate: Double) {
        guard let transcriber else { importMessage = "Neural model unavailable in this build."; return }
        guard samples.count > 8000 else { importMessage = "Recording too short — play for a few seconds."; return }
        isTranscribing = true; importMessage = "Transcribing…"
        Task.detached(priority: .userInitiated) {
            let melody = (try? transcriber.transcribeMelody(samples: samples, sampleRate: sampleRate)) ?? []
            await MainActor.run {
                self.isTranscribing = false
                guard !melody.isEmpty else {
                    self.importMessage = "No notes detected — play louder or closer to the mic."; return
                }
                let piece = Piece(id: "rec-\(UUID().uuidString.prefix(4))",
                                  title: "Recording — \(melody.count) notes", notes: melody)
                let prog = Program.melody(piece)
                self.programs.append(prog)
                self.importMessage = "Transcribed \(melody.count) notes. Ready to learn."
                self.select(program: prog)
            }
        }
    }

    // MARK: Helpers

    private func finishDemo(_ nextHint: String) {
        eyebrow = "Demonstrate · done"; status = "That's the whole piece."
        detail = nextHint; statusKind = .correct; running = false; targets = []
    }

    private func flashKey(_ midi: Int, correct: Bool) {
        flash = Flash(midi: midi, correct: correct)
        Task { [weak self] in
            try? await Task.sleep(nanoseconds: 400_000_000)
            if self?.flash?.midi == midi { self?.flash = nil }
        }
    }
}
