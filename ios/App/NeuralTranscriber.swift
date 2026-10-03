import Foundation
import CoreML
import EtudeCore

/// On-device neural transcription with Spotify's basic-pitch Core ML model.
///
/// This is the iOS counterpart of the desktop `neural.py` path: the accurate,
/// **polyphonic** engine for real recordings, running offline via Core ML.
/// Live monophonic feedback stays on `PitchDetector`; this is for transcribing
/// a whole recording into notes/chords.
///
/// The model (`nmp.mlpackage`, in App/Models) was inspected to write this:
///   input  `input_2`     : [1, 43844, 1]  mono audio, 22050 Hz (~2.0 s window)
///   output `Identity_1`  : [1, 172, 88]   per-frame NOTE activations (88 keys)
///   output `Identity_2`  : [1, 172, 88]   per-frame ONSET activations
/// Key bin k maps to MIDI note 21 + k; frames advance at 22050/256 ≈ 86.13 fps
/// (verified against the model with a C4 tone → bin 39 → MIDI 60).
///
/// Note extraction here is intentionally straightforward (onset + sustain
/// thresholding). basic-pitch's fuller note-creation (pitch-bend contour, the
/// "melodia" trick) can be layered on for more fidelity — see neural.py.
final class NeuralTranscriber: @unchecked Sendable {
    enum TranscriberError: Error { case modelNotFound }

    // Model geometry (from inspection).
    private static let sampleRate = 22050.0
    private static let windowSamples = 43844
    private static let frames = 172
    private static let keys = 88
    private static let midiOffset = 21
    private static let framesPerSecond = 22050.0 / 256.0   // ≈ 86.13

    private let model: MLModel

    /// Loads the compiled model. When `nmp.mlpackage` is added to the Xcode
    /// target it is compiled to `nmp.mlmodelc` and bundled at build time.
    init() throws {
        guard let url = Bundle.main.url(forResource: "nmp", withExtension: "mlmodelc") else {
            throw TranscriberError.modelNotFound
        }
        model = try MLModel(contentsOf: url)
    }

    /// Transcribe audio samples into timed notes. Reuses EtudeCore's `TimedNote`
    /// so the result feeds `Importer.toMelody` / `toChords` exactly like an
    /// imported file.
    func transcribe(samples: [Float], sampleRate: Double,
                    onsetThreshold: Float = 0.5, frameThreshold: Float = 0.3) throws -> [TimedNote] {
        let audio = sampleRate == Self.sampleRate ? samples
                                                  : Self.resample(samples, from: sampleRate, to: Self.sampleRate)
        var events: [TimedNote] = []
        var windowStart = 0
        while windowStart < audio.count {
            let offsetSeconds = Double(windowStart) / Self.sampleRate
            let (note, onset) = try runWindow(audio, start: windowStart)
            events.append(contentsOf: extractNotes(note: note, onset: onset,
                                                    offsetSeconds: offsetSeconds,
                                                    onsetThreshold: onsetThreshold,
                                                    frameThreshold: frameThreshold))
            windowStart += Self.windowSamples   // non-overlapping windows (see note above)
        }
        return events.sorted { ($0.start, $0.midi) < ($1.start, $1.midi) }
    }

    /// Convenience: transcribe straight to a melody line.
    func transcribeMelody(samples: [Float], sampleRate: Double) throws -> [String] {
        Importer.toMelody(try transcribe(samples: samples, sampleRate: sampleRate))
    }

    // MARK: Inference

    private func runWindow(_ audio: [Float], start: Int) throws -> (note: MLMultiArray, onset: MLMultiArray) {
        let input = try MLMultiArray(shape: [1, NSNumber(value: Self.windowSamples), 1], dataType: .float32)
        let ptr = input.dataPointer.bindMemory(to: Float32.self, capacity: Self.windowSamples)
        for i in 0..<Self.windowSamples {
            let src = start + i
            ptr[i] = src < audio.count ? audio[src] : 0
        }
        let provider = try MLDictionaryFeatureProvider(dictionary: [
            "input_2": MLFeatureValue(multiArray: input)
        ])
        let output = try model.prediction(from: provider)
        guard let note = output.featureValue(for: "Identity_1")?.multiArrayValue,
              let onset = output.featureValue(for: "Identity_2")?.multiArrayValue else {
            throw TranscriberError.modelNotFound
        }
        return (note, onset)
    }

    private func extractNotes(note: MLMultiArray, onset: MLMultiArray,
                              offsetSeconds: Double,
                              onsetThreshold: Float, frameThreshold: Float) -> [TimedNote] {
        // Direct pointer access for speed; layout is [1, frames, keys] row-major.
        let notePtr = note.dataPointer.bindMemory(to: Float32.self, capacity: Self.frames * Self.keys)
        let onsetPtr = onset.dataPointer.bindMemory(to: Float32.self, capacity: Self.frames * Self.keys)
        func idx(_ f: Int, _ k: Int) -> Int { f * Self.keys + k }

        var events: [TimedNote] = []
        for k in 0..<Self.keys {
            var f = 0
            while f < Self.frames {
                if onsetPtr[idx(f, k)] >= onsetThreshold, notePtr[idx(f, k)] >= frameThreshold {
                    let startFrame = f
                    var end = f
                    while end < Self.frames, notePtr[idx(end, k)] >= frameThreshold { end += 1 }
                    let start = offsetSeconds + Double(startFrame) / Self.framesPerSecond
                    let duration = Double(end - startFrame) / Self.framesPerSecond
                    events.append(TimedNote(start: start, duration: duration, midi: Self.midiOffset + k))
                    f = end
                } else {
                    f += 1
                }
            }
        }
        return events
    }

    // MARK: Resampling

    /// Simple linear resampler (mic audio is usually 44100/48000; the model
    /// wants 22050). Adequate for transcription; swap for a windowed-sinc
    /// resampler if you need higher fidelity.
    private static func resample(_ samples: [Float], from: Double, to: Double) -> [Float] {
        guard from > 0, to > 0, !samples.isEmpty else { return samples }
        let ratio = to / from
        let count = Int(Double(samples.count) * ratio)
        var out = [Float](repeating: 0, count: count)
        for i in 0..<count {
            let srcPos = Double(i) / ratio
            let i0 = Int(srcPos)
            let frac = Float(srcPos - Double(i0))
            let a = samples[min(i0, samples.count - 1)]
            let b = samples[min(i0 + 1, samples.count - 1)]
            out[i] = a + (b - a) * frac
        }
        return out
    }
}
