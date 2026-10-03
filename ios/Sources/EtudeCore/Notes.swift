import Foundation

/// Conversions between frequency, MIDI note number, and note names.
/// Equal temperament, A4 = 440 Hz = MIDI 69, middle C (C4) = MIDI 60.
public enum Notes {
    public static let names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    public static let a4Freq = 440.0
    public static let a4Midi = 69
    private static let blackClasses: Set<Int> = [1, 3, 6, 8, 10]

    public static func midiToFreq(_ midi: Double) -> Double {
        a4Freq * pow(2.0, (midi - Double(a4Midi)) / 12.0)
    }

    public static func freqToMidi(_ freq: Double) -> Double {
        Double(a4Midi) + 12.0 * log2(freq / a4Freq)
    }

    public static func midiToName(_ midi: Int) -> String {
        let pitchClass = ((midi % 12) + 12) % 12
        let octave = Int(floor(Double(midi) / 12.0)) - 1
        return names[pitchClass] + String(octave)
    }

    /// Parses a note name like "C4" or "F#3". Returns nil if malformed.
    public static func nameToMidi(_ name: String) -> Int? {
        var pitch = ""
        var index = name.startIndex
        while index < name.endIndex, !(name[index].isNumber || name[index] == "-") {
            pitch.append(name[index])
            index = name.index(after: index)
        }
        guard let pitchClass = names.firstIndex(of: pitch),
              let octave = Int(name[index...]) else { return nil }
        return pitchClass + (octave + 1) * 12
    }

    public static func isBlack(_ midi: Int) -> Bool {
        blackClasses.contains(((midi % 12) + 12) % 12)
    }
}
