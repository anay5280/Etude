import Foundation
import Compression

/// A note with timing, produced by importing a score file.
public struct TimedNote: Equatable {
    public let start: Double      // seconds
    public let duration: Double   // seconds
    public let midi: Int
    public let velocity: Int

    public init(start: Double, duration: Double, midi: Int, velocity: Int = 80) {
        self.start = start
        self.duration = duration
        self.midi = midi
        self.velocity = velocity
    }

    public var name: String { Notes.midiToName(midi) }
}

public enum ImportError: Error, Equatable {
    case notMIDI
    case smpteUnsupported
    case unsupportedType(String)
    case badArchive
    case noScoreInArchive
}

/// Imports real songs from MIDI and MusicXML — a Swift port of `importer.py`.
/// Uses only system frameworks (Foundation + Compression), so it runs on iOS.
public enum Importer {
    private static let stepSemitone: [String: Int] =
        ["C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11]
    private static let defaultTempo = 500_000   // microseconds/quarter (120 bpm)

    // MARK: Dispatch

    public static func loadNotes(path: String) throws -> [TimedNote] {
        let url = URL(fileURLWithPath: path)
        let data = try Data(contentsOf: url)
        return try loadNotes(data: data, ext: url.pathExtension.lowercased())
    }

    public static func loadNotes(data: Data, ext: String) throws -> [TimedNote] {
        switch ext {
        case "mid", "midi": return try parseMIDI(data)
        case "xml", "musicxml": return parseMusicXML(data)
        case "mxl": return try parseMXL(data)
        default: throw ImportError.unsupportedType(ext)
        }
    }

    // MARK: Conversion to pieces

    private static func groupOnsets(_ notes: [TimedNote], tolerance: Double = 0.03) -> [[TimedNote]] {
        guard !notes.isEmpty else { return [] }
        let sorted = notes.sorted { ($0.start, $0.midi) < ($1.start, $1.midi) }
        var groups: [[TimedNote]] = [[sorted[0]]]
        for note in sorted.dropFirst() {
            if note.start - groups[groups.count - 1][0].start <= tolerance {
                groups[groups.count - 1].append(note)
            } else {
                groups.append([note])
            }
        }
        return groups
    }

    /// A chord-per-onset sequence (all notes of each onset).
    public static func toChords(_ notes: [TimedNote], tolerance: Double = 0.03) -> [[String]] {
        groupOnsets(notes, tolerance: tolerance).map { group in
            Set(group.map { $0.midi }).sorted().map(Notes.midiToName)
        }
    }

    /// A monophonic melody: the highest note of each onset.
    public static func toMelody(_ notes: [TimedNote], tolerance: Double = 0.03) -> [String] {
        groupOnsets(notes, tolerance: tolerance).map { group in
            Notes.midiToName(group.max { $0.midi < $1.midi }!.midi)
        }
    }

    public static func toPiece(_ notes: [TimedNote], id: String, title: String) -> Piece {
        Piece(id: id, title: title, notes: toMelody(notes))
    }

    public static func loadPiece(path: String) throws -> Piece {
        let url = URL(fileURLWithPath: path)
        let base = url.deletingPathExtension().lastPathComponent
        return toPiece(try loadNotes(path: path), id: base, title: base)
    }

    // MARK: MIDI

    private struct MidiEvent { let tick: Int; let kind: Int; let a: Int; let b: Int }
    // kind: 0 = note on, 1 = note off, 2 = tempo

    public static func parseMIDI(_ data: Data) throws -> [TimedNote] {
        let bytes = [UInt8](data)
        guard bytes.count >= 14, bytes[0] == 0x4D, bytes[1] == 0x54,
              bytes[2] == 0x68, bytes[3] == 0x64 else { throw ImportError.notMIDI }
        let division = be16(bytes, 12)
        if division & 0x8000 != 0 { throw ImportError.smpteUnsupported }
        let ticksPerBeat = Double(division)
        let nTracks = be16(bytes, 10)

        var events: [MidiEvent] = []
        var pos = 14
        var track = 0
        while track < nTracks, pos + 8 <= bytes.count {
            guard bytes[pos] == 0x4D, bytes[pos + 1] == 0x54,
                  bytes[pos + 2] == 0x72, bytes[pos + 3] == 0x6B else { break }
            let length = be32(bytes, pos + 4)
            let start = pos + 8
            let end = min(start + length, bytes.count)
            parseTrack(Array(bytes[start..<end]), into: &events)
            pos = start + length
            track += 1
        }

        events.sort { $0.tick < $1.tick }

        // Tempo map -> tick to seconds.
        var tempoChanges = events.filter { $0.kind == 2 }.map { ($0.tick, $0.a) }
        if tempoChanges.first?.0 != 0 { tempoChanges.insert((0, defaultTempo), at: 0) }

        func tickToSeconds(_ target: Int) -> Double {
            var seconds = 0.0
            var lastTick = 0
            var tempo = tempoChanges[0].1
            for (changeTick, changeTempo) in tempoChanges {
                if changeTick >= target { break }
                seconds += Double(changeTick - lastTick) / ticksPerBeat * (Double(tempo) / 1e6)
                lastTick = changeTick
                tempo = changeTempo
            }
            seconds += Double(target - lastTick) / ticksPerBeat * (Double(tempo) / 1e6)
            return seconds
        }

        // Pair note-on with the next matching note-off (FIFO).
        var open: [Int: [(Int, Int)]] = [:]   // midi -> [(tick, velocity)]
        var notes: [TimedNote] = []
        for e in events {
            if e.kind == 0 {
                open[e.a, default: []].append((e.tick, e.b))
            } else if e.kind == 1 {
                if var stack = open[e.a], !stack.isEmpty {
                    let (onTick, vel) = stack.removeFirst()
                    open[e.a] = stack
                    let s = tickToSeconds(onTick)
                    let en = tickToSeconds(e.tick)
                    notes.append(TimedNote(start: s, duration: max(0, en - s), midi: e.a, velocity: vel))
                }
            }
        }
        return notes.sorted { ($0.start, $0.midi) < ($1.start, $1.midi) }
    }

    private static func parseTrack(_ b: [UInt8], into events: inout [MidiEvent]) {
        var i = 0
        var tick = 0
        var status = 0
        let n = b.count
        while i < n {
            let (delta, next) = readVLQ(b, i)
            tick += delta
            i = next
            if i >= n { break }
            if b[i] & 0x80 != 0 { status = Int(b[i]); i += 1 }

            if status == 0xFF {                    // meta event
                guard i < n else { break }
                let metaType = Int(b[i]); i += 1
                let (len, after) = readVLQ(b, i)
                i = after
                if metaType == 0x51, len == 3, i + 2 < n {
                    let tempo = Int(b[i]) << 16 | Int(b[i + 1]) << 8 | Int(b[i + 2])
                    events.append(MidiEvent(tick: tick, kind: 2, a: tempo, b: 0))
                }
                i += len
            } else if status == 0xF0 || status == 0xF7 {   // sysex
                let (len, after) = readVLQ(b, i)
                i = after + len
            } else {
                let hi = status & 0xF0
                if hi == 0x80 || hi == 0x90 || hi == 0xA0 || hi == 0xB0 || hi == 0xE0 {
                    guard i + 1 < n else { break }
                    let d1 = Int(b[i]); let d2 = Int(b[i + 1]); i += 2
                    if hi == 0x90 && d2 > 0 {
                        events.append(MidiEvent(tick: tick, kind: 0, a: d1, b: d2))
                    } else if hi == 0x80 || (hi == 0x90 && d2 == 0) {
                        events.append(MidiEvent(tick: tick, kind: 1, a: d1, b: 0))
                    }
                } else if hi == 0xC0 || hi == 0xD0 {
                    i += 1
                }
            }
        }
    }

    private static func readVLQ(_ b: [UInt8], _ start: Int) -> (Int, Int) {
        var value = 0
        var i = start
        while i < b.count {
            let byte = b[i]; i += 1
            value = (value << 7) | Int(byte & 0x7F)
            if byte & 0x80 == 0 { break }
        }
        return (value, i)
    }

    // MARK: MusicXML

    public static func parseMusicXML(_ data: Data) -> [TimedNote] {
        let delegate = MusicXMLDelegate()
        let parser = XMLParser(data: data)
        parser.delegate = delegate
        parser.parse()
        return delegate.notes.sorted { ($0.start, $0.midi) < ($1.start, $1.midi) }
    }

    private final class MusicXMLDelegate: NSObject, XMLParserDelegate {
        var notes: [TimedNote] = []
        private var divisions = 1
        private var secondsPerDivision = 0.5   // quarter = 0.5s @120bpm
        private var position = 0
        private var prevOnset = 0

        private var inNote = false
        private var isChord = false
        private var isRest = false
        private var hasPitch = false
        private var step = ""
        private var alter = 0
        private var octave = 0
        private var noteDuration = 0

        private var inBackup = false
        private var inForward = false
        private var containerDuration = 0

        private var text = ""

        private func local(_ name: String) -> String {
            name.components(separatedBy: ":").last ?? name
        }

        func parser(_ parser: XMLParser, didStartElement elementName: String,
                    namespaceURI: String?, qualifiedName qName: String?,
                    attributes attributeDict: [String: String]) {
            text = ""
            switch local(elementName) {
            case "part": position = 0; prevOnset = 0; divisions = 1; secondsPerDivision = 0.5
            case "note":
                inNote = true; isChord = false; isRest = false; hasPitch = false
                step = ""; alter = 0; octave = 0; noteDuration = 0
            case "chord": if inNote { isChord = true }
            case "rest": if inNote { isRest = true }
            case "pitch": if inNote { hasPitch = true }
            case "backup": inBackup = true; containerDuration = 0
            case "forward": inForward = true; containerDuration = 0
            default: break
            }
        }

        func parser(_ parser: XMLParser, foundCharacters string: String) {
            text += string
        }

        func parser(_ parser: XMLParser, didEndElement elementName: String,
                    namespaceURI: String?, qualifiedName qName: String?) {
            let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
            switch local(elementName) {
            case "divisions":
                divisions = Int(trimmed) ?? 1
                secondsPerDivision = 0.5 / Double(divisions)
            case "step": if inNote { step = trimmed }
            case "alter": if inNote { alter = Int(Double(trimmed) ?? 0) }
            case "octave": if inNote { octave = Int(trimmed) ?? 0 }
            case "duration":
                let d = Int(trimmed) ?? 0
                if inNote { noteDuration = d }
                else if inBackup || inForward { containerDuration = d }
            case "note": finishNote(); inNote = false
            case "backup": position -= containerDuration; inBackup = false
            case "forward": position += containerDuration; inForward = false
            default: break
            }
        }

        private func finishNote() {
            let onset: Int
            if isChord {
                onset = prevOnset
            } else {
                onset = position
                position += noteDuration
            }
            if !isRest, hasPitch, let semitone = stepSemitone[step] {
                let midi = (octave + 1) * 12 + semitone + alter
                notes.append(TimedNote(start: Double(onset) * secondsPerDivision,
                                       duration: Double(noteDuration) * secondsPerDivision,
                                       midi: midi))
            }
            prevOnset = onset
        }
    }

    // MARK: MXL (zipped MusicXML)

    private static func parseMXL(_ data: Data) throws -> [TimedNote] {
        let entries = try Zip.entries(in: [UInt8](data))
        var scoreName: String?
        if let container = entries["META-INF/container.xml"],
           let s = String(data: container, encoding: .utf8),
           let r = s.range(of: "full-path=\"") {
            let rest = s[r.upperBound...]
            if let end = rest.firstIndex(of: "\"") { scoreName = String(rest[..<end]) }
        }
        if scoreName == nil {
            scoreName = entries.keys.first {
                (($0.hasSuffix(".xml") || $0.hasSuffix(".musicxml")) && !$0.hasPrefix("META-INF"))
            }
        }
        guard let name = scoreName, let xml = entries[name] else {
            throw ImportError.noScoreInArchive
        }
        return parseMusicXML(xml)
    }

    // MARK: byte helpers

    private static func be16(_ b: [UInt8], _ o: Int) -> Int { Int(b[o]) << 8 | Int(b[o + 1]) }
    private static func be32(_ b: [UInt8], _ o: Int) -> Int {
        Int(b[o]) << 24 | Int(b[o + 1]) << 16 | Int(b[o + 2]) << 8 | Int(b[o + 3])
    }
}

/// Minimal ZIP reader (central-directory based) with DEFLATE support, enough to
/// open `.mxl` archives. Uses Apple's Compression framework for inflation.
enum Zip {
    static func entries(in bytes: [UInt8]) throws -> [String: Data] {
        guard let eocd = findEOCD(bytes) else { throw ImportError.badArchive }
        let count = le16(bytes, eocd + 10)
        var offset = le32(bytes, eocd + 16)
        var result: [String: Data] = [:]

        for _ in 0..<count {
            guard offset + 46 <= bytes.count, le32(bytes, offset) == 0x0201_4b50 else { break }
            let method = le16(bytes, offset + 10)
            let compSize = le32(bytes, offset + 20)
            let uncompSize = le32(bytes, offset + 24)
            let nameLen = le16(bytes, offset + 28)
            let extraLen = le16(bytes, offset + 30)
            let commentLen = le16(bytes, offset + 32)
            let localOffset = le32(bytes, offset + 42)
            let name = String(bytes: bytes[(offset + 46)..<(offset + 46 + nameLen)], encoding: .utf8) ?? ""

            if let data = extract(bytes, localOffset: localOffset, method: method,
                                  compSize: compSize, uncompSize: uncompSize) {
                result[name] = data
            }
            offset += 46 + nameLen + extraLen + commentLen
        }
        return result
    }

    private static func extract(_ bytes: [UInt8], localOffset: Int, method: Int,
                                compSize: Int, uncompSize: Int) -> Data? {
        guard localOffset + 30 <= bytes.count, le32(bytes, localOffset) == 0x0403_4b50 else { return nil }
        let nameLen = le16(bytes, localOffset + 26)
        let extraLen = le16(bytes, localOffset + 28)
        let dataStart = localOffset + 30 + nameLen + extraLen
        guard dataStart + compSize <= bytes.count else { return nil }
        let comp = Array(bytes[dataStart..<(dataStart + compSize)])
        if method == 0 { return Data(comp) }                 // stored
        if method == 8 { return inflate(comp, expected: uncompSize) }  // deflate
        return nil
    }

    private static func inflate(_ data: [UInt8], expected: Int) -> Data? {
        guard expected > 0 else { return Data() }
        let dst = UnsafeMutablePointer<UInt8>.allocate(capacity: expected)
        defer { dst.deallocate() }
        let written = data.withUnsafeBufferPointer { src in
            compression_decode_buffer(dst, expected, src.baseAddress!, data.count, nil, COMPRESSION_ZLIB)
        }
        return written > 0 ? Data(bytes: dst, count: written) : nil
    }

    private static func findEOCD(_ b: [UInt8]) -> Int? {
        guard b.count >= 22 else { return nil }
        var i = b.count - 22
        let lowest = max(0, b.count - 22 - 65_536)
        while i >= lowest {
            if le32(b, i) == 0x0605_4b50 { return i }
            i -= 1
        }
        return nil
    }

    private static func le16(_ b: [UInt8], _ o: Int) -> Int { Int(b[o]) | Int(b[o + 1]) << 8 }
    private static func le32(_ b: [UInt8], _ o: Int) -> Int {
        Int(b[o]) | Int(b[o + 1]) << 8 | Int(b[o + 2]) << 16 | Int(b[o + 3]) << 24
    }
}
