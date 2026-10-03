import Foundation
import AVFoundation

/// Records microphone audio into a raw sample buffer, for offline neural
/// transcription (basic-pitch via `NeuralTranscriber`). Separate from
/// `AudioEngine`, which does low-latency *live* detection.
final class AudioRecorder {
    private let engine = AVAudioEngine()
    private var samples: [Float] = []
    private var captureRate: Double = 44100
    private(set) var isRecording = false

    func start() throws {
        samples.removeAll(keepingCapacity: true)
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playAndRecord, options: [.defaultToSpeaker])
        try session.setActive(true)

        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        captureRate = format.sampleRate
        input.installTap(onBus: 0, bufferSize: 4096, format: format) { [weak self] buffer, _ in
            guard let self, let channel = buffer.floatChannelData?[0] else { return }
            self.samples.append(contentsOf: UnsafeBufferPointer(start: channel, count: Int(buffer.frameLength)))
        }
        try engine.start()
        isRecording = true
    }

    /// Stops recording and returns everything captured.
    func stop() -> (samples: [Float], sampleRate: Double) {
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        isRecording = false
        return (samples, captureRate)
    }
}
