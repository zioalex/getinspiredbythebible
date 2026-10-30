import SwiftUI
import WebKit
import Combine

/// Local HTML that mirrors `android/app/src/main/assets/turnstile.html`,
/// with the site key injected by Swift and the JS->Swift bridge posted
/// through `window.webkit.messageHandlers.turnstileBridge` instead of
/// the Android `Android` JavascriptInterface.
///
/// Loaded with `baseURL = https://voxquieta.org` so the Turnstile widget
/// validates against the production hostname — the exact parallel of
/// Android's `loadDataWithBaseURL(BuildConfig.FRONTEND_URL, ...)`.
enum TurnstileHTML {
    static func page(siteKey: String) -> String {
        """
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8"/>
          <meta name="viewport" content="width=device-width, initial-scale=1"/>
        </head>
        <body>
          <div id="cf-turnstile"></div>
          <script src="https://challenges.cloudflare.com/turnstile/v0/api.js?onload=onTurnstileLoad" async defer></script>
          <script>
            function post(type, value) {
              window.webkit.messageHandlers.turnstileBridge.postMessage(
                { type: type, value: value === undefined ? null : String(value) });
            }
            function onTurnstileLoad() {
              turnstile.render('#cf-turnstile', {
                sitekey: '\(siteKey)',
                theme: 'light',
                callback: function(token) { post('token', token); },
                'expired-callback': function() { post('expired'); },
                'error-callback': function(code) { post('error', code); }
              });
              window.resetWidget = function() {
                turnstile.reset('#cf-turnstile');
              };
            }
          </script>
        </body>
        </html>
        """
    }
}

/// Swift mirror of the Android `TurnstileWebView.kt`:
/// a hidden WebView hosting the widget (Android: 1.dp box), a JS bridge
/// (`WKScriptMessageHandler` standing in for `@JavascriptInterface`),
/// `window.resetWidget()` on reset, and reload-with-backoff error recovery
/// (1s initial, doubling, capped at 8s, max 5 attempts).
struct TurnstileWebView: UIViewRepresentable {
    @ObservedObject var manager: TurnstileManager
    @ObservedObject var log: ProbeLog

    static let bridgeName = "turnstileBridge"

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        let controller = WKUserContentController()
        controller.add(context.coordinator, name: Self.bridgeName)
        config.userContentController = controller
        let webView = WKWebView(frame: .zero, configuration: config)
        #if DEBUG
        if #available(iOS 16.4, *) {
            webView.isInspectable = true
        }
        #endif
        // Hidden-but-alive, like Android's 1.dp box: zero height, never clipped
        // out of the hierarchy (a removed WebView stops the widget).
        webView.frame = CGRect(x: 0, y: 0, width: 1, height: 1)
        webView.alpha = 0.01
        context.coordinator.webView = webView
        load(webView)
        context.coordinator.startErrorRecovery()
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        // Nothing to update per-render; the page is static, resets go
        // through the coordinator's resetHandler.
    }

    private func load(_ webView: WKWebView) {
        let html = TurnstileHTML.page(siteKey: manager.siteKey)
        webView.loadHTMLString(html, baseURL: ProbeConfig.frontendBaseURL)
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(manager: manager, log: log, load: load)
    }

    final class Coordinator: NSObject, WKScriptMessageHandler {
        private let manager: TurnstileManager
        private let log: ProbeLog
        private let load: (WKWebView) -> Void
        private var recoveryTask: Task<Void, Never>?
        private var cancellables = Set<AnyCancellable>()
        weak var webView: WKWebView?

        init(manager: TurnstileManager, log: ProbeLog, load: @escaping (WKWebView) -> Void) {
            self.manager = manager
            self.log = log
            self.load = load
            super.init()
            manager.resetHandler = { [weak self] in
                guard let self, let webView = self.webView else { return }
                self.log.add("reset: evaluating window.resetWidget()")
                webView.evaluateJavaScript("window.resetWidget ? window.resetWidget() : null") { [weak self] _, error in
                    if let error {
                        self?.log.add("reset: resetWidget undefined/error (\(error.localizedDescription)) — reloading page")
                        self?.load(webView)
                    } else {
                        self?.log.add("reset: window.resetWidget() called")
                    }
                }
            }
        }

        func userContentController(_ userContentController: WKUserContentController,
                                   didReceive message: WKScriptMessage) {
            guard let body = message.body as? [String: Any],
                  let type = body["type"] as? String else { return }
            let value = body["value"] as? String
            switch type {
            case "token":
                log.add("widget: token received (\(value?.prefix(12) ?? "nil")…)")
                manager.onTokenReceived(value ?? "")
            case "expired":
                log.add("widget: token expired (expired-callback)")
                manager.onTokenExpired()
            case "error":
                log.add("widget: error-callback code=\(value ?? "nil")")
                manager.onError(value ?? "unknown")
            default:
                break
            }
        }

        /// Reload-with-backoff error recovery, mirroring TurnstileWebView.kt:
        /// on hasError, wait 1s, reload; double up to 8s, max 5 attempts.
        /// Runs on the main actor like the Android collectLatest on Main.
        func startErrorRecovery() {
            manager.$hasError
                .receive(on: DispatchQueue.main)
                .sink { [weak self] hasError in
                    guard let self, hasError else { return }
                    self.recoveryTask?.cancel()
                    self.recoveryTask = Task { [weak self] in
                        guard let self else { return }
                        var backoff: TimeInterval = 1
                        for _ in 0..<5 {
                            try? await Task.sleep(nanoseconds: UInt64(backoff * 1_000_000_000))
                            guard !Task.isCancelled, self.manager.hasError else { return }
                            self.log.add("recovery: widget in error state — reloading (backoff \(Int(backoff))s)")
                            if let webView = self.webView { self.load(webView) }
                            backoff = min(backoff * 2, 8)
                        }
                        self.log.add("recovery: 5 reload attempts exhausted, widget still in error (fail-open)")
                    }
                }
                .store(in: &cancellables)
        }
    }
}
