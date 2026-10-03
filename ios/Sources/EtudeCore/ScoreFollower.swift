import Foundation

/// Plain-language guidance to get from a played note to the target note.
public func correctionHint(played: Int, target: Int) -> String {
    let delta = target - played
    let steps = abs(delta)
    let direction = delta > 0 ? "up" : "down"
    let lowHigh = delta > 0 ? "too low" : "too high"
    let plural = steps > 1 ? "s" : ""
    let key = Notes.isBlack(target) ? "black" : "white"
    return "You're \(steps) semitone\(plural) \(lowHigh) — move \(direction) \(steps) key\(plural) to \(Notes.midiToName(target)) (a \(key) key)."
}

public struct Feedback {
    public enum Status: Equatable { case correct, wrong, done }
    public let status: Status
    public let position: Int
    public let total: Int
    public let expectedName: String?
    public let playedName: String?
    public let semitones: Int
    public let message: String
}

/// Follows played notes against a reference piece and judges each one.
/// On a wrong note it stays on the same position (waits for a retry) unless
/// `advanceOnWrong` is set.
public final class ScoreFollower {
    public let expectedNames: [String]
    private let expected: [Int]
    public private(set) var pos = 0
    public private(set) var correctCount = 0
    public private(set) var wrongCount = 0
    public var advanceOnWrong: Bool

    public init(_ names: [String], advanceOnWrong: Bool = false) {
        self.expectedNames = names
        self.expected = names.compactMap(Notes.nameToMidi)
        self.advanceOnWrong = advanceOnWrong
    }

    public var total: Int { expected.count }
    public var finished: Bool { pos >= expected.count }

    public func reset() { pos = 0; correctCount = 0; wrongCount = 0 }

    public func onNote(_ midi: Int) -> Feedback {
        if finished {
            return Feedback(status: .done, position: total, total: total,
                            expectedName: nil, playedName: Notes.midiToName(midi),
                            semitones: 0, message: "The piece is complete.")
        }
        let targetMidi = expected[pos]
        let targetName = expectedNames[pos]
        let playedName = Notes.midiToName(midi)

        if midi == targetMidi {
            correctCount += 1
            let at = pos
            pos += 1
            var message = "Correct — \(targetName)."
            if finished {
                message += "  Piece complete! \(correctCount)/\(total) correct."
            }
            return Feedback(status: .correct, position: at, total: total,
                            expectedName: targetName, playedName: playedName,
                            semitones: 0, message: message)
        }

        wrongCount += 1
        let at = pos
        let message = "You played \(playedName), but note \(pos + 1) should be \(targetName). "
            + correctionHint(played: midi, target: targetMidi)
        if advanceOnWrong { pos += 1 }
        return Feedback(status: .wrong, position: at, total: total,
                        expectedName: targetName, playedName: playedName,
                        semitones: targetMidi - midi, message: message)
    }
}
