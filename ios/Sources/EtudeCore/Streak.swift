import Foundation

/// Daily practice-streak state. Days are represented as integer day indices
/// (days since a fixed reference), so the update logic is pure and testable
/// without dealing with dates directly.
public struct StreakState: Equatable {
    public var current: Int
    public var best: Int
    public var lastDay: Int?

    public init(current: Int = 0, best: Int = 0, lastDay: Int? = nil) {
        self.current = current
        self.best = best
        self.lastDay = lastDay
    }
}

public enum Streak {
    /// The day index for a date (whole days since the reference date, in the
    /// given calendar's local time — DST-safe via day-component math).
    public static func dayIndex(_ date: Date, calendar: Calendar = .current) -> Int {
        let reference = Date(timeIntervalSinceReferenceDate: 0)
        let from = calendar.startOfDay(for: reference)
        let to = calendar.startOfDay(for: date)
        return calendar.dateComponents([.day], from: from, to: to).day ?? 0
    }

    /// Record a practice session on `today`, returning the updated state.
    /// Practicing the same day again is a no-op; a consecutive day extends the
    /// streak; a gap resets it to 1.
    public static func recording(_ state: StreakState, today: Int) -> StreakState {
        var next = state
        if next.lastDay == today {
            // already counted today
        } else if next.lastDay == today - 1 {
            next.current += 1
        } else {
            next.current = 1
        }
        next.lastDay = today
        next.best = max(next.best, next.current)
        return next
    }

    /// The streak to show today: valid only if the last practice was today or
    /// yesterday; otherwise the streak is broken and shows 0.
    public static func displayCurrent(_ state: StreakState, today: Int) -> Int {
        guard let last = state.lastDay else { return 0 }
        return (last == today || last == today - 1) ? state.current : 0
    }
}
