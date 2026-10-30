import Foundation

/// Copy-pasteable timestamped observation log. Every checklist observation is
/// recorded here so the maintainer can paste the whole transcript into the
/// probe doc's result log after the run.
final class ProbeLog: ObservableObject {
    @Published private(set) var lines: [String] = []

    private static let formatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "HH:mm:ss.SSS"
        return f
    }()

    func add(_ text: String) {
        let stamp = Self.formatter.string(from: Date())
        lines.append("\(stamp)  \(text)")
        NSLog("%@", "[TurnstileProbe] \(text)")
    }

    func clear() { lines = [] }

    var fullText: String { lines.joined(separator: "\n") }
}
