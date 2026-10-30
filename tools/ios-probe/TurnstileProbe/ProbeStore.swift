import Foundation

/// Swift port of the Android reference interceptor behavior
/// (`TurnstileInterceptor.kt:24-83`):
///  - POST-only attach: the token header is attached only when we have one
///    (probe only issues POSTs, matching the gated endpoints).
///  - single-use: every attached-token request consumes the token,
///    regardless of upstream status.
///  - 403: requestReset() → await fresh token (8s) → EXACTLY one retry,
///    then stop (fail-open last resort is logged, not silently re-sent).
///  - 5s initial wait / 8s retry wait, fail-open, no hang.
@MainActor
final class ProbeStore: ObservableObject {

    let manager: TurnstileManager
    let log: ProbeLog

    /// URL of the POST target (default: production chat endpoint; editable).
    @Published var postURLString = ProbeConfig.defaultPostURLString

    /// Last token actually attached to a request, kept for the (b)
    /// single-use reuse test.
    @Published private(set) var lastAttachedToken: String?

    /// Number of times the 403 path re-sent the request (must be 0 or 1).
    @Published private(set) var lastRetryCount = 0

    private var inFlight = false

    init(manager: TurnstileManager, log: ProbeLog) {
        self.manager = manager
        self.log = log
    }

    // MARK: Waits (Android: awaitTokenOrNull / awaitFreshTokenOrNull)

    /// Bounded 5s wait for the WebView to deliver a token. Fail-open:
    /// returns nil on timeout or widget error, so the request still goes out.
    private func awaitTokenOrNull(timeout: TimeInterval = ProbeConfig.tokenWaitSeconds) async -> String? {
        if manager.hasError {
            log.add("wait: widget in error state — failing open (no wait)")
            return nil
        }
        log.add("wait: up to \(Int(timeout))s for a token…")
        let start = Date()
        while Date().timeIntervalSince(start) < timeout {
            if let token = manager.token { return token }
            if manager.hasError {
                log.add("wait: widget errored during wait — failing open")
                return nil
            }
            try? await Task.sleep(nanoseconds: 100_000_000)
        }
        log.add("wait: \(Int(timeout))s elapsed with no token — failing open")
        return nil
    }

    /// Like awaitTokenOrNull but does NOT short-circuit on hasError and
    /// waits 8s — used only on the 403-retry path (Android parity).
    private func awaitFreshTokenOrNull(timeout: TimeInterval = ProbeConfig.retryTokenWaitSeconds) async -> String? {
        log.add("retry-wait: up to \(Int(timeout))s for a fresh token (no error short-circuit)…")
        let start = Date()
        while Date().timeIntervalSince(start) < timeout {
            if let token = manager.token { return token }
            try? await Task.sleep(nanoseconds: 100_000_000)
        }
        log.add("retry-wait: \(Int(timeout))s elapsed with no fresh token — last resort: stop, log, no hang")
        return nil
    }

    // MARK: POST path

    /// Single POST through the interceptor-equivalent path.
    /// `forceToken` lets the caller bypass the manager (tests (b) reuse and
    /// (c) stale-403); `consumeAttached` toggles the single-use consume.
    private func post(forceToken: String?, consumeAttached: Bool = true) async -> Int {
        let token = forceToken ?? await awaitTokenOrNull()
        if let token {
            log.add("POST: attaching X-Turnstile-Token \(token.prefix(12))…")
        } else {
            log.add("POST: no token — sending WITHOUT header (fail-open)")
        }
        let (status, _) = await send(token: token)
        log.add("POST: response status \(status)")
        if let token, consumeAttached {
            lastAttachedToken = token
            // Single-use: consume on EVERY attached request, regardless of
            // upstream status (Android parity).
            manager.onTokenConsumed()
            log.add("single-use: token consumed (manager cleared, widget reset)")
        }

        // 403-retry path (POST-only, matching the Android needsToken gate).
        if status == 403 {
            log.add("403: stale/missing token — requestReset() then EXACTLY one retry")
            manager.requestReset()
            lastRetryCount = 0
            if let fresh = await awaitFreshTokenOrNull() {
                log.add("403: retrying once with fresh token \(fresh.prefix(12))…")
                let (retryStatus, _) = await send(token: fresh)
                lastRetryCount = 1
                log.add("403: retry response status \(retryStatus) (retries=1)")
                manager.onTokenConsumed()
                return retryStatus
            }
            // Last resort (Android parity: chain.proceed(original) without a
            // token) — bounded, logged, no hang.
            log.add("403: last resort — retrying WITHOUT token (fail-open)")
            let (finalStatus, _) = await send(token: nil)
            lastRetryCount = 1
            return finalStatus
        }
        return status
    }

    private func send(token: String?) async -> (Int, Data?) {
        guard let url = URL(string: postURLString) else {
            log.add("POST: INVALID URL '\(postURLString)'")
            return (-1, nil)
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token {
            request.setValue(token, forHTTPHeaderField: "X-Turnstile-Token")
        }
        request.httpBody = Data(ProbeConfig.chatBody.utf8)
        request.timeoutInterval = 30
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            let status = (response as? HTTPURLResponse)?.statusCode ?? -1
            if status >= 400, let body = String(data: data.prefix(300), encoding: .utf8) {
                log.add("POST: error body: \(body)")
            }
            return (status, data)
        } catch {
            log.add("POST: transport error: \(error.localizedDescription)")
            return (-2, nil)
        }
    }

    // MARK: Checklist buttons

    /// (a) Fresh token + POST succeeds.
    func runA() async {
        guard busyGuard() else { return }
        log.add("=== (a) fresh token → POST ===")
        let status = await post(forceToken: nil)
        log.add("=== (a) done: status \(status) — pass if 200/2xx ===")
        inFlight = false
    }

    /// (b) Single-use: re-send the SAME token; Cloudflare must reject it
    /// (timeout-or-duplicate → expect 403).
    func runB() async {
        guard busyGuard() else { return }
        log.add("=== (b) single-use: re-attach last token ===")
        guard let lastAttachedToken else {
            log.add("=== (b) skipped: no previously attached token — run (a) first ===")
            inFlight = false
            return
        }
        // Do NOT consume: we are explicitly testing reuse of a spent token.
        let status = await post(forceToken: lastAttachedToken, consumeAttached: false)
        log.add("=== (b) done: status \(status) — pass if 403/4xx-rejected (consumed, not reusable) ===")
        inFlight = false
    }

    /// (c) Force a 403 with a stale token; verify widget reset, fresh token,
    /// exactly one retry.
    func runC() async {
        guard busyGuard() else { return }
        log.add("=== (c) forced 403 with stale token → reset → fresh → ONE retry ===")
        lastRetryCount = 0
        let status = await post(forceToken: "STALE-TOKEN-FORCED-403-PROBE")
        log.add("=== (c) done: status \(status), retryCount=\(lastRetryCount) — pass if retryCount == 1 ===")
        inFlight = false
    }

    /// (d) Timeout behavior: suppress token delivery; verify the 5s initial
    /// and 8s retry waits elapse and fail open without a hang.
    func runD() async {
        guard busyGuard() else { return }
        log.add("=== (d) timeout: tokens suppressed → waits must elapse & fail open ===")
        manager.suppressTokens = true
        manager.requestReset()
        log.add("(d) tokens suppressed; initial wait starts now")
        let start = Date()
        _ = await post(forceToken: nil)
        let elapsed1 = Date().timeIntervalSince(start)
        log.add("(d) first POST elapsed \(String(format: "%.1f", elapsed1))s (expect ≥5s wait then sent WITHOUT token)")
        manager.suppressTokens = false
        log.add("=== (d) done: fail-open elapsed \(String(format: "%.1f", elapsed1))s, no hang ===")
        inFlight = false
    }

    private func busyGuard() -> Bool {
        if inFlight {
            log.add("busy: a probe run is already in flight — wait for it to finish")
            return false
        }
        inFlight = true
        return true
    }
}
