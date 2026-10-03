import Foundation
import AVFoundation
import EtudeCore

/// Plays short piano-ish tones — a single note or a whole chord — used to
/// demonstrate pieces and cue notes/chords. A fixed pool of voices is summed in
/// the render callback (fixed size so the audio thread never touches a
/// reallocating array).
final class TonePlayer {
    private struct Voice { var freq: Double = 0; var phase: Double = 0; var amp: Double = 0 }

    private let engine = AVAudioEngine()
    private let sampleRate: Double = 44100
    private let voiceCount = 8
    private var voices: [Voice]
    private var source: AVAudioSourceNode!

    init() {
        voices = Array(repeating: Voice(), count: voiceCount)
        source = AVAudioSourceNode { [weak self] _, _, frameCount, audioBufferList -> OSStatus in
            guard let self else { return noErr }
            let buffers = UnsafeMutableAudioBufferListPointer(audioBufferList)
            for frame in 0..<Int(frameCount) {
                var sample: Double = 0
                for v in 0..<self.voiceCount {
                    if self.voices[v].amp <= 0.0005 { continue }
                    self.voices[v].phase += 2.0 * Double.pi * self.voices[v].freq / self.sampleRate
                    if self.voices[v].phase > 2 * Double.pi { self.voices[v].phase -= 2 * Double.pi }
                    sample += (sin(self.voices[v].phase) + 0.3 * sin(2 * self.voices[v].phase)) * self.voices[v].amp
                    self.voices[v].amp *= 0.9997   // gentle decay
                }
                let out = Float(sample)
                for buffer in buffers {
                    buffer.mData!.assumingMemoryBound(to: Float.self)[frame] = out
                }
            }
            return noErr
        }
        let format = AVAudioFormat(standardFormatWithSampleRate: sampleRate, channels: 1)
        engine.attach(source)
        engine.connect(source, to: engine.mainMixerNode, format: format)
        try? engine.start()
    }

    func play(midi: Int) { playChord([midi]) }

    func playChord(_ midis: [Int]) {
        let amp = 0.22 / Double(max(1, midis.count))
        for v in 0..<voiceCount {
            if v < midis.count {
                voices[v].freq = Notes.midiToFreq(Double(midis[v]))
                voices[v].phase = 0
                voices[v].amp = amp
            } else {
                voices[v].amp = 0
            }
        }
    }
}
