# Changelog

All notable changes to this project will be documented in this file.

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
