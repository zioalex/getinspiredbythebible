# Changelog

All notable changes to this project will be documented in this file.

## [1.54.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.53.0...v1.54.0) (2026-09-05)


### Features

* **android:** normalize Traditional Chinese book names in verse parsing (BITB-110) ([#1034](https://github.com/zioalex/getinspiredbythebible/issues/1034)) ([3c3f0c6](https://github.com/zioalex/getinspiredbythebible/commit/3c3f0c6535f49bb6182d1814e3185b63e9f33070))
* **android:** support Android 7.x tablets (BITB-122) ([#1041](https://github.com/zioalex/getinspiredbythebible/issues/1041)) ([dcd3785](https://github.com/zioalex/getinspiredbythebible/commit/dcd3785060af72a202f5a35169d22b85afa369b5))
* **ci:** populate verse_topics on every seed and alarm when coverage collapses (BITB-105) ([#1019](https://github.com/zioalex/getinspiredbythebible/issues/1019)) ([66f0814](https://github.com/zioalex/getinspiredbythebible/commit/66f08144273f4b605b1fc5a5a6c37e9e99b32d36))
* **search-eval:** make the golden set validate topic boosting (BITB-103) ([#1023](https://github.com/zioalex/getinspiredbythebible/issues/1023)) ([5ca9f89](https://github.com/zioalex/getinspiredbythebible/commit/5ca9f89d2dac3ba053ecc1bccd925b512229f311))
* **search-eval:** un-stub topic_boosted eval config and fix boost truncation bug (BITB-104) ([#1032](https://github.com/zioalex/getinspiredbythebible/issues/1032)) ([2d4ed40](https://github.com/zioalex/getinspiredbythebible/commit/2d4ed40f1a89e374e36dbe711b819a1451776945))


### Bug Fixes

* **android:** bound verse-parser connector regex to close ReDoS gap (BITB-114) ([#1033](https://github.com/zioalex/getinspiredbythebible/issues/1033)) ([77b9204](https://github.com/zioalex/getinspiredbythebible/commit/77b920422e8a779aa04c8774db48dc5b4fd1b356))
* **api,android:** attribute Android sessions correctly in weekly report ([#1038](https://github.com/zioalex/getinspiredbythebible/issues/1038)) ([fd017d7](https://github.com/zioalex/getinspiredbythebible/commit/fd017d7b2e9bd096ced9db05004482846d6454dc))
* **api:** remove init_db()/create_all() now that Alembic owns the schema (BITB-090) ([#1035](https://github.com/zioalex/getinspiredbythebible/issues/1035)) ([3327157](https://github.com/zioalex/getinspiredbythebible/commit/3327157e687a2d22140744592fdf8dcc5d9c0b98))
* **ci:** encode eval-prod's DB password and surface its failure log (BITB-101) ([#1020](https://github.com/zioalex/getinspiredbythebible/issues/1020)) ([31cf078](https://github.com/zioalex/getinspiredbythebible/commit/31cf078724abc550110f2cc5204a8a13c0d7be04))
* **ci:** make both search-eval routes actually run (BITB-107 + BITB-101) ([#1018](https://github.com/zioalex/getinspiredbythebible/issues/1018)) ([6de7cb7](https://github.com/zioalex/getinspiredbythebible/commit/6de7cb7e22ae9cabf54d74abf27ebefc5168ddd9))
* **ci:** report what the search-eval and verse_topics jobs actually did ([#1022](https://github.com/zioalex/getinspiredbythebible/issues/1022)) ([ee87867](https://github.com/zioalex/getinspiredbythebible/commit/ee878675c8a71aa5f5f69add9199c538a1547fd5))
* **db:** read-only Postgres role for the nightly search-eval harness (BITB-101) ([#1017](https://github.com/zioalex/getinspiredbythebible/issues/1017)) ([78b3101](https://github.com/zioalex/getinspiredbythebible/commit/78b31011a0dcaef8c4dc2d5f9d18bd2736fc847c))
* **deploy:** percent-encode the DB password at every DSN site (BITB-112) ([#1021](https://github.com/zioalex/getinspiredbythebible/issues/1021)) ([f4328a9](https://github.com/zioalex/getinspiredbythebible/commit/f4328a9ff4396631e24466df3c3f2592ced3ffcf))
* **frontend:** bound verse-parser connector regex to close ReDoS gap (BITB-108) ([#1024](https://github.com/zioalex/getinspiredbythebible/issues/1024)) ([12129b6](https://github.com/zioalex/getinspiredbythebible/commit/12129b6a104547fa6297f64f651e5e43cd2863a3))


### Documentation

* add BITB-115 — Bible version sticks to old language after switch ([#1039](https://github.com/zioalex/getinspiredbythebible/issues/1039)) ([252780b](https://github.com/zioalex/getinspiredbythebible/commit/252780bb34b4697aba6bea2104a6d78c5f926c17))
* add BITB-115 backlog story for flexible session message limit ([#1036](https://github.com/zioalex/getinspiredbythebible/issues/1036)) ([edddb92](https://github.com/zioalex/getinspiredbythebible/commit/edddb92202413e1c087e8ef9e22fd31f26308f70))
* add BITB-119 and BITB-120 voice feature stories ([#1037](https://github.com/zioalex/getinspiredbythebible/issues/1037)) ([e78629a](https://github.com/zioalex/getinspiredbythebible/commit/e78629a0eda0f4e91b19c91646b7762122a12bbe))
* **ios:** record provisional BITB-085 SwiftUI delivery decision ([#1040](https://github.com/zioalex/getinspiredbythebible/issues/1040)) ([d7078fe](https://github.com/zioalex/getinspiredbythebible/commit/d7078fe99141906c7bb21fc2ac448853ea9f5502))
* **migrations:** enforce lock_timeout and make safety rules checkable (BITB-100) ([#1015](https://github.com/zioalex/getinspiredbythebible/issues/1015)) ([194059f](https://github.com/zioalex/getinspiredbythebible/commit/194059ffb46fdc7cfcb1f04ebcbd50c491893ad0))

## [1.53.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.52.0...v1.53.0) (2026-08-22)

### Features

* **api:** ask one clarifying question on a vague first message (BITB-078) ([#956](https://github.com/zioalex/getinspiredbythebible/issues/956)) ([9c71ab6](https://github.com/zioalex/getinspiredbythebible/commit/9c71ab6681006ddae9b50fb586a0ab6565f28c0f))
* **api:** emit server-side citation spans on the completion event (BITB-086) ([#985](https://github.com/zioalex/getinspiredbythebible/issues/985)) ([3d0f80b](https://github.com/zioalex/getinspiredbythebible/commit/3d0f80b589937530810e4b4c25eecd09c01d1a62))
* **api:** seed verse_topics from the topic keyword map (BITB-044) ([#970](https://github.com/zioalex/getinspiredbythebible/issues/970)) ([d99c3ac](https://github.com/zioalex/getinspiredbythebible/commit/d99c3ac58feca992d108c37b1ba6a4b7effce284))
* **ci:** automate search-eval prod + smoke runs (BITB-051 P4a) ([#968](https://github.com/zioalex/getinspiredbythebible/issues/968)) ([be311a5](https://github.com/zioalex/getinspiredbythebible/commit/be311a55939e0104696a7f055cc51f7dabf2e167))
* **scripture:** recognize Traditional Chinese verse references (BITB-025) ([#982](https://github.com/zioalex/getinspiredbythebible/issues/982)) ([fce7c48](https://github.com/zioalex/getinspiredbythebible/commit/fce7c4817855cac2541a286b0ba05002668bfa20))
* **web:** generate the localized book-name map instead of hand-maintaining it (BITB-059) ([#983](https://github.com/zioalex/getinspiredbythebible/issues/983)) ([38d71fa](https://github.com/zioalex/getinspiredbythebible/commit/38d71fa73730ddfc85a8b5ae8142e3e3624a24aa))
* **web:** installable PWA manifest, iOS safe areas, and Add to Home Screen CTA (BITB-084) ([#969](https://github.com/zioalex/getinspiredbythebible/issues/969)) ([58b23d5](https://github.com/zioalex/getinspiredbythebible/commit/58b23d50cd88bba1c90a25595e73cea921b6a09a))

### Bug Fixes

* **android:** send example prompt on first tap regardless of Turnstile readiness (BITB-081) ([#957](https://github.com/zioalex/getinspiredbythebible/issues/957)) ([e84b56e](https://github.com/zioalex/getinspiredbythebible/commit/e84b56e5bc1c26aaa219a8f9f3776b080628a938))
* **api:** remove stale mypy suppressions in scripture search routes (BITB-009) ([#984](https://github.com/zioalex/getinspiredbythebible/issues/984)) ([468417a](https://github.com/zioalex/getinspiredbythebible/commit/468417a2ab660aa94dd7571d1ae0f48d9a730b25))
* **ci:** sequence deploy pipeline correctly around migrations (BITB-097) ([#1005](https://github.com/zioalex/getinspiredbythebible/issues/1005)) ([073b7f0](https://github.com/zioalex/getinspiredbythebible/commit/073b7f068bb8f5bbafc8950a147fd1f191d9c7b3))
* **deploy:** auto-remediate origin cert binding on post-deploy 525/526 (BITB-067) ([#967](https://github.com/zioalex/getinspiredbythebible/issues/967)) ([2592386](https://github.com/zioalex/getinspiredbythebible/commit/259238657f07f13bf514a61fd3a4a3563542d895))

### Documentation

* **backlog:** file BITB-101 and the BITB-044 follow-up chain (BITB-103..106) ([#1007](https://github.com/zioalex/getinspiredbythebible/issues/1007)) ([eb00cd9](https://github.com/zioalex/getinspiredbythebible/commit/eb00cd94e6dc6b59f1474302ee1bc3314625b340))
* **backlog:** file BITB-107..111 for gaps found across the open PRs ([#1008](https://github.com/zioalex/getinspiredbythebible/issues/1008)) ([e2e5145](https://github.com/zioalex/getinspiredbythebible/commit/e2e51450ec1aa6b970d5a465b21c3755e7c67e0d))

## [1.52.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.51.0...v1.52.0) (2026-08-20)

### Features

* **api:** add persisted generated tsvector column on verses (BITB-062) ([#955](https://github.com/zioalex/getinspiredbythebible/issues/955)) ([fe1d69f](https://github.com/zioalex/getinspiredbythebible/commit/fe1d69f47eb8f12fd267cabac3dad1386a49f50f))
* **ci:** deploy Alembic migrations from the pipeline (BITB-089) ([#974](https://github.com/zioalex/getinspiredbythebible/issues/974)) ([ca23ac5](https://github.com/zioalex/getinspiredbythebible/commit/ca23ac580679332b4f9e7b2463f0dbdbfccf19c1))
* **db:** prove the deploy pipeline reaches production (BITB-089) ([#987](https://github.com/zioalex/getinspiredbythebible/issues/987)) ([c3f7448](https://github.com/zioalex/getinspiredbythebible/commit/c3f7448020381d9a6c8e3f2ee7ee6adaf41a9f4b))
* **db:** reconcile the production schema with the ORM models (BITB-093) ([#980](https://github.com/zioalex/getinspiredbythebible/issues/980)) ([d71e148](https://github.com/zioalex/getinspiredbythebible/commit/d71e148a14db0c52d8d1089b0327e00d002ba292))
* **db:** remove the pipeline probe comment (BITB-089) ([#990](https://github.com/zioalex/getinspiredbythebible/issues/990)) ([eed8584](https://github.com/zioalex/getinspiredbythebible/commit/eed85840a72b8a2ab642c9f02912dab9df1e58a1))

### Bug Fixes

* **db:** persist the verse tsvector in a side table, not a rewrite (BITB-096) ([#1001](https://github.com/zioalex/getinspiredbythebible/issues/1001)) ([9840e8b](https://github.com/zioalex/getinspiredbythebible/commit/9840e8b23725091bee89ff6f7db42aad337389a2))
* **dev:** restore local database initialization (BITB-092) ([#973](https://github.com/zioalex/getinspiredbythebible/issues/973)) ([4881561](https://github.com/zioalex/getinspiredbythebible/commit/4881561c0a50820617df994d9513a4419a80430a))
* **infra:** let Azure own storage_mb once auto-grow is enabled ([#1002](https://github.com/zioalex/getinspiredbythebible/issues/1002)) ([afebd76](https://github.com/zioalex/getinspiredbythebible/commit/afebd76b85622a8c0fdbd7b129fe285370a76a78))
* **scripts:** make a failed rehearsal connection say what to do ([#986](https://github.com/zioalex/getinspiredbythebible/issues/986)) ([548b5ec](https://github.com/zioalex/getinspiredbythebible/commit/548b5ec1416349a24bd21f8725d4cc233f06913b))
* **scripts:** restore the Alembic rehearsal targets lost when [#975](https://github.com/zioalex/getinspiredbythebible/issues/975) merged ([#981](https://github.com/zioalex/getinspiredbythebible/issues/981)) ([b52af26](https://github.com/zioalex/getinspiredbythebible/commit/b52af268f49aeeb619f90bae08bb496b5f3cab7e))

### Performance Improvements

* **api:** read the persisted tsvector in ts_rank instead of recomputing it (BITB-095) ([#1003](https://github.com/zioalex/getinspiredbythebible/issues/1003)) ([1cb0ac9](https://github.com/zioalex/getinspiredbythebible/commit/1cb0ac9d966fd111ce1762259e70dd4866df970b))

### Documentation

* **backlog:** file the column-type audit as BITB-094 ([#988](https://github.com/zioalex/getinspiredbythebible/issues/988)) ([18ecc5e](https://github.com/zioalex/getinspiredbythebible/commit/18ecc5e87bc9e3aa5fa7933270757c81145a8396))
* **backlog:** mark BITB-089 and BITB-093 done ([#989](https://github.com/zioalex/getinspiredbythebible/issues/989)) ([2f54792](https://github.com/zioalex/getinspiredbythebible/commit/2f54792376ab40fb7d621b153b3e3c79397fd4d3))
* point migration guide to Alembic tests ([#971](https://github.com/zioalex/getinspiredbythebible/issues/971)) ([c6be70b](https://github.com/zioalex/getinspiredbythebible/commit/c6be70b272b787a47d04032f5c2997020820fe18))
* retrospective on the tsvector migration outage, plus BITB-100 ([#1004](https://github.com/zioalex/getinspiredbythebible/issues/1004)) ([5141e20](https://github.com/zioalex/getinspiredbythebible/commit/5141e203291ff067bf5e14219668d11758c5fee1))

## [1.51.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.50.1...v1.51.0) (2026-07-31)

### Features

* **api:** add Alembic migration framework (BITB-004) ([#948](https://github.com/zioalex/getinspiredbythebible/issues/948)) ([b81d85b](https://github.com/zioalex/getinspiredbythebible/commit/b81d85bc76dc59f9faed050948ed06620110b4a6))

### Bug Fixes

* **api:** emit the verseless-response SLI on the non-stream chat path (BITB-055) ([#953](https://github.com/zioalex/getinspiredbythebible/issues/953)) ([4b54fcf](https://github.com/zioalex/getinspiredbythebible/commit/4b54fcf5668b499f71570299fba183206972673a))

### Documentation

* **backlog:** track the Alembic adoption follow-ups as BITB-089/090/091 ([#952](https://github.com/zioalex/getinspiredbythebible/issues/952)) ([8a3e1d4](https://github.com/zioalex/getinspiredbythebible/commit/8a3e1d4e6454ef6175a291d6d52521d01646a053))
* **ops:** add database backup & restore runbook ([#951](https://github.com/zioalex/getinspiredbythebible/issues/951)) ([e0c7f5c](https://github.com/zioalex/getinspiredbythebible/commit/e0c7f5c6f3756e12df7451810f4ad02bbc52fc9a))

## [1.50.1](https://github.com/zioalex/getinspiredbythebible/compare/v1.50.0...v1.50.1) (2026-07-30)

### Documentation

* plan the iOS launch as five staged backlog stories (BITB-084…088) ([#949](https://github.com/zioalex/getinspiredbythebible/issues/949)) ([b9e0281](https://github.com/zioalex/getinspiredbythebible/commit/b9e028179dd4d2dcb11c186fb3ec848e6f6b90f7))

## [1.50.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.49.0...v1.50.0) (2026-07-29)

### Features

* **android:** add About settings row + first-run intro sheet (BITB-082) ([#941](https://github.com/zioalex/getinspiredbythebible/issues/941)) ([c0aec69](https://github.com/zioalex/getinspiredbythebible/commit/c0aec69bee9d020bbf5412202b3d645c3ce4344e))
* **web:** give the About page a more personal voice (BITB-083) ([#947](https://github.com/zioalex/getinspiredbythebible/issues/947)) ([c3760ce](https://github.com/zioalex/getinspiredbythebible/commit/c3760ceeae47d703a94e51fb178765e002cbe270))

### Bug Fixes

* **api:** raise chat message limit to 500 and publish via /config (BITB-075) ([#944](https://github.com/zioalex/getinspiredbythebible/issues/944)) ([749c302](https://github.com/zioalex/getinspiredbythebible/commit/749c3020cec70f018cfd7926a7cbd0bf0e793f86))
* **frontend:** make chat page footer links reachable (BITB-079) ([#945](https://github.com/zioalex/getinspiredbythebible/issues/945)) ([47e44de](https://github.com/zioalex/getinspiredbythebible/commit/47e44deb26d3e1a1a10a88def1f7f9fc8bf563ce))

### Documentation

* **backlog:** capture About page personal-voice follow-up (BITB-083) ([#943](https://github.com/zioalex/getinspiredbythebible/issues/943)) ([460a9df](https://github.com/zioalex/getinspiredbythebible/commit/460a9df801d224103575ecd25cd0eace5963cdf5))

## [1.49.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.48.0...v1.49.0) (2026-07-27)

### Features

* **api:** cache embedding provider calls (BITB-057 Phase 2) ([#886](https://github.com/zioalex/getinspiredbythebible/issues/886)) ([f96d226](https://github.com/zioalex/getinspiredbythebible/commit/f96d2267b0deb1f91d0447eb7007ca9974d4e942))
* **api:** propagate request ID into SQL queries as a comment (BITB-008) ([#929](https://github.com/zioalex/getinspiredbythebible/issues/929)) ([8850491](https://github.com/zioalex/getinspiredbythebible/commit/8850491bca3603631327e3bf1feda6f575e0ab72))
* **search-eval:** add retrieval runner + report/CLI (BITB-051 P3) ([#881](https://github.com/zioalex/getinspiredbythebible/issues/881)) ([14810f4](https://github.com/zioalex/getinspiredbythebible/commit/14810f422ff3a6db52cacd8ccb7e695ffadfb1d5))
* **verse-parser:** generate Android book-name map from single JSON source (BITB-059 Phase 1) ([#926](https://github.com/zioalex/getinspiredbythebible/issues/926)) ([2417373](https://github.com/zioalex/getinspiredbythebible/commit/241737352510bf2b0d2fbd0fd89894360f0da21d))
* **web:** add About page and one-time intro modal (BITB-076, BITB-077) ([#939](https://github.com/zioalex/getinspiredbythebible/issues/939)) ([482658c](https://github.com/zioalex/getinspiredbythebible/commit/482658c7933bccc3c117eeef6c03972041df9a3b))

### Bug Fixes

* **api:** split dev/prod Python requirements (BITB-073) ([#928](https://github.com/zioalex/getinspiredbythebible/issues/928)) ([0b49837](https://github.com/zioalex/getinspiredbythebible/commit/0b498375730e259bd058357647e68d5c5c0c5d7e))
* **deploy:** decouple probe-secret rotation from backend app replacement (BITB-067) ([#896](https://github.com/zioalex/getinspiredbythebible/issues/896)) ([a0099cd](https://github.com/zioalex/getinspiredbythebible/commit/a0099cd048f0ee883531505d610ec59ff7c4226b))
* **dev-env:** correct db firewall Makefile CLI flags, add stale-rule cleanup ([#885](https://github.com/zioalex/getinspiredbythebible/issues/885)) ([3bce7f0](https://github.com/zioalex/getinspiredbythebible/commit/3bce7f098eaf954ec68f4c29e5e70a3628edd18a))
* **frontend:** seed splash state deterministically to avoid SSR/CSR hydration mismatch ([#917](https://github.com/zioalex/getinspiredbythebible/issues/917)) ([24285e2](https://github.com/zioalex/getinspiredbythebible/commit/24285e28c9d5b7c1254a48171990838e3f5a9771))
* **frontend:** show email-specific error on contact form 422 (BITB-052) ([#930](https://github.com/zioalex/getinspiredbythebible/issues/930)) ([a75477f](https://github.com/zioalex/getinspiredbythebible/commit/a75477fb90e60c07d2c17648a91b027a94df7109))
* **verse-parser:** recognize रोमियो alias and preserve full verse ranges ([#903](https://github.com/zioalex/getinspiredbythebible/issues/903)) ([f39ff94](https://github.com/zioalex/getinspiredbythebible/commit/f39ff94780adbd6107491a48406c5200e32e695f))

### Documentation

* add BITB-074 research and user story for a support-us funding feature ([#924](https://github.com/zioalex/getinspiredbythebible/issues/924)) ([7ef74c1](https://github.com/zioalex/getinspiredbythebible/commit/7ef74c11321221c460958b93127995bfb9378344))
* **android:** add Play Console compliance checklist for policy updates ([#902](https://github.com/zioalex/getinspiredbythebible/issues/902)) ([59eb6e6](https://github.com/zioalex/getinspiredbythebible/commit/59eb6e6445081fee2a344f2f1de816a25f81cd7f))
* **backlog:** close out BITB-073 (PR [#928](https://github.com/zioalex/getinspiredbythebible/issues/928) merged, move to DONE) ([#932](https://github.com/zioalex/getinspiredbythebible/issues/932)) ([7a81a55](https://github.com/zioalex/getinspiredbythebible/commit/7a81a554f0ec49652bcdc6662e14a16eabd024c7))
* **backlog:** product review batch (BITB-075…081) — message limit, About page, UX fixes ([#931](https://github.com/zioalex/getinspiredbythebible/issues/931)) ([3e5031d](https://github.com/zioalex/getinspiredbythebible/commit/3e5031d64644bf99b967978598630a0a65069628))
* **content:** dev-process content kit + recover Models & harness metrics section + PR template ([#865](https://github.com/zioalex/getinspiredbythebible/issues/865)) ([9ae0711](https://github.com/zioalex/getinspiredbythebible/commit/9ae071176052978356aa58c2076870967cb0312c))
* **legal:** disclose third-party AI processing in privacy policy ([#900](https://github.com/zioalex/getinspiredbythebible/issues/900)) ([9a3f261](https://github.com/zioalex/getinspiredbythebible/commit/9a3f261033da5042571d05d8fad36d6b9ced731b))

## [1.48.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.47.0...v1.48.0) (2026-07-22)

### Features

* **frontend,android:** add language/Bible-version/community entries to the hamburger menu ([#921](https://github.com/zioalex/getinspiredbythebible/issues/921)) ([afbe106](https://github.com/zioalex/getinspiredbythebible/commit/afbe106ebb7b425520309d0ab4e4a8efcf54ca37))

### Bug Fixes

* **android:** remove staleness gate blocking in-app update prompts ([#919](https://github.com/zioalex/getinspiredbythebible/issues/919)) ([fe716af](https://github.com/zioalex/getinspiredbythebible/commit/fe716af07da8453dbe9e4ee8b9c71b45bf5dc1f6))
* **ci:** route multi-line docker tags through env:, not raw ${{ }} splice ([#922](https://github.com/zioalex/getinspiredbythebible/issues/922)) ([fe63044](https://github.com/zioalex/getinspiredbythebible/commit/fe630447f243ad55e8695891fa5b9a630c0f2b35))

## [1.47.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.46.2...v1.47.0) (2026-07-21)

### Features

* **frontend:** add official app story page and demote beta CTA ([#915](https://github.com/zioalex/getinspiredbythebible/issues/915)) ([4c06bf4](https://github.com/zioalex/getinspiredbythebible/commit/4c06bf47161a4ad4e6f7699bde821cbcf578147a))
* **frontend:** privacy-first local conversation history ([#882](https://github.com/zioalex/getinspiredbythebible/issues/882)) ([4681957](https://github.com/zioalex/getinspiredbythebible/commit/4681957917cc58ab9a411c50d140e8722cfe9cdc))
* **monitoring:** alert on backend/frontend Container App saturation + chat TTFT p95 ([#918](https://github.com/zioalex/getinspiredbythebible/issues/918)) ([0b54645](https://github.com/zioalex/getinspiredbythebible/commit/0b546450e4eccb962a3b05717f3c8d4452b16e3e))

### Bug Fixes

* **android:** prevent FOREIGN KEY crash when saving a message for a deleted conversation ([#878](https://github.com/zioalex/getinspiredbythebible/issues/878)) ([53ad1fb](https://github.com/zioalex/getinspiredbythebible/commit/53ad1fb99dee7d1fe8e7184f2b9f6cb0da00c561))
* **api:** stop .dockerignore from excluding the reports/ package ([#920](https://github.com/zioalex/getinspiredbythebible/issues/920)) ([7294122](https://github.com/zioalex/getinspiredbythebible/commit/729412210ad1bb9d2de03acce5eccad7dc5883f3))
* **rate-limiter:** apply BITB-061 migrations to local/CI Postgres, add fail-closed alert ([#907](https://github.com/zioalex/getinspiredbythebible/issues/907)) ([b694665](https://github.com/zioalex/getinspiredbythebible/commit/b69466553825d9a6dcf8da7457f5ba323fb37125))
* **security:** route public semantic search through the index-friendly candidate-pool pattern (BITB-062) ([#877](https://github.com/zioalex/getinspiredbythebible/issues/877)) ([83ecf2d](https://github.com/zioalex/getinspiredbythebible/commit/83ecf2d3a7abaa89eb034e0bfc989111de8c44b8))
* **security:** shared Postgres rate limiter across replicas (BITB-061) ([#866](https://github.com/zioalex/getinspiredbythebible/issues/866)) ([6822694](https://github.com/zioalex/getinspiredbythebible/commit/68226944666ffb1c67edb1827e2e6effea29d702))
* **weekly-report:** track sessions on the streaming chat endpoint ([#875](https://github.com/zioalex/getinspiredbythebible/issues/875)) ([3690671](https://github.com/zioalex/getinspiredbythebible/commit/36906713703aa0f06b6e365494ef52e85e732463))

### Documentation

* **backlog:** add BITB-069 story for Menge-Bibel German default ([#910](https://github.com/zioalex/getinspiredbythebible/issues/910)) ([bfd48ed](https://github.com/zioalex/getinspiredbythebible/commit/bfd48edf95b40f3f339a748dbd9844d9d857a386))

## [1.46.2](https://github.com/zioalex/getinspiredbythebible/compare/v1.46.1...v1.46.2) (2026-07-18)

### Bug Fixes

* **monitoring:** stop paging llama-guard-primary-failure-rate on baseline noise ([#898](https://github.com/zioalex/getinspiredbythebible/issues/898)) ([47a485f](https://github.com/zioalex/getinspiredbythebible/commit/47a485f0c18c2db9343611d7fd753375e0713ddd))
* **monitoring:** stop paging Sev1 backend-5xx-rate on expected 4xx ([#897](https://github.com/zioalex/getinspiredbythebible/issues/897)) ([d1abaf8](https://github.com/zioalex/getinspiredbythebible/commit/d1abaf8f0f992129db02084316342e31a49f34eb))

## [1.46.1](https://github.com/zioalex/getinspiredbythebible/compare/v1.46.0...v1.46.1) (2026-07-17)

### Bug Fixes

* **verses:** normalize non-ASCII digits in verse-link chapter/verse parsing ([#893](https://github.com/zioalex/getinspiredbythebible/issues/893)) ([5f55b2a](https://github.com/zioalex/getinspiredbythebible/commit/5f55b2a40d85fa57f5859260de1688f5d569a5d4))

### Documentation

* **backlog:** mark BITB-071 done, move story to docs/DONE/ ([#895](https://github.com/zioalex/getinspiredbythebible/issues/895)) ([e514ee8](https://github.com/zioalex/getinspiredbythebible/commit/e514ee8590aeed0cfbecf35e75e5f5ba3b10a391))

## [1.46.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.45.1...v1.46.0) (2026-07-17)

### Features

* **translations:** commit Hindi IRV Bible data, fix loader/license config ([#890](https://github.com/zioalex/getinspiredbythebible/issues/890)) ([b05e432](https://github.com/zioalex/getinspiredbythebible/commit/b05e4321994785db47712ed96e78b415a0f4d831))

### Bug Fixes

* **deploy:** grant deploy SP roleAssignments/write on the Log Analytics workspace ([#891](https://github.com/zioalex/getinspiredbythebible/issues/891)) ([38b27c4](https://github.com/zioalex/getinspiredbythebible/commit/38b27c47ea337631a20d742d4795d2941f2a0492))

### Documentation

* **backlog:** add BITB-070 to re-evaluate hybrid content-safety mode ([#888](https://github.com/zioalex/getinspiredbythebible/issues/888)) ([32d52ab](https://github.com/zioalex/getinspiredbythebible/commit/32d52ab7c995179764b94817ef888a0ca266014a))

## [1.45.1](https://github.com/zioalex/getinspiredbythebible/compare/v1.45.0...v1.45.1) (2026-07-17)

### Bug Fixes

* **security:** close content-safety fail-open gaps in the abuse-control stack (BITB-061) ([#840](https://github.com/zioalex/getinspiredbythebible/issues/840)) ([d65e0ac](https://github.com/zioalex/getinspiredbythebible/commit/d65e0ac30e2fe239f73151c1fd218623d8b45b68))

## [1.45.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.44.0...v1.45.0) (2026-07-16)

### Features

* **android:** show "What's New" bottom sheet on first launch after update (BITB-058) ([#879](https://github.com/zioalex/getinspiredbythebible/issues/879)) ([e64210f](https://github.com/zioalex/getinspiredbythebible/commit/e64210fbe37412e1f421a3f074f7831009b177ef))
* **monitoring:** inline the failing sample + RequestIds in Telegram alerts ([#880](https://github.com/zioalex/getinspiredbythebible/issues/880)) ([dc4d131](https://github.com/zioalex/getinspiredbythebible/commit/dc4d131ce2d96a0885759938b31d658f2bbc28c6))

## [1.44.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.43.0...v1.44.0) (2026-07-12)

### Features

* **android:** add in-app update flow (flexible) (BITB-057) ([#863](https://github.com/zioalex/getinspiredbythebible/issues/863)) ([a98e4e2](https://github.com/zioalex/getinspiredbythebible/commit/a98e4e2eae52793d1f2ac711d2c6146f00dce1b0))

### Bug Fixes

* **dev-env:** make local dev and local-prod environments actually startable ([#861](https://github.com/zioalex/getinspiredbythebible/issues/861)) ([c7072b0](https://github.com/zioalex/getinspiredbythebible/commit/c7072b011bc0def857678b4043dce441f7efc3ed))

## [1.43.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.42.1...v1.43.0) (2026-07-11)

### Features

* **language:** readiness guard so a default Bible is never served before it's loaded ([#858](https://github.com/zioalex/getinspiredbythebible/issues/858)) ([c242ee2](https://github.com/zioalex/getinspiredbythebible/commit/c242ee2d6df8a04f0c9d29f2ec49e03230632d0c))

### Bug Fixes

* **openrouter:** give language-override route the same fallback resilience ([#859](https://github.com/zioalex/getinspiredbythebible/issues/859)) ([8537716](https://github.com/zioalex/getinspiredbythebible/commit/8537716a56aa18246e69bc51ee59fa3000d603c0))

### Documentation

* **backlog:** add BITB-068 per-language model fallback chain ([#860](https://github.com/zioalex/getinspiredbythebible/issues/860)) ([4137583](https://github.com/zioalex/getinspiredbythebible/commit/41375830c56bbaf5ba7c0fd271af9bd2871fae56))
* **backlog:** close BITB-067 gap [#1](https://github.com/zioalex/getinspiredbythebible/issues/1), scope gap [#6](https://github.com/zioalex/getinspiredbythebible/issues/6) secret-rotation fix ([#856](https://github.com/zioalex/getinspiredbythebible/issues/856)) ([8d6af63](https://github.com/zioalex/getinspiredbythebible/commit/8d6af63c043f8e2afba53a98ca079bbd1941895a))

## [1.42.1](https://github.com/zioalex/getinspiredbythebible/compare/v1.42.0...v1.42.1) (2026-07-10)

### Documentation

* **backlog:** add BITB-068 to refresh & expand Bible translations ([#852](https://github.com/zioalex/getinspiredbythebible/issues/852)) ([b96f27a](https://github.com/zioalex/getinspiredbythebible/commit/b96f27a1c708a8aa84422831f4a7d4919f1b7ab1))

## [1.42.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.41.0...v1.42.0) (2026-07-10)

### Features

* **translations:** auto-derive seed matrix and add Luther 1912 (German) ([#851](https://github.com/zioalex/getinspiredbythebible/issues/851)) ([7c4c124](https://github.com/zioalex/getinspiredbythebible/commit/7c4c124339394c60d99452700ebf94ec167c742b))

## [1.41.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.40.1...v1.41.0) (2026-07-10)

### Features

* **api:** add Luther 1912 and Elberfelder 1871 German Bible translations (BITB-046) ([#787](https://github.com/zioalex/getinspiredbythebible/issues/787)) ([d4325f8](https://github.com/zioalex/getinspiredbythebible/commit/d4325f825f3b47043f4ace8d18496ca7d6bf2a52))
* **api:** diacritic-insensitive book-name matching + coverage audit (BITB-052) ([#847](https://github.com/zioalex/getinspiredbythebible/issues/847)) ([b279ed2](https://github.com/zioalex/getinspiredbythebible/commit/b279ed24544277fab5a080d6aff7db83d7bb1f10))

### Bug Fixes

* **api:** raise typed error for exhausted LLM providers (BITB-063) ([#843](https://github.com/zioalex/getinspiredbythebible/issues/843)) ([ae4f85d](https://github.com/zioalex/getinspiredbythebible/commit/ae4f85d34a53cb12a77263c59f02a51f5849acee))

## [1.40.1](https://github.com/zioalex/getinspiredbythebible/compare/v1.40.0...v1.40.1) (2026-07-08)

### Bug Fixes

* **android:** 16 KB page-size support — AGP 8.7 + graphics-path pin + CI gate ([#844](https://github.com/zioalex/getinspiredbythebible/issues/844)) ([0da8b1b](https://github.com/zioalex/getinspiredbythebible/commit/0da8b1b19cda909e09ed110a226daa834a0ef51f))
* **monitor:** deploy & smoke-monitor reliability — cert re-bind + smoke-test hardening (BITB-067) ([#845](https://github.com/zioalex/getinspiredbythebible/issues/845)) ([f1d3e6b](https://github.com/zioalex/getinspiredbythebible/commit/f1d3e6b0b0e865fa8384ebfacba0693f0859709b))

## [1.40.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.39.1...v1.40.0) (2026-07-07)

### Features

* **observability:** browser smoke test + backend/frontend error alerting (BITB-064/065/066) ([#839](https://github.com/zioalex/getinspiredbythebible/issues/839)) ([039c741](https://github.com/zioalex/getinspiredbythebible/commit/039c741c1d6de81886c7a3c9bcc17b005d42647c))

### Bug Fixes

* **deploy:** rebind custom domain + origin cert when the backend app is replaced ([#842](https://github.com/zioalex/getinspiredbythebible/issues/842)) ([25faa10](https://github.com/zioalex/getinspiredbythebible/commit/25faa10a1a90242b558c0b2e2b644f9e3f4bb29d))

## [1.39.1](https://github.com/zioalex/getinspiredbythebible/compare/v1.39.0...v1.39.1) (2026-07-05)

### Bug Fixes

* **api:** resolve _IncludedRouter 500 on CORS preflight (FastAPI 0.137 vs OTel) ([#824](https://github.com/zioalex/getinspiredbythebible/issues/824)) ([033ed6b](https://github.com/zioalex/getinspiredbythebible/commit/033ed6b815c7e727cd8f878399614947eb193b4f))

## [1.39.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.38.0...v1.39.0) (2026-07-05)

### Features

* **BITB-053:** ground unquoted/paraphrased verse citations (ships in detect-only mode) ([#785](https://github.com/zioalex/getinspiredbythebible/issues/785)) ([b0d71df](https://github.com/zioalex/getinspiredbythebible/commit/b0d71df5dff41246e662196ce1edc9b18a419402))
* **search-eval:** bitb-051 p2 — golden set + loader + --validate + non-blocking ci ([#795](https://github.com/zioalex/getinspiredbythebible/issues/795)) ([51332f3](https://github.com/zioalex/getinspiredbythebible/commit/51332f384d8bba25aee9fae5f7aa3a9fba349281))
* **seo:** add WebSite/Organization JSON-LD and branded OG image (BITB-037) ([#808](https://github.com/zioalex/getinspiredbythebible/issues/808)) ([c89e9b6](https://github.com/zioalex/getinspiredbythebible/commit/c89e9b69f6adc63b922c2c0affb8cc87cfcbb768))

### Bug Fixes

* **audit-metrics:** harden parser, slim snapshots, detect moved hotspots ([#822](https://github.com/zioalex/getinspiredbythebible/issues/822)) ([2864fbb](https://github.com/zioalex/getinspiredbythebible/commit/2864fbb077cb432b9be8fc4b4ce08b95ea7f2b95))
* **BITB-052:** english abbreviation aliases + case-insensitive book-name normalization ([#791](https://github.com/zioalex/getinspiredbythebible/issues/791)) ([c98ec45](https://github.com/zioalex/getinspiredbythebible/commit/c98ec455061b79aa33f7d8b256bdf6957fc83fb1))
* **security:** make Turnstile fail closed on persistent errors (BITB-061) ([#821](https://github.com/zioalex/getinspiredbythebible/issues/821)) ([26b664b](https://github.com/zioalex/getinspiredbythebible/commit/26b664b1edafe3f7ef7686b5a8531ce01d157959))

## [1.38.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.37.0...v1.38.0) (2026-07-04)

### Features

* **claude:** add risk-auditor subagent for the adversarial risk audit ([#819](https://github.com/zioalex/getinspiredbythebible/issues/819)) ([5381297](https://github.com/zioalex/getinspiredbythebible/commit/538129765c9cfab7d26e43adda9549c31517375b))

## [1.37.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.36.0...v1.37.0) (2026-07-04)

### Features

* **metrics:** add repo productivity analytics tool, dashboard and monthly workflow ([#813](https://github.com/zioalex/getinspiredbythebible/issues/813)) ([e53c559](https://github.com/zioalex/getinspiredbythebible/commit/e53c559eef0dde662bf71cf85a95bd1008c0565d))
* **metrics:** audit trend framework — tools/audit-metrics with report, dashboard and workflow ([#817](https://github.com/zioalex/getinspiredbythebible/issues/817)) ([6556c88](https://github.com/zioalex/getinspiredbythebible/commit/6556c8848485512c3fcac49bac896d894052ff4d))

### Bug Fixes

* **api:** repair weekly report 500 and harden its workflow ([#815](https://github.com/zioalex/getinspiredbythebible/issues/815)) ([0a6b26d](https://github.com/zioalex/getinspiredbythebible/commit/0a6b26ddab11e1249fd438e3bbfd1f4cdd58ffda))
* **BITB-060:** stop email service from blocking the event loop ([#814](https://github.com/zioalex/getinspiredbythebible/issues/814)) ([5737889](https://github.com/zioalex/getinspiredbythebible/commit/57378894d868cfa1f29eec8cb4fa31fe4e2a8c63))

## [1.36.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.35.0...v1.36.0) (2026-07-03)

### Features

* **api:** per-translation data observability + honest unresolved citations (BITB-054) ([#803](https://github.com/zioalex/getinspiredbythebible/issues/803)) ([5b17abf](https://github.com/zioalex/getinspiredbythebible/commit/5b17abfb64ef1f924d20435bd51b42ef5c5d013e))
* **web+android:** one-tap copy of user prompt (BITB-047) ([#771](https://github.com/zioalex/getinspiredbythebible/issues/771)) ([535822b](https://github.com/zioalex/getinspiredbythebible/commit/535822b843fb92fb6da781503de762cce78cfd03))

### Bug Fixes

* **api:** prevent weekly digest crash on missing session analytics ([#811](https://github.com/zioalex/getinspiredbythebible/issues/811)) ([28b0efb](https://github.com/zioalex/getinspiredbythebible/commit/28b0efb1421ccc99c92a0a13169bb362ab662f46))

## [1.35.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.34.4...v1.35.0) (2026-07-03)

### Features

* **android:** negative-feedback reason chips (BITB-042) ([#783](https://github.com/zioalex/getinspiredbythebible/issues/783)) ([3c603e5](https://github.com/zioalex/getinspiredbythebible/commit/3c603e5c2822f6ec6301823fe69f8b89eac0a703))
* **api:** address user's specific focus and improve prophetic-justice expansion (BITB-050) ([#758](https://github.com/zioalex/getinspiredbythebible/issues/758)) ([72c18fc](https://github.com/zioalex/getinspiredbythebible/commit/72c18fc604d2054b573fb5024ade6b5ca253864f))
* **web:** surface Bible version as amber chip badge in header (BITB-029) ([#763](https://github.com/zioalex/getinspiredbythebible/issues/763)) ([2da373a](https://github.com/zioalex/getinspiredbythebible/commit/2da373a5f7c3976f0e8ecb4b5b2f3ebfce96747e))

### Documentation

* **audit:** adversarial risk audit baseline, periodic playbook, /risk-audit command, and top-5 backlog stories ([#809](https://github.com/zioalex/getinspiredbythebible/issues/809)) ([d53ca8c](https://github.com/zioalex/getinspiredbythebible/commit/d53ca8cf9773f5851f4f707e55e5f24f7075d950))

## [1.34.4](https://github.com/zioalex/getinspiredbythebible/compare/v1.34.3...v1.34.4) (2026-07-02)

### Bug Fixes

* **verse-links:** link references everywhere via string-level linkify (web) ([#806](https://github.com/zioalex/getinspiredbythebible/issues/806)) ([7a0cd03](https://github.com/zioalex/getinspiredbythebible/commit/7a0cd03a2870e7a0b435b7c29f15e3f39a043ce7))

## [1.34.3](https://github.com/zioalex/getinspiredbythebible/compare/v1.34.2...v1.34.3) (2026-07-02)

### Bug Fixes

* **verse-links:** accept comma chapter-verse separator (de/fr/it citations) ([#804](https://github.com/zioalex/getinspiredbythebible/issues/804)) ([5ccb9ed](https://github.com/zioalex/getinspiredbythebible/commit/5ccb9ed1903c6efec49a21138af341c7223455c2))

## [1.34.2](https://github.com/zioalex/getinspiredbythebible/compare/v1.34.1...v1.34.2) (2026-07-01)

### Bug Fixes

* **verse-links:** recover references hidden by greedy over-matches (web + android) ([#801](https://github.com/zioalex/getinspiredbythebible/issues/801)) ([0c6396d](https://github.com/zioalex/getinspiredbythebible/commit/0c6396ded48ae80ffa7a263cbc7487a67921395f))

## [1.34.1](https://github.com/zioalex/getinspiredbythebible/compare/v1.34.0...v1.34.1) (2026-07-01)

### Bug Fixes

* safe-filter false positive on German Bible references ([#799](https://github.com/zioalex/getinspiredbythebible/issues/799)) ([6e72186](https://github.com/zioalex/getinspiredbythebible/commit/6e7218623e55df08bbc131200b888783195f442e))

## [1.34.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.33.1...v1.34.0) (2026-07-01)

### Features

* **resilience:** embedding circuit breaker + fail-closed scripture grounding (BITB-057/058) ([#797](https://github.com/zioalex/getinspiredbythebible/issues/797)) ([30392f6](https://github.com/zioalex/getinspiredbythebible/commit/30392f64c8a2e619252e131e866d8da3780fc5a4))

## [1.33.1](https://github.com/zioalex/getinspiredbythebible/compare/v1.33.0...v1.33.1) (2026-06-30)

### Bug Fixes

* **api+ci:** stop readiness-probe flapping; bound + observe upstream dependencies ([#796](https://github.com/zioalex/getinspiredbythebible/issues/796)) ([7d4d73e](https://github.com/zioalex/getinspiredbythebible/commit/7d4d73e7c73fb9bce3974fdf79b2564ad3cd2033))
* **content-filter:** stop blocking ellipses and surface blocked message on Android ([#792](https://github.com/zioalex/getinspiredbythebible/issues/792)) ([a20ed05](https://github.com/zioalex/getinspiredbythebible/commit/a20ed051e0845ebd8302199bad8c9d1b2e1b092a))

## [1.33.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.32.1...v1.33.0) (2026-06-26)

### Features

* **db:** move hnsw.ef_search tuning from migration to connection pool ([#789](https://github.com/zioalex/getinspiredbythebible/issues/789)) ([1787b2f](https://github.com/zioalex/getinspiredbythebible/commit/1787b2f1786f98ce084ffb98152bb98ca7a89bc9))
* **monitoring:** actionable ERROR-level backend alert + DB saturation detection (BITB-056) ([#788](https://github.com/zioalex/getinspiredbythebible/issues/788)) ([ddf4167](https://github.com/zioalex/getinspiredbythebible/commit/ddf4167110458d00e4c58fd4e89d87ead7968877))

## [1.32.1](https://github.com/zioalex/getinspiredbythebible/compare/v1.32.0...v1.32.1) (2026-06-25)

### Performance Improvements

* **search:** partial HNSW indexes, DB pool, B2s SKU + concurrency test ([#784](https://github.com/zioalex/getinspiredbythebible/issues/784)) ([e2a4dcc](https://github.com/zioalex/getinspiredbythebible/commit/e2a4dcce1593488f44b1680c544cbfdf0efc698b))

## [1.32.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.31.1...v1.32.0) (2026-06-23)

### Features

* **api+ci:** instrument scripture pipeline for silent-failure detection (BITB-055) ([#778](https://github.com/zioalex/getinspiredbythebible/issues/778)) ([fdee9d4](https://github.com/zioalex/getinspiredbythebible/commit/fdee9d461e9ec117cdef228e39ff69b6bd91a3e0))

### Performance Improvements

* **api:** parallelize query embed with expansion to trim TTFT ([#776](https://github.com/zioalex/getinspiredbythebible/issues/776)) ([f12b673](https://github.com/zioalex/getinspiredbythebible/commit/f12b673bc82c9d71c0b133bbf09493bae1eb09b1))

## [1.31.1](https://github.com/zioalex/getinspiredbythebible/compare/v1.31.0...v1.31.1) (2026-06-23)

### Bug Fixes

* **frontend:** self-heal Turnstile widget and recover gated POSTs from 403 ([#781](https://github.com/zioalex/getinspiredbythebible/issues/781)) ([475b6c9](https://github.com/zioalex/getinspiredbythebible/commit/475b6c976b4941fe528b3775c8485a97caf98d77))
* recover Turnstile widget to stop chat retry and bug-report 403s ([#779](https://github.com/zioalex/getinspiredbythebible/issues/779)) ([42ea0cb](https://github.com/zioalex/getinspiredbythebible/commit/42ea0cb25e9d23f6c4076e597d54441a2a8a5f19))

## [1.31.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.30.1...v1.31.0) (2026-06-22)

### Features

* **api:** add typo-tolerance guidance to all system prompts (BITB-045) ([#756](https://github.com/zioalex/getinspiredbythebible/issues/756)) ([2f0a3da](https://github.com/zioalex/getinspiredbythebible/commit/2f0a3da38cd998f851c473fa915771f912199b6d))

### Bug Fixes

* **android:** dismiss keyboard on send and always start fresh chat (BITB-048/049) ([#751](https://github.com/zioalex/getinspiredbythebible/issues/751)) ([68c7b47](https://github.com/zioalex/getinspiredbythebible/commit/68c7b47cdbe17f36cebac1ddcb31360717b85bb0))

## [1.30.1](https://github.com/zioalex/getinspiredbythebible/compare/v1.30.0...v1.30.1) (2026-06-21)

### Performance Improvements

* **api:** index-backed hybrid search + working query expansion ([#772](https://github.com/zioalex/getinspiredbythebible/issues/772)) ([ff93286](https://github.com/zioalex/getinspiredbythebible/commit/ff932864c1a19fc51f9b358a0cfa297cd79c1dd2))

## [1.30.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.29.4...v1.30.0) (2026-06-20)

### Features

* **api:** instrument per-stage chat pipeline timing ([#769](https://github.com/zioalex/getinspiredbythebible/issues/769)) ([db7ab72](https://github.com/zioalex/getinspiredbythebible/commit/db7ab722b20151ef6203ce3524b9fc6019619950))

## [1.29.4](https://github.com/zioalex/getinspiredbythebible/compare/v1.29.3...v1.29.4) (2026-06-20)

### Bug Fixes

* **api:** bind embedding via CAST() so asyncpg accepts the vector cast in scripture search ([#768](https://github.com/zioalex/getinspiredbythebible/issues/768)) ([ff455b1](https://github.com/zioalex/getinspiredbythebible/commit/ff455b15d02bf19ce5097f939d13b8912c26f9d1))

### Documentation

* add BITB-053 modern open translations research and BITB-054 first-run feature spotlight ([#757](https://github.com/zioalex/getinspiredbythebible/issues/757)) ([8f9c407](https://github.com/zioalex/getinspiredbythebible/commit/8f9c407357a414d4ec3e46254a42f0c33ff8bb41))
* **backlog:** add BITB-055 scripture/chat pipeline observability story ([#765](https://github.com/zioalex/getinspiredbythebible/issues/765)) ([ea97f8b](https://github.com/zioalex/getinspiredbythebible/commit/ea97f8b0cb72ada86b92b7cffec31a25e1e5366e))

## [1.29.3](https://github.com/zioalex/getinspiredbythebible/compare/v1.29.2...v1.29.3) (2026-06-20)

### Bug Fixes

* **api:** remove misplaced # nosec that broke all scripture search SQL ([#764](https://github.com/zioalex/getinspiredbythebible/issues/764)) ([32f12dc](https://github.com/zioalex/getinspiredbythebible/commit/32f12dce7f4d437b7392bfcb7582e0a08fdfb72b))

## [1.29.2](https://github.com/zioalex/getinspiredbythebible/compare/v1.29.1...v1.29.2) (2026-06-19)

### Bug Fixes

* **api:** parse parenthesized verse references so grounding resolves them ([#759](https://github.com/zioalex/getinspiredbythebible/issues/759)) ([28dccb9](https://github.com/zioalex/getinspiredbythebible/commit/28dccb901dd145eab0d22b227d2a1c63b2f8be94))

## [1.29.1](https://github.com/zioalex/getinspiredbythebible/compare/v1.29.0...v1.29.1) (2026-06-19)

### Bug Fixes

* **android:** show email-specific error on contact 422 and require email (BITB-051) ([#750](https://github.com/zioalex/getinspiredbythebible/issues/750)) ([cd5b8d3](https://github.com/zioalex/getinspiredbythebible/commit/cd5b8d3b30be4257192baf622ae988cdad4dcecf))

## [1.29.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.28.0...v1.29.0) (2026-06-18)

### Features

* **api:** retrieval-eval core + harness stories (BITB-051 P1) ([#745](https://github.com/zioalex/getinspiredbythebible/issues/745)) ([a5c4868](https://github.com/zioalex/getinspiredbythebible/commit/a5c4868a20cbd7ea33f3a92968ee324ce5062ed3))

### Bug Fixes

* **chat:** ground inline verse quotes against the real Bible text ([#755](https://github.com/zioalex/getinspiredbythebible/issues/755)) ([324b064](https://github.com/zioalex/getinspiredbythebible/commit/324b064ebb4b7de576c209f46a20ca3670162b70))

## [1.28.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.27.0...v1.28.0) (2026-06-16)

### Features

* **api:** enable hybrid search by default + form-data security fix (BITB-043) ([#727](https://github.com/zioalex/getinspiredbythebible/issues/727)) ([44bb168](https://github.com/zioalex/getinspiredbythebible/commit/44bb168ee6496df173abb1c133ab9aa884cfc5a3))

## [1.27.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.26.0...v1.27.0) (2026-06-14)

### Features

* **api:** enable query_expansion_enabled by default ([#741](https://github.com/zioalex/getinspiredbythebible/issues/741)) ([98418bd](https://github.com/zioalex/getinspiredbythebible/commit/98418bd922d2bf5be93b2f5ff8fe4bc5cd64d16e))

### Bug Fixes

* **android:** make user-query text selection readable in both themes ([#743](https://github.com/zioalex/getinspiredbythebible/issues/743)) ([c04652e](https://github.com/zioalex/getinspiredbythebible/commit/c04652e3f2583f087a90fc9bd5870ac8af8fefae))

## [1.26.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.25.2...v1.26.0) (2026-06-13)

### Features

* **android:** language-mismatch switch suggestion banner (BITB-040 slice 3) ([#737](https://github.com/zioalex/getinspiredbythebible/issues/737)) ([6b587a9](https://github.com/zioalex/getinspiredbythebible/commit/6b587a9cad3f757064e8edad9bf23a63d5a936d2))
* **api:** improve search thematic relevance and response depth (BITB-050) ([#735](https://github.com/zioalex/getinspiredbythebible/issues/735)) ([76cc90b](https://github.com/zioalex/getinspiredbythebible/commit/76cc90b5fe66d3e72d52b940de844189cb8fdde6))

### Bug Fixes

* **android:** prevent white screen when resuming app from background ([#740](https://github.com/zioalex/getinspiredbythebible/issues/740)) ([ae1374b](https://github.com/zioalex/getinspiredbythebible/commit/ae1374bc0ccd5c3765103656bb43d3308f91d839))
* **frontend:** resolve high-severity esbuild/vite audit advisories ([#739](https://github.com/zioalex/getinspiredbythebible/issues/739)) ([dd266d0](https://github.com/zioalex/getinspiredbythebible/commit/dd266d05f8d3ecede2095ddd8c506b2a026475c0))

### Documentation

* capture beta-tester feedback as six backlog stories (BITB-045…050) ([#734](https://github.com/zioalex/getinspiredbythebible/issues/734)) ([bc0d7af](https://github.com/zioalex/getinspiredbythebible/commit/bc0d7af946cece3efb2be6afaa086f4188c82828))

## [1.25.2](https://github.com/zioalex/getinspiredbythebible/compare/v1.25.1...v1.25.2) (2026-06-11)

### Bug Fixes

* **android:** chapter load timeout + hide placeholder verse text (BITB-041) ([#722](https://github.com/zioalex/getinspiredbythebible/issues/722)) ([64d06b2](https://github.com/zioalex/getinspiredbythebible/commit/64d06b2b5d943868382a027bd01fc750724ac360))
* clear 'message too long' handling + raise limit to 300 (web + Android + API) ([#725](https://github.com/zioalex/getinspiredbythebible/issues/725)) ([24c642a](https://github.com/zioalex/getinspiredbythebible/commit/24c642a52ca3cc0d8c04e2a4be18e9a591f1d554))

## [1.25.1](https://github.com/zioalex/getinspiredbythebible/compare/v1.25.0...v1.25.1) (2026-06-10)

### Bug Fixes

* **frontend:** surface chat stream stalls & empty responses instead of failing silently ([#721](https://github.com/zioalex/getinspiredbythebible/issues/721)) ([f4928a0](https://github.com/zioalex/getinspiredbythebible/commit/f4928a0bc21b32f0a7263dca05a2fa5adb756c11))
* make 10-interaction session limit durable on Android and backend ([#719](https://github.com/zioalex/getinspiredbythebible/issues/719)) ([1445088](https://github.com/zioalex/getinspiredbythebible/commit/1445088af47bad3697766348e1b707c0e2ab68ce))

## [1.25.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.24.0...v1.25.0) (2026-06-10)

### Features

* **android:** make user question text selectable for copy ([#713](https://github.com/zioalex/getinspiredbythebible/issues/713)) ([29dacdc](https://github.com/zioalex/getinspiredbythebible/commit/29dacdcdcf6ed353be6936e622fb665a04d1bbfa))
* verbatim scripture quoting and db load status diagnostic ([#714](https://github.com/zioalex/getinspiredbythebible/issues/714)) ([3b21f24](https://github.com/zioalex/getinspiredbythebible/commit/3b21f244887b36d0f7e463571a922209f4a45058))

### Bug Fixes

* **api:** strengthen verse placeholder guard + add repo-layer timeout tests (BITB-041) ([#712](https://github.com/zioalex/getinspiredbythebible/issues/712)) ([8056659](https://github.com/zioalex/getinspiredbythebible/commit/8056659e0c9e9231ef8d4f07819ace64483a9e60))

## [1.24.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.23.0...v1.24.0) (2026-06-09)

### Features

* **android:** submit sample question directly on tap ([#711](https://github.com/zioalex/getinspiredbythebible/issues/711)) ([5584a24](https://github.com/zioalex/getinspiredbythebible/commit/5584a2476153d37b8fcfd4a99a06e8b79d9dd7ec))

### Bug Fixes

* **api:** verse/chapter query timeout, error handling & monitoring (BITB-041) ([#700](https://github.com/zioalex/getinspiredbythebible/issues/700)) ([ff48248](https://github.com/zioalex/getinspiredbythebible/commit/ff482485982e79842bce8b3cd231d75e7fcc450b))
* **frontend:** patch 3 moderate dependabot advisories ([#699](https://github.com/zioalex/getinspiredbythebible/issues/699)) ([9e82239](https://github.com/zioalex/getinspiredbythebible/commit/9e8223921faf7061dcbd52dbb309bef1b2314633))
* **frontend:** show effective Bible translation in header selector (BITB-029) ([#709](https://github.com/zioalex/getinspiredbythebible/issues/709)) ([afc7d3a](https://github.com/zioalex/getinspiredbythebible/commit/afc7d3a6f677e6a5415a86a05c9b237df5b2f988))

## [1.23.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.22.2...v1.23.0) (2026-06-08)

### Features

* add weekly activity digest email and dashboard backlog story ([#701](https://github.com/zioalex/getinspiredbythebible/issues/701)) ([e43b5d9](https://github.com/zioalex/getinspiredbythebible/commit/e43b5d91e802f2bf9002de886d6c5667d0633b55))
* require contact email and make negative feedback actionable (BITB-043) ([#702](https://github.com/zioalex/getinspiredbythebible/issues/702)) ([19bec10](https://github.com/zioalex/getinspiredbythebible/commit/19bec1052817d09312558dc001f3eda41185541c))

### Documentation

* **search:** refine search-improvement stories + add turbovec evaluation ([#698](https://github.com/zioalex/getinspiredbythebible/issues/698)) ([a6137b4](https://github.com/zioalex/getinspiredbythebible/commit/a6137b4269d16259f250f90c41f97a6aba23fa0e))

## [1.22.2](https://github.com/zioalex/getinspiredbythebible/compare/v1.22.1...v1.22.2) (2026-06-07)

### Bug Fixes

* **feedback:** show comment field in one panel; pause countdown on focus ([#696](https://github.com/zioalex/getinspiredbythebible/issues/696)) ([f5cf36b](https://github.com/zioalex/getinspiredbythebible/commit/f5cf36b1f3e518408211ed62dbb546f67c04d2a5))

## [1.22.1](https://github.com/zioalex/getinspiredbythebible/compare/v1.22.0...v1.22.1) (2026-06-06)

### Bug Fixes

* **android:** float feedback rethink panel as a popover over the thumbs ([#692](https://github.com/zioalex/getinspiredbythebible/issues/692)) ([5319012](https://github.com/zioalex/getinspiredbythebible/commit/5319012bd72ae5fe05400ea471472c8a1a4250ae))
* **android:** localized book name in verse-detail header (BITB-040) ([#694](https://github.com/zioalex/getinspiredbythebible/issues/694)) ([c14be02](https://github.com/zioalex/getinspiredbythebible/commit/c14be02b2e7069dd95edfd98a3c38f4b8b9a3c60))
* **android:** preserve chat on device rotation (BITB-039) ([#689](https://github.com/zioalex/getinspiredbythebible/issues/689)) ([a3eb40d](https://github.com/zioalex/getinspiredbythebible/commit/a3eb40d5705299955a30b34082e9b088cc20e1fb))
* consistent, language-correct Bible version when opening a verse (web + Android) ([#691](https://github.com/zioalex/getinspiredbythebible/issues/691)) ([b4c182d](https://github.com/zioalex/getinspiredbythebible/commit/b4c182d53f5ad85d6bcd95b8941f7d04ef9bca19))

## [1.22.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.21.2...v1.22.0) (2026-06-06)

### Features

* **android:** inline feedback rethink window + maintainer notice (BITB-042) ([#685](https://github.com/zioalex/getinspiredbythebible/issues/685)) ([c2adb70](https://github.com/zioalex/getinspiredbythebible/commit/c2adb7067bfaee79b5520489cb88996b0966d225))

## [1.21.2](https://github.com/zioalex/getinspiredbythebible/compare/v1.21.1...v1.21.2) (2026-06-06)

### Bug Fixes

* **ci:** add Gemfile and use bundle exec to fix missing multi_json gem ([#688](https://github.com/zioalex/getinspiredbythebible/issues/688)) ([1a6694b](https://github.com/zioalex/getinspiredbythebible/commit/1a6694be17033ec590d02f062ca65ec81a2bd602))

### Documentation

* **backlog:** add BITB-042 feedback rethink delay + maintainer notice ([#686](https://github.com/zioalex/getinspiredbythebible/issues/686)) ([c677b56](https://github.com/zioalex/getinspiredbythebible/commit/c677b56f311527f91b323324fffe8b7a2d671f16))

## [1.21.1](https://github.com/zioalex/getinspiredbythebible/compare/v1.21.0...v1.21.1) (2026-06-05)

### Bug Fixes

* **api:** require verbatim scripture quotation, never paraphrase (BITB-038) ([#682](https://github.com/zioalex/getinspiredbythebible/issues/682)) ([005bcdb](https://github.com/zioalex/getinspiredbythebible/commit/005bcdbb5141630a0019c85416b43a85fbcd2b1c))

### Documentation

* **backlog:** add BITB-038 (verbatim scripture citation) and BITB-039 (preserve chat on rotation) ([#679](https://github.com/zioalex/getinspiredbythebible/issues/679)) ([f007115](https://github.com/zioalex/getinspiredbythebible/commit/f007115ec29a138f0f7f4cd08853db90d1daa4b7))
* **backlog:** close out mobile verse FAB reposition — verified, no change needed ([#681](https://github.com/zioalex/getinspiredbythebible/issues/681)) ([ba52a30](https://github.com/zioalex/getinspiredbythebible/commit/ba52a30dd5e50146ba5cbe614adb05cf1fab6c88))

## [1.21.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.20.0...v1.21.0) (2026-06-02)

### Features

* **frontend:** emphasize Android beta tester call-to-action ([#658](https://github.com/zioalex/getinspiredbythebible/issues/658)) ([c27f3e2](https://github.com/zioalex/getinspiredbythebible/commit/c27f3e242e478f462cb524b6b29f159cb15d535c))
* **seo:** server-render homepage hero to fix zero-word crawler output ([#657](https://github.com/zioalex/getinspiredbythebible/issues/657)) ([769d338](https://github.com/zioalex/getinspiredbythebible/commit/769d3382f1865866105f7791abdd6754d4de982c))

### Bug Fixes

* **android:** render changelog body as markdown so links are tappable ([#661](https://github.com/zioalex/getinspiredbythebible/issues/661)) ([7791fef](https://github.com/zioalex/getinspiredbythebible/commit/7791fef31d9b7381f029bd0d0f0d35cf272ef097))
* **ci:** split ANDROID_EXTRA_TRACKS on commas only ([#673](https://github.com/zioalex/getinspiredbythebible/issues/673)) ([7274655](https://github.com/zioalex/getinspiredbythebible/commit/7274655344f04763e57d2448a2943bbb4b80f9ff))
* **frontend:** restore emphasized tester CTA lost in homepage refactor ([#674](https://github.com/zioalex/getinspiredbythebible/issues/674)) ([357618a](https://github.com/zioalex/getinspiredbythebible/commit/357618a2cc899f568187cdba7ef25467da097584))

## [1.20.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.19.0...v1.20.0) (2026-05-31)

### Features

* add Android beta tester recruitment page and multi-track publish ([#656](https://github.com/zioalex/getinspiredbythebible/issues/656)) ([b7bbf9a](https://github.com/zioalex/getinspiredbythebible/commit/b7bbf9a7bd470809be5b252b87c2d4f9cefac434))

### Bug Fixes

* populate Cited tab on follow-up turns (resolve cited verses on backend) ([#654](https://github.com/zioalex/getinspiredbythebible/issues/654)) ([95c8502](https://github.com/zioalex/getinspiredbythebible/commit/95c8502fb4cf9aee4c573ac844f540d4b849f917))

## [1.19.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.18.3...v1.19.0) (2026-05-31)

### Features

* **android:** show cited verse text inline and harden verse links ([#651](https://github.com/zioalex/getinspiredbythebible/issues/651)) ([2864ec6](https://github.com/zioalex/getinspiredbythebible/commit/2864ec6f4a80a3c1238fac5092d808d4cd94df7b))
* **seo:** add favicon.ico, fix seo-live-check truncation, reprioritize BITB-037 ([#653](https://github.com/zioalex/getinspiredbythebible/issues/653)) ([c92304b](https://github.com/zioalex/getinspiredbythebible/commit/c92304be824e101252a9dcad6a9dc3cb0e69f55d))

### Bug Fixes

* **web:** always show cited verse cards in the References panel (BITB-037) ([#650](https://github.com/zioalex/getinspiredbythebible/issues/650)) ([47b7cd7](https://github.com/zioalex/getinspiredbythebible/commit/47b7cd7cfab20e6bb47380d171763db0ec48f90e))

## [1.18.3](https://github.com/zioalex/getinspiredbythebible/compare/v1.18.2...v1.18.3) (2026-05-30)

### Bug Fixes

* **android:** resolve localized verse taps and stop quote truncation ([#648](https://github.com/zioalex/getinspiredbythebible/issues/648)) ([c8dc53b](https://github.com/zioalex/getinspiredbythebible/commit/c8dc53b1142872d4223c5583d216785579e74a63))

## [1.18.2](https://github.com/zioalex/getinspiredbythebible/compare/v1.18.1...v1.18.2) (2026-05-30)

### Bug Fixes

* validate book names and handle linked verse references in chat ([#647](https://github.com/zioalex/getinspiredbythebible/issues/647)) ([281d9ef](https://github.com/zioalex/getinspiredbythebible/commit/281d9ef174e2bed98409d0bfb60095f67ea7eb9d))
* **web:** show every verse of a cited range in the references panel ([#645](https://github.com/zioalex/getinspiredbythebible/issues/645)) ([de4bf5f](https://github.com/zioalex/getinspiredbythebible/commit/de4bf5f8627e41deda79a81144ccf0dcbafc329a))

## [1.18.1](https://github.com/zioalex/getinspiredbythebible/compare/v1.18.0...v1.18.1) (2026-05-30)

### Documentation

* **backlog:** add BITB-037 SEO follow-ups story ([#642](https://github.com/zioalex/getinspiredbythebible/issues/642)) ([6d7567b](https://github.com/zioalex/getinspiredbythebible/commit/6d7567bcee9eab8a15cfb659606df6042301528d))
* **backlog:** add BITB-037 test-coverage follow-up for amber quote chip ([#643](https://github.com/zioalex/getinspiredbythebible/issues/643)) ([b3db07a](https://github.com/zioalex/getinspiredbythebible/commit/b3db07a2bf11fd636e7a2634b70db4e454807480))

## [1.18.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.17.0...v1.18.0) (2026-05-29)

### Features

* **android:** inline amber quote chip for quoted scripture (BITB-036) ([#637](https://github.com/zioalex/getinspiredbythebible/issues/637)) ([77f4452](https://github.com/zioalex/getinspiredbythebible/commit/77f44520f2ec2f69ede9525fe3f4ce560b9ecb95))

### Bug Fixes

* **backend:** enforce consistent language responses across all prompts ([#640](https://github.com/zioalex/getinspiredbythebible/issues/640)) ([c07b1a8](https://github.com/zioalex/getinspiredbythebible/commit/c07b1a8324ee9699859680b9a6cdf901a71c548f))

## [1.17.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.16.0...v1.17.0) (2026-05-29)

### Features

* **seo:** add SEO audit scripts, metadata improvements, and agent/skill definitions ([#636](https://github.com/zioalex/getinspiredbythebible/issues/636)) ([c4fdbcf](https://github.com/zioalex/getinspiredbythebible/commit/c4fdbcfdcd47a80b6e63f92491767c94b467f1d5))
* **web:** language-mismatch switch suggestion banner (Slice 2) ([#635](https://github.com/zioalex/getinspiredbythebible/issues/635)) ([d3b2fe3](https://github.com/zioalex/getinspiredbythebible/commit/d3b2fe3701f605325e96b0eecb70c3b96e4833b5))

## [1.16.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.15.0...v1.16.0) (2026-05-27)

### Features

* **backend:** emit language_suggestion in chat API (language-mismatch Slice 1) ([#634](https://github.com/zioalex/getinspiredbythebible/issues/634)) ([2720ffa](https://github.com/zioalex/getinspiredbythebible/commit/2720ffa509244967f3e229da203879e95a68a6bb))

### Documentation

* plan for language-mismatch switch-suggestion (Web + Android) ([#630](https://github.com/zioalex/getinspiredbythebible/issues/630)) ([8876472](https://github.com/zioalex/getinspiredbythebible/commit/88764722ab8b9d681bd0e00b7e1385d9218d5f48))

## [1.15.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.14.0...v1.15.0) (2026-05-26)

### Features

* **android:** style verse quote blockquotes with amber bar and background ([#629](https://github.com/zioalex/getinspiredbythebible/issues/629)) ([40b95ec](https://github.com/zioalex/getinspiredbythebible/commit/40b95ec565c280249288220df2db7f277320a90e))

## [1.14.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.13.0...v1.14.0) (2026-05-25)

### Features

* **android:** add New Chat top-bar shortcut and resume navigation tests (BITB-027) ([#617](https://github.com/zioalex/getinspiredbythebible/issues/617)) ([c3e36f2](https://github.com/zioalex/getinspiredbythebible/commit/c3e36f26d372588eaab4cca12cb2c2e13b95b8e9))
* **android:** add verse quote highlighting for scripture passages ([#619](https://github.com/zioalex/getinspiredbythebible/issues/619)) ([c2a52e6](https://github.com/zioalex/getinspiredbythebible/commit/c2a52e6ff119b7c741c1eab1b19440490a4a168a))

## [1.13.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.12.0...v1.13.0) (2026-05-24)

### Features

* **android:** make tag publish track configurable and add production promotion ([#613](https://github.com/zioalex/getinspiredbythebible/issues/613)) ([26eff02](https://github.com/zioalex/getinspiredbythebible/commit/26eff02d6cc47700c8ca4165c6851c8eb4b84b4e))
* **contact-form:** add required fields for bug reports with structured layout ([#616](https://github.com/zioalex/getinspiredbythebible/issues/616)) ([3f47edc](https://github.com/zioalex/getinspiredbythebible/commit/3f47edc63bb1c128560da62aefdc60ad47166018))

## [1.12.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.11.0...v1.12.0) (2026-05-24)

### Features

* **config:** add android-gemini agent backed by Qwen3 Coder via OpenRouter (BITB-023) ([#609](https://github.com/zioalex/getinspiredbythebible/issues/609)) ([9eccefe](https://github.com/zioalex/getinspiredbythebible/commit/9eccefe67c9fbf3fcb64e82e91c1781400ffd9fb))
* **contact-form:** add contextual message placeholder for bug reports ([#611](https://github.com/zioalex/getinspiredbythebible/issues/611)) ([156b574](https://github.com/zioalex/getinspiredbythebible/commit/156b5740c31fafb0475c2b9efef89db09fd776f6))

### Bug Fixes

* **ci:** disable header-max-length to allow Dependabot long PR titles ([#601](https://github.com/zioalex/getinspiredbythebible/issues/601)) ([8b6329f](https://github.com/zioalex/getinspiredbythebible/commit/8b6329fa13ceabc9d54a43e1e52ad7b92320940f))
* **frontend:** prevent horizontal overflow on narrow mobile viewports ([#607](https://github.com/zioalex/getinspiredbythebible/issues/607)) ([fe8bc90](https://github.com/zioalex/getinspiredbythebible/commit/fe8bc9000593daab30c1b17d67dd585dc1d897f1))
* **ops:** route contact form and diagnostic emails to <support@voxquieta.org> ([#603](https://github.com/zioalex/getinspiredbythebible/issues/603)) ([f6bd92e](https://github.com/zioalex/getinspiredbythebible/commit/f6bd92e47c5fc070b736e1c19dfa6b7c778881cd))

## [1.11.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.10.0...v1.11.0) (2026-05-22)

### Features

* **api:** guide assistant to Bible version selector when asked (BITB-029) ([#605](https://github.com/zioalex/getinspiredbythebible/issues/605)) ([2929249](https://github.com/zioalex/getinspiredbythebible/commit/29292498d8bd5ca514c257f442283fdd7fe56e1a))

## [1.10.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.9.0...v1.10.0) (2026-05-20)

### Features

* **ops:** blocked-sample exporter + pg_cron TTL purge ([#597](https://github.com/zioalex/getinspiredbythebible/issues/597)) ([c820a22](https://github.com/zioalex/getinspiredbythebible/commit/c820a2279dbb54f258bfaf13c51d985167a51983))

### Bug Fixes

* **android:** restore Compose test tier isolation (BITB-034) ([#598](https://github.com/zioalex/getinspiredbythebible/issues/598)) ([c87e4c1](https://github.com/zioalex/getinspiredbythebible/commit/c87e4c14578b85954dd0535f595ce5ec6a9383e8))
* **android:** show the raster PNG launcher icon on all API levels ([#599](https://github.com/zioalex/getinspiredbythebible/issues/599)) ([193a153](https://github.com/zioalex/getinspiredbythebible/commit/193a1537ae159d53dfa3558730412a8ce2c8d60f))

## [1.9.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.8.0...v1.9.0) (2026-05-19)

### Features

* **android:** add Robolectric/Compose UI test tier (BITB-034) ([#591](https://github.com/zioalex/getinspiredbythebible/issues/591)) ([7fd0908](https://github.com/zioalex/getinspiredbythebible/commit/7fd090874ec399a8160444f5734a14d95f9e5c1b))
* **safety:** privacy-friendly capture of blocked messages for tuning ([#594](https://github.com/zioalex/getinspiredbythebible/issues/594)) ([eb9ae21](https://github.com/zioalex/getinspiredbythebible/commit/eb9ae21cff60496afcf12c8ce0275dd6bcfce107))
* **safety:** warm notification when defenses block a message ([#593](https://github.com/zioalex/getinspiredbythebible/issues/593)) ([5c344d8](https://github.com/zioalex/getinspiredbythebible/commit/5c344d8ca4cd8a11762f1f319faa47053b0552b5))

### Bug Fixes

* **android:** fix analytics over-counting and locale-revert-to-English bugs ([#590](https://github.com/zioalex/getinspiredbythebible/issues/590)) ([d3960fa](https://github.com/zioalex/getinspiredbythebible/commit/d3960fab4a1309394700b3f468afffc9b37b76b7))
* **api:** harden external API dependency paths after 2026-05-15 incident ([#592](https://github.com/zioalex/getinspiredbythebible/issues/592)) ([7d7bf73](https://github.com/zioalex/getinspiredbythebible/commit/7d7bf73cf76672d586bcf1c65198048c6e3ea9bd))
* **chat:** auto-detect message language instead of forcing UI locale ([#585](https://github.com/zioalex/getinspiredbythebible/issues/585)) ([f13ce81](https://github.com/zioalex/getinspiredbythebible/commit/f13ce81eeb25bc7f101409213f2307cb8f504f49))

## [1.8.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.7.0...v1.8.0) (2026-05-17)

### Features

* **android:** add warm radial gradient to icon outer space ([#582](https://github.com/zioalex/getinspiredbythebible/issues/582)) ([ed49c51](https://github.com/zioalex/getinspiredbythebible/commit/ed49c513aa1def9dfdfc199ac1315b416549150a))

## [1.7.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.6.6...v1.7.0) (2026-05-17)

### Features

* **android:** add closed testing workflow for Play Store releases ([#581](https://github.com/zioalex/getinspiredbythebible/issues/581)) ([2c23c88](https://github.com/zioalex/getinspiredbythebible/commit/2c23c887fbbbd88513010a98e285b79ccae63b83))

## [1.6.6](https://github.com/zioalex/getinspiredbythebible/compare/v1.6.5...v1.6.6) (2026-05-17)

### Documentation

* **agents:** clarify feat vs chore commit type choice ([#579](https://github.com/zioalex/getinspiredbythebible/issues/579)) ([37560d7](https://github.com/zioalex/getinspiredbythebible/commit/37560d741a201295e7ff52ab552c13141d870b57))

## [1.6.5](https://github.com/zioalex/getinspiredbythebible/compare/v1.6.4...v1.6.5) (2026-05-17)

### Bug Fixes

* **frontend:** pass UI locale to chat API so AI responds in selected language ([#577](https://github.com/zioalex/getinspiredbythebible/issues/577)) ([d959a14](https://github.com/zioalex/getinspiredbythebible/commit/d959a142ba62ab6a545420445ae24523ce54bf59))

## [1.6.4](https://github.com/zioalex/getinspiredbythebible/compare/v1.6.3...v1.6.4) (2026-05-16)

### Bug Fixes

* **android-publish:** default tag publishes to internal + validate_only pre-flight ([#574](https://github.com/zioalex/getinspiredbythebible/issues/574)) ([ff92366](https://github.com/zioalex/getinspiredbythebible/commit/ff923665813a89e19a5ae14ac1d1236a6f9e4a36))

## [1.6.3](https://github.com/zioalex/getinspiredbythebible/compare/v1.6.2...v1.6.3) (2026-05-16)

### Bug Fixes

* **android:** correct app branding with golden bible icon and rays ([#569](https://github.com/zioalex/getinspiredbythebible/issues/569)) ([#572](https://github.com/zioalex/getinspiredbythebible/issues/572)) ([9e28516](https://github.com/zioalex/getinspiredbythebible/commit/9e28516c5c22052267a9e498d62d568cae5ef4ce))
* **ci:** filter Android CI runs by .path, not .name ([#570](https://github.com/zioalex/getinspiredbythebible/issues/570)) ([909abb3](https://github.com/zioalex/getinspiredbythebible/commit/909abb3e4ba73198d2736b3cff6a2af293733d4b))

### Documentation

* **agents:** require conventional-commits format on PR titles ([#568](https://github.com/zioalex/getinspiredbythebible/issues/568)) ([#573](https://github.com/zioalex/getinspiredbythebible/issues/573)) ([7a01368](https://github.com/zioalex/getinspiredbythebible/commit/7a013685da40e5dbad6eb72e02a34aaf5223f411))

## [1.6.2](https://github.com/zioalex/getinspiredbythebible/compare/v1.6.1...v1.6.2) (2026-05-16)

### Bug Fixes

* **android:** wrap message persistence in NonCancellable context ([#565](https://github.com/zioalex/getinspiredbythebible/issues/565)) ([#567](https://github.com/zioalex/getinspiredbythebible/issues/567)) ([8214925](https://github.com/zioalex/getinspiredbythebible/commit/82149256521c94cdad20a8c682f29423aaac94e1))

### Documentation

* **agents:** add failure-forecaster subagent for 12-month risk audits ([#563](https://github.com/zioalex/getinspiredbythebible/issues/563)) ([2a5c2c7](https://github.com/zioalex/getinspiredbythebible/commit/2a5c2c7694f04b9689c78f01823a3cffb456b732))

## [1.6.1](https://github.com/zioalex/getinspiredbythebible/compare/v1.6.0...v1.6.1) (2026-05-15)

### Bug Fixes

* **ci:** poll Android CI status in verify-ci-green to handle race ([#560](https://github.com/zioalex/getinspiredbythebible/issues/560)) ([99941cd](https://github.com/zioalex/getinspiredbythebible/commit/99941cde88905363ba440c74166301bcbcfa5d4a))

## [1.6.0](https://github.com/zioalex/getinspiredbythebible/compare/v1.5.1...v1.6.0) (2026-05-15)

### Features

* **chat:** BITB-035 interruptible streaming + multi-line input (web + Android) ([#557](https://github.com/zioalex/getinspiredbythebible/issues/557)) ([c4cb0a6](https://github.com/zioalex/getinspiredbythebible/commit/c4cb0a62d0fe3e417eca646d2dc49104ba59c94c))

### Bug Fixes

* **android:** allow partial text selection in assistant messages ([#559](https://github.com/zioalex/getinspiredbythebible/issues/559)) ([8edbb74](https://github.com/zioalex/getinspiredbythebible/commit/8edbb74cf686a02714c1bfab3d125417507a4d4f))
* **android:** show "Bible Version" on translation chip instead of "Auto" ([#555](https://github.com/zioalex/getinspiredbythebible/issues/555)) ([f2352c5](https://github.com/zioalex/getinspiredbythebible/commit/f2352c548f5b939f4f65c29f668878c406e3b855))

## [1.5.1](https://github.com/zioalex/getinspiredbythebible/compare/v1.5.0...v1.5.1) (2026-05-14)

### Bug Fixes

* **android-publish:** skip rollout param when release_status is draft ([#549](https://github.com/zioalex/getinspiredbythebible/issues/549)) ([57995b7](https://github.com/zioalex/getinspiredbythebible/commit/57995b7fc2ac95521629c1db12e844c2010a56bc))
* **android:** rename post-send dismiss button from Cancel to Done (BITB-033) ([#548](https://github.com/zioalex/getinspiredbythebible/issues/548)) ([56a88ad](https://github.com/zioalex/getinspiredbythebible/commit/56a88ad6d9142bfc522d8f88abfd6ef4ff75489e))
* **ui:** compact Bible version selector and default verses to Cited ([#551](https://github.com/zioalex/getinspiredbythebible/issues/551)) ([45b35b3](https://github.com/zioalex/getinspiredbythebible/commit/45b35b34604e44e0204645577926d65656663b94))

## [1.5.0](https://github.com/zioalex/getinspiredbythebible/compare/v0.9.0...v1.5.0) (2026-05-13)

### Features

* **android:** in-app What's New / Changelog screen (BITB-031) ([#546](https://github.com/zioalex/getinspiredbythebible/issues/546)) ([a0d7f51](https://github.com/zioalex/getinspiredbythebible/commit/a0d7f51350acaf4ed8c74088f3fa43e1569f16c5))

### Bug Fixes

* **android:** re-throw CancellationException in all coroutine catch blocks ([#543](https://github.com/zioalex/getinspiredbythebible/issues/543)) ([7342401](https://github.com/zioalex/getinspiredbythebible/commit/7342401ef54a0c0d702d62f6305e58d09a8f4626))

## [0.9.0](https://github.com/zioalex/getinspiredbythebible/compare/v0.8.0...v0.9.0) (2026-05-12)

### Features

* **android:** redesign Settings UX (BITB-026) ([#539](https://github.com/zioalex/getinspiredbythebible/issues/539)) ([6235c48](https://github.com/zioalex/getinspiredbythebible/commit/6235c48a14aa1880ecbd8978095a91c644d34069))

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
