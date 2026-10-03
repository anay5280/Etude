import SwiftUI
import EtudeCore

/// A playable piano keyboard (C4–B5). White keys tile horizontally; black keys
/// are overlaid at the right offsets. Keys glow brass when they're the target,
/// and flash green/red on a correct/wrong hit.
struct PianoKeyboardView: View {
    let startMidi = 60
    let endMidi = 83
    /// Keys the learner should play next (glow brass). One note in melody mode,
    /// a whole chord in chord mode.
    let targets: Set<Int>
    /// Keys the learner has tapped into the current pending chord (chord mode).
    let armed: Set<Int>
    let flash: SessionModel.Flash?
    let onPlay: (Int) -> Void

    private var whiteMidis: [Int] { (startMidi...endMidi).filter { !Notes.isBlack($0) } }
    private var blackMidis: [Int] { (startMidi...endMidi).filter { Notes.isBlack($0) } }

    var body: some View {
        GeometryReader { geo in
            let whiteW = geo.size.width / CGFloat(whiteMidis.count)
            let blackW = whiteW * 0.62
            ZStack(alignment: .topLeading) {
                HStack(spacing: 0) {
                    ForEach(whiteMidis, id: \.self) { midi in
                        keyShape(midi: midi, isBlack: false)
                            .frame(width: whiteW)
                            .overlay(alignment: .bottom) {
                                Text(Notes.midiToName(midi))
                                    .font(.system(size: 10, weight: .semibold))
                                    .foregroundStyle(.secondary)
                                    .padding(.bottom, 6)
                            }
                            .contentShape(Rectangle())
                            .onTapGesture { onPlay(midi) }
                    }
                }
                ForEach(blackMidis, id: \.self) { midi in
                    let belowIndex = whiteMidis.firstIndex(of: midi - 1) ?? 0
                    keyShape(midi: midi, isBlack: true)
                        .frame(width: blackW, height: geo.size.height * 0.62)
                        .offset(x: CGFloat(belowIndex + 1) * whiteW - blackW / 2, y: 0)
                        .onTapGesture { onPlay(midi) }
                }
            }
        }
        .frame(height: 180)
    }

    @ViewBuilder
    private func keyShape(midi: Int, isBlack: Bool) -> some View {
        RoundedRectangle(cornerRadius: isBlack ? 5 : 7)
            .fill(fill(midi: midi, isBlack: isBlack))
            .overlay(
                RoundedRectangle(cornerRadius: isBlack ? 5 : 7)
                    .stroke(Palette.line, lineWidth: 1)
            )
            .shadow(color: isBlack ? .black.opacity(0.4) : .clear, radius: 3, y: 2)
    }

    private func fill(midi: Int, isBlack: Bool) -> Color {
        if let flash, flash.midi == midi { return flash.correct ? Palette.good : Palette.bad }
        if targets.contains(midi) { return Palette.accent }
        if armed.contains(midi) { return Palette.accent.opacity(0.4) }
        return isBlack ? Palette.blackKey : Palette.whiteKey
    }
}
