import SwiftUI
import UniformTypeIdentifiers
import EtudeCore

enum Palette {
    static let accent = Color(red: 0.86, green: 0.67, blue: 0.33)   // brass
    static let good = Color(red: 0.33, green: 0.75, blue: 0.55)     // green
    static let bad = Color(red: 0.93, green: 0.45, blue: 0.38)      // coral
    static let whiteKey = Color(red: 0.97, green: 0.96, blue: 0.90)
    static let blackKey = Color(red: 0.13, green: 0.12, blue: 0.10)
    static let line = Color.primary.opacity(0.12)
}

struct ContentView: View {
    @StateObject private var session = SessionModel()
    @StateObject private var audio = AudioEngine()
    @StateObject private var streak = StreakStore()
    @State private var micOn = false
    @State private var showingImporter = false
    @AppStorage("hasOnboarded") private var hasOnboarded = false

    /// File types the picker allows: MIDI, MusicXML and .mxl (plus a data
    /// fallback so files with non-standard type identifiers stay selectable).
    private var importTypes: [UTType] {
        var types: [UTType] = [.midi, .xml]
        for ext in ["mid", "midi", "musicxml", "mxl"] {
            if let type = UTType(filenameExtension: ext) { types.append(type) }
        }
        types.append(.data)
        return types
    }

    var body: some View {
        VStack(spacing: 18) {
            header
            controls
            stage
            ribbon
            PianoKeyboardView(targets: session.targets,
                              armed: session.armed,
                              flash: session.flash) { midi in
                session.play(midi, fromTap: true)
            }
            .padding(10)
            .background(RoundedRectangle(cornerRadius: 14).fill(Color(.secondarySystemBackground)))

            footnote
            Spacer(minLength: 0)
        }
        .padding()
        .onAppear {
            audio.onNote = { midi in session.play(midi, fromTap: false) }
            session.onPracticeCompleted = { streak.recordPractice() }
            streak.refresh()
        }
        .fileImporter(isPresented: $showingImporter, allowedContentTypes: importTypes) { result in
            if case .success(let url) = result { session.importSong(from: url) }
        }
        .fullScreenCover(isPresented: Binding(
            get: { !hasOnboarded },
            set: { if !$0 { hasOnboarded = true } }
        )) {
            OnboardingView { hasOnboarded = true }
        }
    }

    private var header: some View {
        HStack(alignment: .center) {
            VStack(alignment: .leading, spacing: 1) {
                Text("Etude").font(.system(.largeTitle, design: .serif)).bold()
                Text("Learn a piece, note by note.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            Spacer()
            streakBadge
        }
    }

    private var streakBadge: some View {
        let lit = streak.current > 0
        return HStack(spacing: 5) {
            Image(systemName: lit ? "flame.fill" : "flame")
            Text("\(streak.current)").fontWeight(.bold).monospacedDigit()
        }
        .font(.subheadline)
        .foregroundStyle(lit ? Color.orange : .secondary)
        .padding(.horizontal, 11).padding(.vertical, 6)
        .background(Capsule().fill(Color.orange.opacity(lit ? 0.16 : 0.07)))
        .accessibilityElement(children: .combine)
        .accessibilityLabel(
            streak.practicedToday
                ? "Practice streak \(streak.current) days, practiced today"
                : "Practice streak \(streak.current) days. Best \(streak.best)."
        )
    }

    private var controls: some View {
        VStack(spacing: 12) {
            HStack {
                Picker("Piece", selection: Binding(
                    get: { session.program },
                    set: { session.select(program: $0) }
                )) {
                    ForEach(session.programs) { Text($0.title).tag($0) }
                }
                .pickerStyle(.menu)
                Spacer()
                Button {
                    showingImporter = true
                } label: {
                    Label("Import", systemImage: "square.and.arrow.down")
                }
            }

            Picker("Mode", selection: Binding(
                get: { session.mode },
                set: { session.select(mode: $0) }
            )) {
                ForEach(SessionModel.Mode.allCases) { Text($0.rawValue).tag($0) }
            }
            .pickerStyle(.segmented)

            HStack {
                Button(session.running ? "Restart" : "Start") { session.startOrRestart() }
                    .buttonStyle(.borderedProminent)
                    .tint(Palette.accent)
                Button(micOn ? "Mic On" : "Mic") { toggleMic() }
                    .buttonStyle(.bordered)
                    .tint(micOn ? Palette.good : .secondary)
                    .disabled(session.isRecording || session.isTranscribing)
                Button {
                    session.toggleRecording()
                } label: {
                    Label(session.isRecording ? "Stop" : "Record",
                          systemImage: session.isRecording ? "stop.circle.fill" : "record.circle")
                }
                .buttonStyle(.bordered)
                .tint(session.isRecording ? Palette.bad : .secondary)
                .disabled(micOn || session.isTranscribing)
                if session.isTranscribing { ProgressView() }
                Spacer()
            }
            if let message = session.importMessage {
                Text(message)
                    .font(.caption).foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    private var stage: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(session.eyebrow.uppercased())
                .font(.caption2).bold().foregroundStyle(.secondary)
                .tracking(1)
            Text(session.status)
                .font(.system(.title, design: .serif)).bold()
                .foregroundStyle(statusColor)
                .fixedSize(horizontal: false, vertical: true)
            Text(session.detail)
                .font(.subheadline).foregroundStyle(.secondary)
            HStack(spacing: 16) {
                Text("Note \(min(session.pos + (session.running ? 1 : 0), session.total)) / \(session.total)")
                Text("Correct \(session.correct)").foregroundStyle(Palette.good)
                Text("Wrong \(session.wrong)").foregroundStyle(Palette.bad)
            }
            .font(.footnote.monospacedDigit())
            .padding(.top, 2)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(RoundedRectangle(cornerRadius: 14).fill(Color(.secondarySystemBackground)))
    }

    private var ribbon: some View {
        ScrollViewReader { proxy in
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(Array(session.ribbonItems.enumerated()), id: \.offset) { index, name in
                        Text(name)
                            .font(.callout.monospacedDigit()).bold()
                            .padding(.vertical, 8).padding(.horizontal, 10)
                            .background(RoundedRectangle(cornerRadius: 10).fill(chipColor(index)))
                            .overlay(
                                RoundedRectangle(cornerRadius: 10)
                                    .stroke(index == session.pos && session.running ? Palette.accent : .clear, lineWidth: 2)
                            )
                            .id(index)
                    }
                }
                .padding(.vertical, 4)
            }
            .onChange(of: session.pos) { _, newValue in
                withAnimation { proxy.scrollTo(newValue, anchor: .center) }
            }
        }
    }

    private var footnote: some View {
        Text("Tap keys to play, or turn on Mic to use a real piano.")
            .font(.caption).foregroundStyle(.secondary)
    }

    private var statusColor: Color {
        switch session.statusKind {
        case .correct: return Palette.good
        case .wrong: return Palette.bad
        default: return .primary
        }
    }

    private func chipColor(_ index: Int) -> Color {
        if let result = session.chipResults[index] {
            return (result ? Palette.good : Palette.bad).opacity(0.18)
        }
        return Color(.tertiarySystemBackground)
    }

    private func toggleMic() {
        if micOn { audio.stop(); micOn = false }
        else { audio.start(); micOn = true }
    }
}

#Preview {
    ContentView()
}
