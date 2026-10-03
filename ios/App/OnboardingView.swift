import SwiftUI

/// First-launch introduction. Shown once (gated by `@AppStorage("hasOnboarded")`
/// in ContentView), it explains the core loop in a few lines and matches the
/// Etude identity — serif title, brass accent.
struct OnboardingView: View {
    let onDone: () -> Void

    private struct Feature: Identifiable {
        let id = UUID()
        let symbol: String
        let title: String
        let detail: String
    }

    private let features: [Feature] = [
        Feature(symbol: "music.note.list",
                title: "Pick a piece — or bring your own",
                detail: "Built-in melodies and chords, or import a MIDI / MusicXML file."),
        Feature(symbol: "graduationcap",
                title: "Demonstrate · Learn · Practice",
                detail: "Hear it, learn it note by note, then play it through for a score."),
        Feature(symbol: "pianokeys",
                title: "Play by tap or real piano",
                detail: "Tap the keys, or turn on the mic to play an actual piano into the app."),
        Feature(symbol: "waveform.badge.mic",
                title: "Record & transcribe",
                detail: "Record yourself; an on-device neural model turns it into a piece."),
        Feature(symbol: "flame.fill",
                title: "Keep a daily streak",
                detail: "Finish a lesson each day to build and keep your streak."),
    ]

    var body: some View {
        VStack(spacing: 0) {
            Spacer(minLength: 24)

            VStack(spacing: 8) {
                Image(systemName: "pianokeys.inverse")
                    .font(.system(size: 52))
                    .foregroundStyle(Palette.accent)
                Text("Etude")
                    .font(.system(size: 44, design: .serif)).bold()
                Text("Learn a piece, note by note.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            .padding(.bottom, 36)

            VStack(alignment: .leading, spacing: 22) {
                ForEach(features) { feature in
                    HStack(alignment: .top, spacing: 16) {
                        Image(systemName: feature.symbol)
                            .font(.title2)
                            .foregroundStyle(Palette.accent)
                            .frame(width: 34)
                        VStack(alignment: .leading, spacing: 3) {
                            Text(feature.title).font(.headline)
                            Text(feature.detail)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
            }
            .padding(.horizontal, 8)

            Spacer(minLength: 24)

            Button(action: onDone) {
                Text("Get Started")
                    .font(.headline)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 6)
            }
            .buttonStyle(.borderedProminent)
            .tint(Palette.accent)
        }
        .padding(28)
        .presentationDragIndicator(.hidden)
    }
}

#Preview {
    OnboardingView(onDone: {})
}
