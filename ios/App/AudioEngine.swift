import Foundation
import AVFoundation
import EtudeCore

/// Captures microphone audio with AVAudioEngine, runs the on-device
/// `PitchDetector` (from EtudeCore) per buffer, and reports committed notes.
///
/// This is the iOS counterpart of the web UI's live-mic path — the exact same
/// detection and debouncing, now native. The heavier polyphonic path (Core ML
/// basic-pitch) plugs in here later; see README "Core ML".
final class AudioEngine: ObservableObject {
    @Published private(set) var isRunning = false
    @Published private(set) var micAuthorized = true

    /// Called on the main thread whenever a new, stable note is committed.
    var onNote: ((Int) -> Void)?

    private let engine = AVAudioEngine()
    private let detector = PitchDetector()
    private let segmenter = NoteSegmenter()
    private var pending: [Float] = []
    private let frameSize = 1024
    private let hop = 512

    func start() {
        AVAudioApplication.requestRecordPermission { [weak self] granted in
            DispatchQueue.main.async {
                self?.micAuthorized = granted
                if granted { self?.beginCapture() }
            }
        }
    }

    private func beginCapture() {
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playAndRecord, mode: .measurement,
                                    options: [.defaultToSpeaker, .mixWithOthers])
            try session.setActive(true)

            let input = engine.inputNode
            let format = input.outputFormat(forBus: 0)
            let sampleRate = format.sampleRate
            input.installTap(onBus: 0, bufferSize: UInt32(hop), format: format) { [weak self] buffer, _ in
                self?.process(buffer, sampleRate: sampleRate)
            }
            try engine.start()
            isRunning = true
        } catch {
            isRunning = false
        }
    }

    func stop() {
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        pending.removeAll()
        isRunning = false
    }

    private func process(_ buffer: AVAudioPCMBuffer, sampleRate: Double) {
        guard let channel = buffer.floatChannelData?[0] else { return }
        let count = Int(buffer.frameLength)
        pending.append(contentsOf: UnsafeBufferPointer(start: channel, count: count))

        while pending.count >= frameSize {
            let frame = Array(pending[0..<frameSize])
            pending.removeFirst(hop)
            let result = detector.detect(frame, sampleRate: sampleRate)
            if let committed = segmenter.feed(result.midi) {
                DispatchQueue.main.async { [weak self] in
                    self?.onNote?(committed)
                }
            }
        }
    }
}
