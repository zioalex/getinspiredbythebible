import SwiftUI
import UIKit

struct ContentView: View {
    @StateObject private var manager = TurnstileManager(siteKey: ProbeConfig.siteKeyPlaceholder)
    @StateObject private var log = ProbeLog()
    @StateObject private var store: ProbeStore

    init() {
        let manager = TurnstileManager(siteKey: ProbeConfig.siteKeyPlaceholder)
        let log = ProbeLog()
        let store = ProbeStore(manager: manager, log: log)
        _manager = StateObject(wrappedValue: manager)
        _log = StateObject(wrappedValue: log)
        _store = StateObject(wrappedValue: store)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Turnstile WKWebView Probe (BITB-085)")
                        .font(.headline)

                    // Hidden, alive WKWebView hosting the widget (Android parallel:
                    // the 1.dp TurnstileWebView box).
                    TurnstileWebView(manager: manager, log: log)
                        .frame(width: 1, height: 1)
                        .accessibilityHidden(true)

                    VStack(alignment: .leading, spacing: 6) {
                        Text("Turnstile site key (from /config)").font(.caption)
                        TextField("paste production site key", text: Binding(
                            get: { manager.siteKey },
                            set: { manager.siteKey = $0 }
                        ))
                        .textFieldStyle(.roundedBorder)
                        .font(.system(.body, design: .monospaced))
                        .disableAutocorrection(true)
                        Text("POST target URL (default: production chat endpoint)")
                            .font(.caption)
                        TextField("https://…", text: $store.postURLString)
                            .textFieldStyle(.roundedBorder)
                            .font(.system(.body, design: .monospaced))
                            .keyboardType(.URL)
                            .disableAutocorrection(true)
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        Button("(a) Obtain token → POST (expect 2xx)") {
                            Task { await store.runA() }
                        }
                        .buttonStyle(.borderedProminent)
                        Button("(b) Reuse last token (expect 403/rejected)") {
                            Task { await store.runB() }
                        }
                        .buttonStyle(.bordered)
                        Button("(c) Force 403 → reset → ONE retry") {
                            Task { await store.runC() }
                        }
                        .buttonStyle(.bordered)
                        Button("(d) Suppress tokens → timeout/fail-open") {
                            Task { await store.runD() }
                        }
                        .buttonStyle(.bordered)
                        Button("Manual: requestReset() widget") {
                            manager.requestReset()
                        }
                        .buttonStyle(.bordered)
                        Button("Clear log") { log.clear() }
                    }

                    // Copy-pasteable timestamped observation log.
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text("Observation log").font(.headline)
                            Spacer()
                            Button("Copy all") {
                                UIPasteboard.general.string = log.fullText
                                log.add("log copied to pasteboard")
                            }
                        }
                        ScrollView {
                            Text(log.fullText.isEmpty ? "(no observations yet)" : log.fullText)
                                .font(.system(size: 11, design: .monospaced))
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .textSelection(.enabled)
                        }
                        .frame(maxHeight: 320)
                        .padding(6)
                        .background(Color(.secondarySystemBackground))
                        .cornerRadius(8)
                    }
                }
                .padding()
            }
            .navigationTitle("Turnstile Probe")
        }
    }
}
