# Security Issues Tracker

This document tracks known security findings that require remediation.

---

## Android OWASP Dependency Check Findings

**Status:** 🔴 Unresolved (continue-on-error workaround in place)
**Date Discovered:** 2026-02-24
**Source:** First OWASP scan of Android project (PR #196)
**CI Run:** <https://github.com/zioalex/getinspiredbythebible/actions/runs/22351535839>
**Priority:** P1 (High) — Security debt blocking proper CI enforcement

### Summary

- **Total Unique CVEs:** 24
- **Critical:** 0
- **High:** 11 (2 are CISA Known Exploited Vulnerabilities)
- **Medium:** 13
- **Low:** 0

### CVE Details

#### High Severity (11 CVEs)

| CVE | CVSS | Dep | Description |
|-----|------|-----|-------------|
| [CVE-2021-33813](https://nvd.nist.gov/vuln/detail/CVE-2021-33813) | 8.9 | `jdom2-2.0.6.jar` | XXE in SAXBuilder — DoS via crafted HTTP request |
| [CVE-2023-31582](https://nvd.nist.gov/vuln/detail/CVE-2023-31582) | 9.6 | `jose4j-0.7.0.jar` | Low iteration count in PBKDF2 — weak key derivation |
| [CVE-2023-44487](https://nvd.nist.gov/vuln/detail/CVE-2023-44487) | 7.5 | `grpc-api-1.57.0.jar` | **🔴 CISA KEV** — HTTP/2 Rapid Reset Attack (DoS) |
| [CVE-2024-29371](https://nvd.nist.gov/vuln/detail/CVE-2024-29371) | 9.6 | `jose4j-0.7.0.jar` | DoS via crafted JWT parsing in jose4j |
| [CVE-2024-7254](https://nvd.nist.gov/vuln/detail/CVE-2024-7254) | 8.7 | `protobuf-java-3.22.3.jar` | Unbounded recursion in protobuf parsing — DoS |
| [CVE-2025-24970](https://nvd.nist.gov/vuln/detail/CVE-2025-24970) | 7.5 | `netty-*-4.1.93.Final.jar` | SslHandler buffer OOB read — crash in TLS handling |
| [CVE-2025-55163](https://nvd.nist.gov/vuln/detail/CVE-2025-55163) | 8.2 | `netty-*-4.1.93.Final.jar` | **🔴 CISA KEV** — Netty HTTP request smuggling |
| [CVE-2025-58056](https://nvd.nist.gov/vuln/detail/CVE-2025-58056) | 7.5 | `netty-*-4.1.93.Final.jar` | Netty DoS via malformed HTTP requests |
| [CVE-2025-58057](https://nvd.nist.gov/vuln/detail/CVE-2025-58057) | 7.5 | `netty-*-4.1.93.Final.jar` | Netty DoS via malformed HTTP requests |
| [CVE-2026-22816](https://nvd.nist.gov/vuln/detail/CVE-2026-22816) | 9.3 | `gradle-8.4.2.jar` *(build tool)* | Gradle native-platform path traversal (build-time only) |
| [CVE-2026-22865](https://nvd.nist.gov/vuln/detail/CVE-2026-22865) | 9.3 | `gradle-8.4.2.jar` *(build tool)* | Gradle native-platform path traversal variant (build-time only) |

#### Medium Severity (13 CVEs)

| CVE | CVSS | Dep | Description |
|-----|------|-----|-------------|
| [CVE-2018-1000840](https://nvd.nist.gov/vuln/detail/CVE-2018-1000840) | 6.5 | `symbol-processing-api-2.0.21-1.0.28.jar` *(build tool)* | XXE in Processing Foundation libs (KSP plugin) |
| [CVE-2021-4277](https://nvd.nist.gov/vuln/detail/CVE-2021-4277) | 5.3 | `common-31.4.2.jar` | Unvalidated redirect in fredsmith utilities |
| [CVE-2023-34462](https://nvd.nist.gov/vuln/detail/CVE-2023-34462) | 6.5 | `netty-*-4.1.93.Final.jar` | Netty stack overflow on large ALPN extensions |
| [CVE-2023-51775](https://nvd.nist.gov/vuln/detail/CVE-2023-51775) | 9.4 | `jose4j-0.7.0.jar` | DoS via PBKDF2 work factor in jose4j ≤0.9.3 |
| [CVE-2024-25710](https://nvd.nist.gov/vuln/detail/CVE-2024-25710) | 5.5 | `commons-compress-1.21.jar` | Infinite loop in malformed Zip/7z entries — DoS |
| [CVE-2024-26308](https://nvd.nist.gov/vuln/detail/CVE-2024-26308) | 5.5 | `commons-compress-1.21.jar` | OOM via unbounded resource allocation in PACK200 |
| [CVE-2024-29025](https://nvd.nist.gov/vuln/detail/CVE-2024-29025) | 5.3 | `netty-*-4.1.93.Final.jar` | Netty HTTP post form data accumulation — DoS |
| [CVE-2024-47535](https://nvd.nist.gov/vuln/detail/CVE-2024-47535) | 5.5 | `netty-*-4.1.93.Final.jar` | Netty native libs write to temp dir with wrong perms |
| [CVE-2024-47554](https://nvd.nist.gov/vuln/detail/CVE-2024-47554) | N/A | `commons-io-2.13.0.jar` | Uncontrolled resource consumption in Commons IO |
| [CVE-2024-7246](https://nvd.nist.gov/vuln/detail/CVE-2024-7246) | 6.3 | `grpc-api-1.57.0.jar` | gRPC client can poison proxy cache headers |
| [CVE-2025-25193](https://nvd.nist.gov/vuln/detail/CVE-2025-25193) | 5.5 | `netty-*-4.1.93.Final.jar` | Netty native lib temp file disclosure |
| [CVE-2025-48924](https://nvd.nist.gov/vuln/detail/CVE-2025-48924) | 5.3 | `kotlin-gradle-plugin-2.0.21.jar` *(build tool)* | Commons Lang uncontrolled recursion (shaded dep) |
| [CVE-2025-67735](https://nvd.nist.gov/vuln/detail/CVE-2025-67735) | 6.5 | `netty-*-4.1.93.Final.jar` | Netty HTTP/2 stream handling — DoS |

### Affected Dependency Groups

| Dependency Group | CVE Count | Scope |
|-----------------|-----------|-------|
| `io.netty:netty-*` 4.1.93.Final | 10 | App runtime (gRPC transport) |
| `org.jose4j:jose4j` 0.7.0 | 3 | App runtime (JWT library) |
| `io.grpc:grpc-*` 1.57.0 | 2 | App runtime (gRPC client) |
| `com.google.protobuf:protobuf-java` 3.22.3 | 1 | App runtime |
| `org.apache.commons:commons-compress` 1.21 | 2 | App runtime |
| `org.apache.commons:commons-io` 2.13.0 | 1 | App runtime |
| `org.jdom:jdom2` 2.0.6 | 1 | App runtime |
| `gradle` 8.4.2 | 2 | **Build tooling only** |
| `com.google.devtools.ksp:symbol-processing-*` | 1 | **Build tooling only** |
| `kotlin-gradle-plugin` 2.0.21 | 1 | **Build tooling only** |

> **Note:** Build tooling CVEs (gradle, KSP, kotlin-gradle-plugin) only affect the
> build environment, not the deployed APK. They should still be addressed but pose
> lower runtime risk.

### Current Workaround

`.github/workflows/android-ci.yml` has `continue-on-error: true` on the OWASP step.
This allows PRs to pass CI but CVEs remain unaddressed.

### Remediation Plan

1. **Triage findings** — Separate false positives from real vulnerabilities
   - Gradle CVEs (CVE-2026-22816, CVE-2026-22865): Build-time only, low runtime risk
   - KSP/kotlin-gradle CVEs: Build-time only, may be false positives
   - Netty CVEs: Likely from gRPC transitive dependencies — check if netty is actually bundled in APK
   - jose4j CVEs: Verify if jose4j is actually used in the Android app

2. **Suppress false positives** — Document in `android/dependency-check-suppressions.xml`

3. **Fix real CVEs:**
   - Upgrade `io.netty:netty-*` from 4.1.93 → latest (≥4.1.118.Final fixes most CVEs)
   - Upgrade `io.grpc:grpc-*` from 1.57.0 → latest stable (≥1.68.0)
   - Upgrade `org.jose4j:jose4j` from 0.7.0 → ≥0.9.6
   - Upgrade `com.google.protobuf:protobuf-java` from 3.22.3 → ≥3.25.5
   - Upgrade `org.apache.commons:commons-compress` from 1.21 → ≥1.27
   - Upgrade `org.apache.commons:commons-io` from 2.13.0 → ≥2.17
   - Upgrade `org.jdom:jdom2` from 2.0.6 → ≥2.0.7 (or suppress if indirect)
   - Upgrade `gradle` from 8.4.2 → ≥9.3.0 (fixes CVE-2026-22816, CVE-2026-22865)

4. **Remove `continue-on-error`** — Restore blocking behavior once CVEs are addressed

### CISA Known Exploited Vulnerabilities (Highest Priority)

These two CVEs are on the CISA KEV catalog and should be fixed first:

- **CVE-2023-44487** (HTTP/2 Rapid Reset, CVSS 7.5) — Fix: upgrade `grpc-*` to ≥1.60
- **CVE-2025-55163** (Netty HTTP smuggling, CVSS 8.2) — Fix: upgrade `netty-*` to ≥4.1.118

### References

- Failing CI run: <https://github.com/zioalex/getinspiredbythebible/actions/runs/22351535839>
- OWASP report artifact: `dependency-check-report` (3.5 MB HTML)
- Related PRs: #184, #188, #196
- OWASP Dependency Check docs: <https://owasp.org/www-project-dependency-check/>

### Acceptance Criteria

- [ ] All CISA KEV CVEs (CVE-2023-44487, CVE-2025-55163) fixed
- [ ] All High (CVSS ≥ 7.0) CVEs fixed, suppressed with justification, or documented as accepted risk
- [ ] Medium CVEs triaged and remediation plan documented
- [ ] Build-tooling CVEs (Gradle, KSP) assessed — suppress if build-only risk
- [ ] `continue-on-error: true` removed from `android-ci.yml`
- [ ] OWASP check blocks PRs with new CVEs above CVSS 7.0

---

**Last Updated:** 2026-02-24
