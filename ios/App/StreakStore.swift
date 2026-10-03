import Foundation
import Combine
import EtudeCore

/// Persists the practice streak in UserDefaults and exposes it to the UI.
/// A "practice" is recorded when a Learn or Practice session is completed.
final class StreakStore: ObservableObject {
    @Published private(set) var current = 0
    @Published private(set) var best = 0
    @Published private(set) var practicedToday = false

    private let defaults: UserDefaults
    private let currentKey = "streak.current"
    private let bestKey = "streak.best"
    private let lastDayKey = "streak.lastDay"

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        refresh()
    }

    private var today: Int { Streak.dayIndex(Date()) }

    private func loadState() -> StreakState {
        let last = defaults.object(forKey: lastDayKey) as? Int
        return StreakState(current: defaults.integer(forKey: currentKey),
                           best: defaults.integer(forKey: bestKey),
                           lastDay: last)
    }

    /// Recompute the displayed streak for the current day (call on launch and
    /// when returning to the app, so a broken streak shows 0).
    func refresh() {
        let state = loadState()
        current = Streak.displayCurrent(state, today: today)
        best = state.best
        practicedToday = (state.lastDay == today)
    }

    /// Record a completed practice session for today.
    func recordPractice() {
        let updated = Streak.recording(loadState(), today: today)
        defaults.set(updated.current, forKey: currentKey)
        defaults.set(updated.best, forKey: bestKey)
        defaults.set(updated.lastDay, forKey: lastDayKey)
        refresh()
    }
}
