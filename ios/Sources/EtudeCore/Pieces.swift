import Foundation

public struct Piece: Identifiable, Hashable {
    public let id: String
    public let title: String
    public let notes: [String]

    public init(id: String, title: String, notes: [String]) {
        self.id = id
        self.title = title
        self.notes = notes
    }
}

/// Built-in monophonic melodies — the same data as the Python/JS engines.
public enum Pieces {
    private static func seq(_ s: String) -> [String] {
        s.split(separator: " ").map(String.init)
    }

    public static let all: [Piece] = [
        Piece(id: "twinkle", title: "Twinkle, Twinkle, Little Star",
              notes: seq("C4 C4 G4 G4 A4 A4 G4 F4 F4 E4 E4 D4 D4 C4 G4 G4 F4 F4 E4 E4 D4 G4 G4 F4 F4 E4 E4 D4 C4 C4 G4 G4 A4 A4 G4 F4 F4 E4 E4 D4 D4 C4")),
        Piece(id: "ode_to_joy", title: "Ode to Joy — Beethoven",
              notes: seq("E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 E4 D4 D4 E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 D4 C4 C4")),
        Piece(id: "mary", title: "Mary Had a Little Lamb",
              notes: seq("E4 D4 C4 D4 E4 E4 E4 D4 D4 D4 E4 G4 G4 E4 D4 C4 D4 E4 E4 E4 E4 D4 D4 E4 D4 C4")),
        Piece(id: "fur_elise", title: "Für Elise — main theme",
              notes: seq("E5 D#5 E5 D#5 E5 B4 D5 C5 A4 C4 E4 A4 B4 E4 G#4 B4 C5 E4 E5 D#5 E5 D#5 E5 B4 D5 C5 A4")),
    ]

    public static func by(_ id: String) -> Piece? {
        all.first { $0.id == id }
    }
}

/// A polyphonic reference piece: an ordered list of chords.
public struct ChordPiece: Identifiable, Hashable {
    public let id: String
    public let title: String
    public let chords: [[String]]

    public init(id: String, title: String, chords: [[String]]) {
        self.id = id
        self.title = title
        self.chords = chords
    }
}

/// Built-in chord progressions (kept in the C3–C5 register), matching the
/// Python `CHORD_PIECES`.
public enum Chords {
    public static let all: [ChordPiece] = [
        ChordPiece(id: "canon", title: "Pachelbel's Canon — triads", chords: [
            ["C4", "E4", "G4"], ["G3", "B3", "D4"], ["A3", "C4", "E4"], ["E4", "G4", "B4"],
            ["F3", "A3", "C4"], ["C4", "E4", "G4"], ["F3", "A3", "C4"], ["G3", "B3", "D4"],
        ]),
        ChordPiece(id: "pop_progression", title: "I–V–vi–IV in C", chords: [
            ["C4", "E4", "G4"], ["G3", "B3", "D4"], ["A3", "C4", "E4"], ["F3", "A3", "C4"],
        ]),
    ]

    public static func by(_ id: String) -> ChordPiece? {
        all.first { $0.id == id }
    }
}
