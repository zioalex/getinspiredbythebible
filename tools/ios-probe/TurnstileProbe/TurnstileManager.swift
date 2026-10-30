import Foundation

/// Swift mirror of the Android reference
/// `android/.../security/TurnstileManager.kt`:
///  - single cached `token` (StateFlow -> @Published)
///  - `hasError` fail-open flag set by the widget's error callback
///  - `requestReset()` clears the token and signals the WebView to re-render
///  - `onTokenConsumed()` is a semantic alias for `requestReset()`
///
/// `resetHandler` is installed by the WKWebView wrapper and evaluates
/// `window.resetWidget()` (falling back to a reload) — the Android parallel
/// is the WebView collecting `resetTrigger`.
final class TurnstileManager: ObservableObject {

    @Published private(set) var token: String?
    @Published private(set) var hasError = false

    /// Current site key for the widget page. ContentView keeps this in sync
    /// with the editable field (placeholder loaded from ProbeConfig); reload
    /// the page after changing it.
    var siteKey: String

    /// Set by TurnstileWebView; re-renders the widget in the page.
    var resetHandler: (() -> Void)?

    /// (d) timeout test hook: when true, incoming tokens are discarded so the
    /// interceptor path can be observed failing open. Not in the Android
    /// manager — it stands in for the Android test's ability to suppress the
    /// WebView's token delivery.
    var suppressTokens = false

    func onTokenReceived(_ newToken: String) {
        if suppressTokens {
            return
        }
        token = newToken
        hasError = false
    }

    func onTokenExpired() {
        token = nil
    }

    func onError(_ code: String) {
        token = nil
        hasError = true
    }

    /// Clears the cached token immediately and asks the WebView to re-render
    /// the widget so a fresh single-use token is obtained.
    func requestReset() {
        token = nil
        resetHandler?()
    }

    /// Semantic alias for requestReset() — call wherever a token has just
    /// been consumed by the server (matches Android exactly).
    func onTokenConsumed() {
        requestReset()
    }
}
