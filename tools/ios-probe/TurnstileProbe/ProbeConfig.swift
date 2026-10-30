import Foundation

/// Defaults and placeholders for the probe. Everything is editable in-app
/// (ContentView exposes the fields), so nothing needs to be recompiled to
/// switch between production and a test endpoint.
///
/// The maintainer pastes the production site key from the site's `/config`
/// endpoint (the same source Android's `BuildConfig`-backed HTML uses).
enum ProbeConfig {
    /// Production frontend origin — used as the WKWebView `baseURL` so the
    /// Turnstile widget sees the same origin Android does
    /// (`loadDataWithBaseURL(BuildConfig.FRONTEND_URL, ...)`).
    static let frontendBaseURL = URL(string: "https://voxquieta.org")!

    /// Default POST target: the production API chat endpoint. Overridable
    /// in-app to any URL (e.g. a local/test endpoint).
    static let defaultPostURLString = "https://voxquieta.org/api/v1/chat"

    /// Placeholder shown in the site-key field until the maintainer pastes
    /// the real key from https://voxquieta.org/config (`turnstile_site_key`).
    static let siteKeyPlaceholder = "0x4AAAAAACaR4GHzrw8fgN5O"

    /// Minimal valid `ChatRequest` body for the production chat endpoint.
    static let chatBody = """
    {"message":"Turnstile iOS WKWebView probe","include_search":false}
    """

    // Android reference constants (TurnstileInterceptor.kt companion):
    static let tokenWaitSeconds: TimeInterval = 5
    static let retryTokenWaitSeconds: TimeInterval = 8
}
