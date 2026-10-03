import Foundation

/// The guided (call-and-response) teaching state machine, one phrase at a time.
/// Port of the Python/JS lesson logic: prompt the next note, wait for it to be
/// played back correctly, advance; on a miss, return a retry with a hint.
public final class GuidedLesson {
    public struct Event {
        public enum Kind: Equatable { case prompt, correct, retry, phraseDone, lessonDone }
        public let kind: Kind
        public let phraseIndex: Int
        public let noteIndex: Int
        public let total: Int
        public let targetName: String?
        public let playedName: String?
        public let message: String
    }

    public let notes: [String]
    private let midi: [Int]
    public let phraseSize: Int
    public private(set) var pos = 0
    public private(set) var correctCount = 0
    public private(set) var totalAttempts = 0

    public init(_ notes: [String], phraseSize: Int = 4) {
        self.notes = notes
        self.midi = notes.compactMap(Notes.nameToMidi)
        self.phraseSize = max(1, phraseSize)
    }

    public var total: Int { notes.count }
    public var finished: Bool { pos >= notes.count }
    public var phraseIndex: Int { pos / phraseSize }

    public func currentPhraseNotes() -> [String] {
        let start = phraseIndex * phraseSize
        let end = min(start + phraseSize, notes.count)
        return Array(notes[start..<end])
    }

    public func prompt() -> Event {
        let target = midi[pos]
        let kind = Notes.isBlack(target) ? "black" : "white"
        return Event(kind: .prompt, phraseIndex: phraseIndex, noteIndex: pos, total: total,
                     targetName: notes[pos], playedName: nil,
                     message: "Play \(notes[pos]) — a \(kind) key.")
    }

    public func feed(_ playedMidi: Int) -> Event {
        let targetMidi = midi[pos]
        let targetName = notes[pos]
        totalAttempts += 1

        if playedMidi != targetMidi {
            return Event(kind: .retry, phraseIndex: phraseIndex, noteIndex: pos, total: total,
                         targetName: targetName, playedName: Notes.midiToName(playedMidi),
                         message: "Not quite — " + correctionHint(played: playedMidi, target: targetMidi) + " Try again.")
        }

        correctCount += 1
        let phraseBefore = phraseIndex
        pos += 1

        if finished {
            return Event(kind: .lessonDone, phraseIndex: phraseBefore, noteIndex: pos - 1, total: total,
                         targetName: targetName, playedName: targetName,
                         message: "Great — \(targetName)! You've learned the whole piece (\(correctCount) notes).")
        }
        if phraseIndex != phraseBefore {
            return Event(kind: .phraseDone, phraseIndex: phraseBefore, noteIndex: pos - 1, total: total,
                         targetName: targetName, playedName: targetName,
                         message: "Nice — \(targetName)! Phrase \(phraseBefore + 1) complete.")
        }
        return Event(kind: .correct, phraseIndex: phraseIndex, noteIndex: pos - 1, total: total,
                     targetName: targetName, playedName: targetName,
                     message: "Correct — \(targetName)!")
    }
}
