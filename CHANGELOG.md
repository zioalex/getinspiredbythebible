# Changelog

All notable changes to this project will be documented in this file.

## [0.8.0](https://github.com/zioalex/getinspiredbythebible/compare/v0.7.0...v0.8.0) (2026-05-12)

### Features

* **android:** bug-report email flow for "Send Diagnostic Report" ([#531](https://github.com/zioalex/getinspiredbythebible/issues/531)) ([c8d4a71](https://github.com/zioalex/getinspiredbythebible/commit/c8d4a71897ccc0f74af9967e907a3a6b5c1c0852))
* **legal:** translate Privacy Policy and Terms of Service into 10 languages (BITB-027) ([#532](https://github.com/zioalex/getinspiredbythebible/issues/532)) ([b7d4ed8](https://github.com/zioalex/getinspiredbythebible/commit/b7d4ed88bcf94d1cd73c0c0d8aaf9257bd71fa03))

### Bug Fixes

* **android:** auto-detect language when user has not set an explicit preference ([#530](https://github.com/zioalex/getinspiredbythebible/issues/530)) ([290a107](https://github.com/zioalex/getinspiredbythebible/commit/290a107fc399de889d295ae51a3b9b19351f2cea))
* **android:** show submitting/success/error feedback in diagnostic report sheet ([#540](https://github.com/zioalex/getinspiredbythebible/issues/540)) ([6616d42](https://github.com/zioalex/getinspiredbythebible/commit/6616d42bb13cc84f98e961931ba5275841a1067e))
* **release:** correct CHANGELOG deltas and fix tag creation ([#537](https://github.com/zioalex/getinspiredbythebible/issues/537)) ([f4a45b3](https://github.com/zioalex/getinspiredbythebible/commit/f4a45b3f20413db9915d626fd07893d32f31c89b))

## [0.7.0](https://github.com/zioalex/getinspiredbythebible/compare/v0.6.0...v0.7.0) (2026-05-11)

No user-visible changes in this release (infrastructure/pipeline fixes only).

## [0.6.0](https://github.com/zioalex/getinspiredbythebible/compare/v0.5.0...v0.6.0) (2026-05-10)

### Features

* **android:** add language picker to ChatScreen top app bar ([#527](https://github.com/zioalex/getinspiredbythebible/issues/527)) ([f253460](https://github.com/zioalex/getinspiredbythebible/commit/f253460df4f1bdf468cbc59cea91ff6faf2a837f))
* **api:** BITB-020 — OpenAI Moderation as Stage 2 content safety ([#512](https://github.com/zioalex/getinspiredbythebible/issues/512)) ([a500dea](https://github.com/zioalex/getinspiredbythebible/commit/a500dea44572c753541c769de2e1e3b728e04ea9))

### Bug Fixes

* **frontend:** default verse panel to Referenced filter ([7b72d58](https://github.com/zioalex/getinspiredbythebible/commit/7b72d58f95ca0b442f30593382f22760b35d7f08))

## [0.5.0](https://github.com/zioalex/getinspiredbythebible/compare/v0.4.0...v0.5.0) (2026-05-10)

No user-visible changes in this release.

## [0.4.0](https://github.com/zioalex/getinspiredbythebible/compare/v0.3.0...v0.4.0) (2026-05-10)

### Documentation

* add troubleshooting section to release process ([#523](https://github.com/zioalex/getinspiredbythebible/issues/523)) ([478a8b3](https://github.com/zioalex/getinspiredbythebible/commit/478a8b34e42e52045284dcb5fa635dff049b1efe))

## [0.3.0](https://github.com/zioalex/getinspiredbythebible/compare/v0.2.0...v0.3.0) (2026-05-10)

### Features

* **BITB-027:** surface content safety signals in LLM responses ([#516](https://github.com/zioalex/getinspiredbythebible/issues/516)) ([358d8ea](https://github.com/zioalex/getinspiredbythebible/commit/358d8ea359100121adab86380b76ba39fac5c486))

## [0.2.0](https://github.com/zioalex/getinspiredbythebible/compare/v0.1.0...v0.2.0) (2026-05-10)

### Features

* **android:** add BITB-026 story for Settings UX improvements ([#504](https://github.com/zioalex/getinspiredbythebible/issues/504)) ([80ebccf](https://github.com/zioalex/getinspiredbythebible/commit/80ebccfef54326aae3887a6e896acff6289c19a2))
* **android:** switch language picker to AppCompatDelegate.setApplicationLocales ([#502](https://github.com/zioalex/getinspiredbythebible/issues/502)) ([c764c60](https://github.com/zioalex/getinspiredbythebible/commit/c764c601dd5c98f0f45da975ce8bb8003833b6fd))
* **frontend:** add changelog page and what's-new modal ([#474](https://github.com/zioalex/getinspiredbythebible/issues/474)) ([85f771a](https://github.com/zioalex/getinspiredbythebible/commit/85f771aaedaaa205e80a8bffa7a776a88ec809c5))

### Bug Fixes

* **android:** declare AD_ID usage for Firebase Analytics ([#500](https://github.com/zioalex/getinspiredbythebible/issues/500)) ([5496298](https://github.com/zioalex/getinspiredbythebible/commit/5496298dcaab6d930465894136069689e925f267))
* **android:** eliminate NetworkOnMainThreadException and HTTP 403 in chatStream ([#509](https://github.com/zioalex/getinspiredbythebible/issues/509)) ([ee45ca2](https://github.com/zioalex/getinspiredbythebible/commit/ee45ca250f48500e2b736470e9aac176a59c0df9))
* **android:** exclude play-services-ads-identifier from firebase-analytics ([#490](https://github.com/zioalex/getinspiredbythebible/issues/490)) ([8591d62](https://github.com/zioalex/getinspiredbythebible/commit/8591d6203cd8ff1705e651fe98ae62d2b2b46d7a))
* **android:** live language swap via Compose, no Activity recreate ([#488](https://github.com/zioalex/getinspiredbythebible/issues/488)) ([99fa77e](https://github.com/zioalex/getinspiredbythebible/commit/99fa77eed4888561b70ce98cbd03555b5692ded4))
* **android:** make debug APK always installable alongside release ([#505](https://github.com/zioalex/getinspiredbythebible/issues/505)) ([87aa5f1](https://github.com/zioalex/getinspiredbythebible/commit/87aa5f1b705895503846fd9d2ddf141ae1485408))
* **android:** override attachBaseContext so language selection actually changes UI strings ([#485](https://github.com/zioalex/getinspiredbythebible/issues/485)) ([7f3d8a5](https://github.com/zioalex/getinspiredbythebible/commit/7f3d8a51a531a804e5f2665818ca3341d634e6f4))
* **android:** provide LocalResources so language picker actually changes UI strings ([#487](https://github.com/zioalex/getinspiredbythebible/issues/487)) ([2991e95](https://github.com/zioalex/getinspiredbythebible/commit/2991e95594ca5d9e35ee246496211901fc7c9fc6))
* **android:** provide LocalResources so language picker actually swaps strings ([#501](https://github.com/zioalex/getinspiredbythebible/issues/501)) ([bbbc484](https://github.com/zioalex/getinspiredbythebible/commit/bbbc4846b8bbdb7e025149435106b60c6289c7b4))
* **android:** remove AD_ID permission auto-merged by Play Services ([#489](https://github.com/zioalex/getinspiredbythebible/issues/489)) ([a103b6b](https://github.com/zioalex/getinspiredbythebible/commit/a103b6bfefa26ae8a151a62e8e9d0f819dca5e97))
* **android-publish:** use Unix-epoch timestamp for versionCode ([#480](https://github.com/zioalex/getinspiredbythebible/issues/480)) ([930a695](https://github.com/zioalex/getinspiredbythebible/commit/930a695f4c4e2ed84d2d5961c9b05e8fe61c2f54))
* **ci:** escape ${{...}} in android-debug.yml comment ([#495](https://github.com/zioalex/getinspiredbythebible/issues/495)) ([eb8a68e](https://github.com/zioalex/getinspiredbythebible/commit/eb8a68e19818989cbe84393747772c555bd45d44))
* **ci:** skip processReleaseGoogleServices in debug workflow ([#497](https://github.com/zioalex/getinspiredbythebible/issues/497)) ([3b9e70f](https://github.com/zioalex/getinspiredbythebible/commit/3b9e70f8a621fd0c42cbc38edb369a8a000a9da7))
* **ci:** use processReleaseManifest in debug workflow ([#496](https://github.com/zioalex/getinspiredbythebible/issues/496)) ([db2d6d1](https://github.com/zioalex/getinspiredbythebible/commit/db2d6d1257f839866067e7591467e672f918911f))
* **frontend:** complete smart auto-scroll — reset on send + i18n scroll button ([#508](https://github.com/zioalex/getinspiredbythebible/issues/508)) ([7e61b92](https://github.com/zioalex/getinspiredbythebible/commit/7e61b92f76a495558fde4e17ef48518472f449b6))
* **frontend:** repair /[locale]/privacy, /[locale]/terms, and changelog pages ([#498](https://github.com/zioalex/getinspiredbythebible/issues/498)) ([9775aa0](https://github.com/zioalex/getinspiredbythebible/commit/9775aa05e79ce0a29a98779ad22917b3a9f4ab06))

### Reverts

* **android:** restore manifest + build.gradle.kts to pre-AD_ID-fix state ([#491](https://github.com/zioalex/getinspiredbythebible/issues/491)) ([85448a2](https://github.com/zioalex/getinspiredbythebible/commit/85448a2babf981007285d8ecea34b48cf4c16bd1))

### Documentation

* **backlog:** add BITB-029 for bible version visibility and version-query guidance ([#518](https://github.com/zioalex/getinspiredbythebible/issues/518)) ([a6392b8](https://github.com/zioalex/getinspiredbythebible/commit/a6392b8cfe24e803925c27e1fd5ca13df020d5d2))
* **release:** add Issues:write to RELEASE_PLEASE_TOKEN requirements ([#517](https://github.com/zioalex/getinspiredbythebible/issues/517)) ([a323f44](https://github.com/zioalex/getinspiredbythebible/commit/a323f448e3635a9de2b923fbdc7ff763e01b3bbb))
* **release:** clarify single-branch model and stale --release-notes ([#515](https://github.com/zioalex/getinspiredbythebible/issues/515)) ([22c69d4](https://github.com/zioalex/getinspiredbythebible/commit/22c69d45741edb74d2e82bf0a285c2b302d4611f))

## [0.1.0](https://github.com/zioalex/getinspiredbythebible) (2026-05-03)

### Features

* Initial public release of Vox Quieta — multilingual Bible inspiration app.
* Multilingual support across 11 locales (en, it, de, es, fr, pt, ar, ru, zh, hi, ko).
* Privacy policy and terms of service pages with per-locale routing.
* AI-powered scripture recommendations via semantic search.
* Changelog page at /[locale]/changelog with release history.
