import Foundation

public struct ChordFeedback {
    public enum Status: Equatable { case correct, wrong, done }
    public let status: Status
    public let position: Int
    public let total: Int
    public let expectedNames: [String]
    public let playedNames: [String]
    public let missingNames: [String]   // expected but not played
    public let extraNames: [String]     // played but not in the chord
    public let message: String
}

/// Pair each wrong extra note to the nearest missing note as a suggestion —
/// a Swift port of `_pair_corrections` from follower.py.
public func chordCorrections(missing: Set<Int>, extra: Set<Int>) -> [String] {
    var hints: [String] = []
    var remaining = missing
    for played in extra.sorted() {
        guard let target = remaining.min(by: { abs($0 - played) < abs($1 - played) }) else {
            hints.append("\(Notes.midiToName(played)) is not part of this chord — lift it.")
            continue
        }
        remaining.remove(target)
        hints.append("\(Notes.midiToName(played)) → " + correctionHint(played: played, target: target))
    }
    for stillMissing in remaining.sorted() {
        hints.append("You're missing \(Notes.midiToName(stillMissing)) — add it.")
    }
    return hints
}

/// Follows played chords against a reference progression, judging each on the
/// exact set of notes and reporting missing / extra notes with corrections.
public final class PolyScoreFollower {
    public let expectedNames: [[String]]
    private let expected: [Set<Int>]
    public private(set) var pos = 0
    public private(set) var correctCount = 0
    public private(set) var wrongCount = 0
    public var advanceOnWrong: Bool

    public init(_ chords: [[String]], advanceOnWrong: Bool = true) {
        self.expectedNames = chords
        self.expected = chords.map { Set($0.compactMap(Notes.nameToMidi)) }
        self.advanceOnWrong = advanceOnWrong
    }

    public var total: Int { expected.count }
    public var finished: Bool { pos >= expected.count }
    public func reset() { pos = 0; correctCount = 0; wrongCount = 0 }

    private func names(_ set: Set<Int>) -> [String] { set.sorted().map(Notes.midiToName) }

    public func onChord(_ played: Set<Int>) -> ChordFeedback {
        if finished {
            return ChordFeedback(status: .done, position: total, total: total,
                                 expectedNames: [], playedNames: names(played),
                                 missingNames: [], extraNames: [], message: "The piece is complete.")
        }
        let exp = expected[pos]
        let expNames = expectedNames[pos]
        let at = pos

        if played == exp {
            correctCount += 1
            pos += 1
            var message = "Correct — \(expNames.joined(separator: " "))."
            if finished { message += "  Complete! \(correctCount)/\(total) chords." }
            return ChordFeedback(status: .correct, position: at, total: total,
                                 expectedNames: expNames, playedNames: names(played),
                                 missingNames: [], extraNames: [], message: message)
        }

        wrongCount += 1
        let missing = exp.subtracting(played)
        let extra = played.subtracting(exp)
        let message = "Chord \(at + 1): expected \(expNames.joined(separator: " ")). "
            + chordCorrections(missing: missing, extra: extra).joined(separator: " ")
        if advanceOnWrong { pos += 1 }
        return ChordFeedback(status: .wrong, position: at, total: total,
                             expectedNames: expNames, playedNames: names(played),
                             missingNames: names(missing), extraNames: names(extra), message: message)
    }
}
