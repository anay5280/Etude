import Foundation

public struct PitchResult {
    public let freq: Double
    public let clarity: Double
    public var detected: Bool { freq > 0 }
    public var midi: Int? { detected ? Int(Notes.freqToMidi(freq).rounded()) : nil }
}

/// Monophonic pitch detector using normalized autocorrelation (McLeod / NSDF).
///
/// This is a direct port of the detector proven in the web UI. It is tuned for
/// piano melodies:
///   * Only searches the keyboard's frequency band, so speech — the male voice
///     especially, which sits below C4 — is rejected before any other test.
///   * Requires a clarity score (how periodic the frame is); struck piano keys
///     score ~1.0 while talking and room noise score far lower.
///   * Bounded to the needed lags, so it is fast enough to run per audio buffer
///     on-device and keep up with quick playing.
public struct PitchDetector {
    public var window = 1024
    public var minFreq: Double
    public var maxFreq: Double
    public var clarityGate = 0.9
    public var rmsGate = 0.02

    public init(minMidi: Int = 60, maxMidi: Int = 83) {
        minFreq = Notes.midiToFreq(Double(minMidi - 1))
        maxFreq = Notes.midiToFreq(Double(maxMidi + 1))
    }

    public func detect(_ buffer: [Float], sampleRate: Double) -> PitchResult {
        let size = min(buffer.count, window)
        let minLag = max(2, Int(sampleRate / maxFreq))
        let maxLag = min(size - 2, Int(sampleRate / minFreq))
        guard maxLag > minLag else { return PitchResult(freq: -1, clarity: 0) }

        var energy = 0.0
        for i in 0..<size { energy += Double(buffer[i]) * Double(buffer[i]) }
        if (energy / Double(size)).squareRoot() < rmsGate {
            return PitchResult(freq: -1, clarity: 0)
        }

        var nsdf = [Double](repeating: 0, count: maxLag + 2)
        var bestLag = -1
        var bestVal = 0.0
        for lag in minLag...maxLag {
            var r = 0.0
            var m = 0.0
            var j = 0
            while j < size - lag {
                let a0 = Double(buffer[j])
                let a1 = Double(buffer[j + lag])
                r += a0 * a1
                m += a0 * a0 + a1 * a1
                j += 1
            }
            let v = m > 0 ? (2 * r / m) : 0   // normalized square difference, [-1, 1]
            nsdf[lag] = v
            if v > bestVal { bestVal = v; bestLag = lag }
        }
        guard bestLag >= 0, bestVal >= clarityGate else {
            return PitchResult(freq: -1, clarity: bestVal)
        }

        // Parabolic interpolation for a sub-sample lag estimate.
        let x1 = nsdf[bestLag - 1]
        let x2 = nsdf[bestLag]
        let x3 = nsdf[bestLag + 1]
        let denom = (x1 + x3 - 2 * x2)
        let lagI = denom != 0 ? Double(bestLag) - 0.5 * (x3 - x1) / denom : Double(bestLag)
        return PitchResult(freq: sampleRate / lagI, clarity: bestVal)
    }
}

/// Debounces a per-buffer stream of detected notes into stable onsets — the
/// Swift counterpart of the web UI's frame-stability logic.
public final class NoteSegmenter {
    public var stableFrames = 2
    public var gapFrames = 2

    private var candidate: Int?
    private var candidateCount = 0
    private var committed: Int?
    private var silenceCount = 0

    public init() {}

    /// Feed one detection (nil = no confident pitch). Returns a committed MIDI
    /// note when a new, stable note begins, else nil.
    public func feed(_ midi: Int?) -> Int? {
        guard let midi else {
            silenceCount += 1
            if silenceCount >= gapFrames {
                committed = nil; candidate = nil; candidateCount = 0
            }
            return nil
        }
        silenceCount = 0
        if midi == candidate {
            candidateCount += 1
        } else {
            candidate = midi; candidateCount = 1
        }
        if candidateCount >= stableFrames, candidate != committed {
            committed = candidate
            return candidate
        }
        return nil
    }
}
