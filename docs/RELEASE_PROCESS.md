# Release Process

This document explains how versioning, release tagging, and Android publishing
work in Vox Quieta.

## Overview

Releases are fully automated using [release-please](https://github.com/googleapis/release-please).
The flow is:

```
Conventional Commits on main
        │
        ▼
Android CI runs on every main commit  (verdict stored as a check-run)
        │
        ▼
release-please opens/updates a "Release PR"  (fires on push: main)
        │
        ▼  (maintainer merges the Release PR)
release-please pushes a semver tag  (e.g. v0.2.0) at the merge commit
        │
        ▼
android-publish.yml fires on push: tags: v*.*.*
        │
        ▼  verify-release-gate:
        │    • assert .release-please-manifest.json matches the tag version
        │    • poll Android CI for the *parent* commit (release-please diffs
        │      are CHANGELOG + manifest only; the parent is the real shipping
        │      code and already has a green Android CI verdict)
        ▼
Uploaded to the Google Play track named by the
ANDROID_AUTO_TRACK repo variable (default: internal)
```

The track a tag publishes to is a **single dial** — the `ANDROID_AUTO_TRACK`
Actions variable. See [The publishing ladder](#the-publishing-ladder) below.

No manual `git tag` is required.
**Do NOT push `vX.Y.Z` tags by hand** — release-please manages them, and the
publish workflow's `verify-release-gate` job will refuse to publish any tag
whose target commit does not have a successful `Android CI` run.

### CI gating (defence in depth)

Three layers ensure that a red Android CI cannot produce a release:

1. **Android CI runs on every push to `main`** (no `paths:` filter on the
   `push` trigger), so every main commit has a definitive verdict.
2. **`android-publish.yml`'s `verify-release-gate`** is the authoritative
   pre-publish check. For release-please merge commits (whose own diff is
   mechanical: CHANGELOG + manifest), it polls Android CI on the **parent**
   commit — the actual shipping code, which by construction has already
   passed CI by the time the Release PR is merged. For any other tag
   (e.g. manually pushed) it polls Android CI on the tag's own commit.
3. **Version sanity**: the same job asserts that `.release-please-manifest.json`
   matches the pushed tag (`v1.6.1` ↔ `"."`: `"1.6.1"`), catching any drift
   between the merged Release PR's manifest and the tag.

> Why not gate `release-please` itself on `Android CI` via `workflow_run`?
> We used to, but it added ~11 min of latency between Release-PR merge and
> publish (release-please waited for Android CI on the merge commit before
> it could fire and create the tag). The merge commit's diff is mechanical,
> so checking the parent's CI at publish time gives the same safety
> property with no wait.
>
> Recommended follow-up (repo settings, not in code): enable branch
> protection on `main` requiring the `Android CI` status check before merge,
> so a red PR cannot land in the first place.

---

## How release-please works

release-please scans commits on `main` that follow
[Conventional Commits](https://www.conventionalcommits.org/) and maintains an
auto-updating "Release PR". Each time a qualifying commit lands on `main`,
release-please:

1. Updates the Release PR's version bump (patch / minor / major) and
   `CHANGELOG.md` based on commit types.
2. When a maintainer **merges the Release PR**, release-please creates a
   semver git tag and a GitHub Release.

### Commit types and version bumps

| Commit type | Version bump | Appears in changelog |
| ----------- | ------------ | -------------------- |
| `feat`      | minor        | ✅ Yes |
| `fix`       | patch        | ✅ Yes |
| `perf`      | patch        | ✅ Yes |
| `revert`    | patch        | ✅ Yes |
| `docs`      | patch        | ✅ Yes |
| `chore`     | –            | hidden |
| `build`     | –            | hidden |
| `ci`        | –            | hidden |
| `refactor`  | –            | hidden |
| `test`      | –            | hidden |
| `BREAKING CHANGE` footer or `!` suffix | **major** | ✅ Yes |

### Configuration files

| File | Purpose |
| ---- | ------- |
| `release-please-config.json` | Release type, tag format, changelog sections |
| `.release-please-manifest.json` | Current version per package (updated by release-please) |

---

## PAT requirement — `RELEASE_PLEASE_TOKEN`

> **Action required for the repo owner before the first release.**

Tags created by the built-in `GITHUB_TOKEN` do **not** trigger downstream
`on: push: tags` workflows (GitHub security restriction). To allow the
release-please tag to automatically fire `android-publish.yml`, you must
create a **Personal Access Token (PAT)** with the following scopes and add it
as a repository secret:

### Creating the PAT

1. Go to **GitHub → Settings → Developer settings → Personal access tokens →
   Fine-grained tokens**.
2. Create a token scoped to `zioalex/getinspiredbythebible` with:
   - **Contents:** Read and write (to push tags and update the manifest)
   - **Pull requests:** Read and write (to open/update the Release PR)
   - **Issues:** Read and write (to add `autorelease: pending/tagged` labels —
     GitHub routes PR label writes through the Issues API even though no
     issue tracker is used)
   - **Workflows:** Read and write (so the tag push can trigger workflow runs)
3. Copy the token value.

### Adding the secret

1. Go to **Repository → Settings → Secrets and variables → Actions**.
2. Click **New repository secret**.
3. Name: `RELEASE_PLEASE_TOKEN`
4. Value: paste the PAT.

Once the secret is in place, every merge of a Release PR will:

- Push a `vX.Y.Z` tag using the PAT
- Trigger `android-publish.yml` → upload to the Play Store track named by the
  `ANDROID_AUTO_TRACK` variable (see [The publishing ladder](#the-publishing-ladder))

> Note: `.github/workflows/release-please.yml` currently sets
> `skip-labeling: true` to avoid intermittent GitHub API denials on
> `issues/labels` endpoints, even when PAT permissions look correct.

---

## Reading the auto-generated Release PR

release-please keeps a single open PR titled
`chore(main): release X.Y.Z`. It shows:

- The proposed new version
- A rendered CHANGELOG preview
- The diff to `CHANGELOG.md` and `.release-please-manifest.json`

**To release:** review the PR and merge it. Do not push the tag yourself.

---

## Android publish chain

### Automatic (tag-triggered)

On merge of the Release PR:

1. release-please pushes tag `vX.Y.Z`
2. `android-publish.yml` triggers on `push: tags: v[0-9]+.[0-9]+.[0-9]+`
3. The workflow builds a signed AAB and uploads it to the track named by the
   `ANDROID_AUTO_TRACK` repo variable (see below)

### The publishing ladder

A Google Play app climbs a ladder of tracks before reaching all users:

```
internal  →  closed testing (e.g. "extend testing")  →  beta (open)  →  production
```

Rather than hardcode which track tags publish to, the pipeline reads a single
**Actions repository variable**, `ANDROID_AUTO_TRACK`. The tag-triggered
publish routes to the matching Fastlane lane:

| `ANDROID_AUTO_TRACK` value | Goes to |
| -------------------------- | ------- |
| _unset / empty_            | `internal` (safe default) |
| `internal`                 | Internal testing |
| `alpha`                    | Closed testing (built-in alpha track) |
| `extend testing` (or any other custom trackId) | That closed testing track |
| `beta`                     | Open testing |
| `production`               | Production |

**To advance the app up the ladder, change the variable — no code change:**

1. Go to **Repo → Settings → Secrets and variables → Actions → Variables**.
2. Edit (or create) `ANDROID_AUTO_TRACK` and set it to the target trackId.
3. The next merged Release PR publishes straight to that track.

> **Current value:** `extend testing` — the app is in closed testing with the
> extended group. Every release now reaches those testers automatically.
>
> **Confirming a custom trackId:** any value that is not
> `internal`/`alpha`/`beta`/`production` is treated as a closed-testing track
> and passed through verbatim. Make sure it matches the Play Console trackId
> exactly. The **List available Play Store tracks** step in
> `android-closed-testing.yml` prints the exact trackIds for the app.

### Reaching production

Google requires a (new) developer account to run a **closed test with at least
12 testers for at least 14 continuous days** before the production track
unlocks. Until that gate is satisfied, keep `ANDROID_AUTO_TRACK` on the closed
track and let testers accumulate days.

Once eligible, **promote the exact build that testers approved** — do not ship
a freshly-built AAB to production. Use the **Android Promote** workflow
(`android-promote.yml`), which runs the Fastfile `promote` lane and moves an
existing `versionCode` between tracks without rebuilding:

1. Find the `versionCode` of the build to promote (Play Console → the release
   on the closed track, or the AAB artifact name / build log of the run that
   published it).
2. Go to **Repository → Actions → Android Promote → Run workflow**.
3. Fill in `promote_version_code`, `promote_from` (default `extend testing`),
   `promote_to` (default `production`), `release_status` (default `draft`), and
   `rollout` (phased fraction, applied only when status is `completed`).
4. With `draft`, review the staged release in Play Console, then set the
   rollout live there (or re-run with `release_status: completed` and a
   `rollout` fraction for a phased launch).

### Publishing to several tracks at once (`ANDROID_EXTRA_TRACKS`)

A second Actions variable, `ANDROID_EXTRA_TRACKS`, lets one tag-triggered
release reach **more than one track** without rebuilding. After the primary
upload to `ANDROID_AUTO_TRACK`, the workflow promotes the *same* `versionCode`
(bit-for-bit, via the Fastfile `promote` lane) to every track listed here.

- **Format:** comma-separated trackIds. Split is on **commas only**, because
  trackIds may contain spaces (e.g. `closed-testing google-group`). Whitespace
  around each entry is trimmed; blanks and the primary track are skipped.
- **Direction matters:** promotion goes *up* the ladder. Promote
  `internal → closed → beta → production`, not downward. Listing a lower track
  than the primary will be rejected by Google Play.
- **Empty/unset:** no-op (only the primary track is published).

> **Current values:** `ANDROID_AUTO_TRACK = extend testing`,
> `ANDROID_EXTRA_TRACKS = closed-testing google-group`. Every release goes to
> both closed-testing tracks at full rollout.

### Why testers may not see an update yet (review delays & the internal fast path)

**A successful publish does not mean the build is downloadable.** A green
`android-publish.yml` run only proves Google *accepted* the upload. Releases to
**closed testing, open testing, and production still go through Google review**,
and that review is an independent gate the upload log cannot see. Through late
2025–2026 these reviews have frequently backed up for **days to weeks**, during
which testers keep the previously-approved build. If you publish a new release
every day, each one re-enters the queue, so the closed tracks can sit
perpetually "In review" while never going live.

Where to confirm: **Play Console → Testing → <your track> → Releases**. If the
latest release shows **"In review" / "Pending publication"** (not "Available to
testers"), the pipeline has done its job — you are waiting on Google. Check
**Play Console → Policy status** and the developer-account email for any
action-required message; a review stuck beyond ~7 days with no message usually
warrants contacting Play support from the Console.

**The internal testing track is the fast lane.** Internal testing releases are
typically available to testers **within minutes**, because they get the
lightest/fastest review — unlike the closed/open/production tracks. If the goal
is to actually *receive* each build promptly (e.g. to dogfood your own
releases), publish to `internal` and join it as a tester:

1. Set `ANDROID_AUTO_TRACK = internal` (primary upload goes straight to
   internal = fast) and, if you still want the formal closed tracks, set
   `ANDROID_EXTRA_TRACKS = extend testing, closed-testing google-group` (the
   same build is promoted *up* to them, where it flows through review in the
   background).
2. **Play Console → Testing → Internal testing → Testers:** add your Google
   account's email, open the internal opt-in URL, and click *Become a tester*.
3. On the device, ensure the Play Store is signed in with that same account,
   then refresh ("Manage apps & device → Updates available").

> Because the upload defaults to `internal` when `ANDROID_AUTO_TRACK` is
> unset, simply **clearing** the variable also restores internal as the primary
> track.

### Checking what actually landed on each track

`android-publish.yml` ends with a read-only **"Report Play Store track status"**
step. It opens a throwaway Play Console edit (committing nothing) and prints,
for every track, each release's `versionCodes`, target `status`, and rollout
`userFraction`. Use it to confirm *which* build is on each track and that the
rollout is full.

> **Caveat:** the `status` it prints is the *target* state you set
> (`completed` / `draft` / etc.) and the rollout fraction — **not** Google's
> review state. The Play Developer API exposes no "In review" field, so this
> step cannot detect a review hold. For review status, the **Play Console UI is
> the source of truth** (see the section above).

### Manual one-off publish (workflow_dispatch)

`android-publish.yml` also has a `workflow_dispatch` trigger with a `track`
input (`validate` | `internal` | `alpha` | `beta` | `production`) for ad-hoc
builds. To publish a fresh build to a specific track:

1. Go to **Repository → Actions → Android Publish → Run workflow**.
2. Select the desired track and click **Run workflow**.

> **Note:** The `workflow_dispatch` path does not bump the version — it uses the
> `versionName` and `versionCode` from `android/app/build.gradle.kts`. For a
> manual dispatch to have the correct version, ensure `build.gradle.kts` matches
> the version you intend to publish, or use the tag-triggered path instead.
>
> For production, prefer **Android Promote** over a fresh `production` dispatch
> so the artifact users get is the one that was actually tested.

---

## Reviewing a Release PR before merging

The Release PR is the manual review surface — you are not expected to merge
it blindly.

> **Only one branch is created by release-please.** It is named
> `release-please--branches--main` (no suffix). It modifies exactly two
> files: `CHANGELOG.md` and `.release-please-manifest.json`. There is no
> `--release-notes` branch and no `release-notes.md` file in this repo —
> if you see either, they are stale and should be deleted, not opened as a
> PR. To read formatted notes for a single release, look at the GitHub
> Release body created when the Release PR merges (or the corresponding
> `## [vX.Y.Z]` section of `CHANGELOG.md`).

1. A push to `main` triggers `.github/workflows/release-please.yml`. It
   opens or updates a single PR on branch `release-please--branches--main`
   (titled like `chore(main): release X.Y.Z`) that touches
   `CHANGELOG.md` and `.release-please-manifest.json`.
2. The follow-up `Lint-fix Release PR` job in the same workflow runs
   pre-commit (`SKIP=hadolint-docker`) on the PR's changed files and
   pushes back any auto-fixes (trailing whitespace, EOF, markdownlint
   `--fix`) as a `chore: lint-fix release-please output` commit. Wait for
   `Pre-Commit Validation` and `Lint Commit Messages` to go green on the
   PR before merging.
3. **To curate the notes**: check the PR branch out locally, edit
   `CHANGELOG.md`, commit with a `chore:` or `docs:` prefix (so commitlint
   passes), and push. Force-push is not needed because release-please
   merges into the existing branch.
4. Merge the PR. release-please then creates the `vX.Y.Z` tag and the
   GitHub Release on the next workflow run, which fires
   `android-publish.yml` (see Overview above).

> ⚠️ **Do not retarget the Release PR's base** to a side branch. release-please
> only creates tags when its PR merges into the configured release branch
> (`main`). A staging branch in between silently breaks tagging.

---

## Seeded version

The manifest was seeded at **`0.1.0`** because no git tags existed in the
repository at the time release-please was introduced. The first Release PR will
propose `0.2.0` (if a `feat` commit lands) or `0.1.1` (if only `fix`/`chore`
commits land after the seed).

---

## Troubleshooting

When release-please misbehaves, the symptom usually maps to a specific
PAT scope, token configuration, or branch issue. Use this table to
diagnose quickly.

### Common errors

| Symptom in workflow logs | Likely cause | Fix |
| ------------------------ | ------------ | --- |
| `Resource not accessible by personal access token` pointing at `pulls#create-a-pull-request` (the branch ref is created, but PR creation fails) | PAT is missing **Pull requests: Read and write**, has expired, or the repository is not in the PAT's selected-repos list | Regenerate / edit the fine-grained PAT (see [PAT requirement](#pat-requirement--release_please_token)), grant `Pull requests: Read and write`, ensure `zioalex/getinspiredbythebible` is selected, then update the `RELEASE_PLEASE_TOKEN` secret |
| `Resource not accessible by personal access token` pointing at `issues/labels` | PAT is missing **Issues: Read and write** | Either grant `Issues: Read and write` on the PAT, or rely on the existing `skip-labeling: true` workaround in `.github/workflows/release-please.yml` (lines 41-43) |
| Release PR merges, tag `vX.Y.Z` is pushed, but `android-publish.yml` does not trigger | The tag was pushed by `GITHUB_TOKEN` (which cannot trigger downstream workflows) instead of the PAT, **or** the PAT is missing **Workflows: Read and write** | Confirm the `release-please-action` step in `.github/workflows/release-please.yml` uses `token: ${{ secrets.RELEASE_PLEASE_TOKEN }}`, and that the PAT has `Workflows: Read and write` |
| Release PR merges but no tag is created | Release PR base was retargeted off `main` to a side branch | Re-open the PR with base `main`. release-please only tags when its PR merges into the configured release branch |
| Workflow logs show `Bad credentials` or `401` | PAT expired or was revoked | Regenerate the PAT and update the `RELEASE_PLEASE_TOKEN` secret |
| Two Release PRs appear, or a stale `release-please--branches--main--release-notes` branch exists | Leftover from older release-please configuration | Delete the stale branch. The current config produces a single PR on branch `release-please--branches--main` (see [Reviewing a Release PR](#reviewing-a-release-pr-before-merging)) |
| `Lint Commit Messages` fails on the Release PR | A manually-edited commit on the Release PR branch does not follow Conventional Commits | Amend with a `chore:` or `docs:` prefix; see `commitlint.config.cjs` for the allowed types |
| `android-publish.yml` is green and the **Report Play Store track status** step shows the build at `completed` / 100%, but testers don't see the update | The release is held in **Google review** on a closed/open/production track (the API status is the *target* state, not the review state). Common 2025–2026 backlog. | Confirm in **Play Console → Testing → <track> → Releases** ("In review" vs "Available to testers"); check **Policy status** + account email. For prompt delivery, publish to the **internal** track instead — see [Why testers may not see an update yet](#why-testers-may-not-see-an-update-yet-review-delays--the-internal-fast-path) |
| Tester is in the closed-testing Google group but still sees the old build | Group membership alone is not enough, or the device's Play Store account differs | Open the track's **opt-in URL** and click *Become a tester* with the device's Google account; confirm the Play Store app is signed in with that account; refresh "Updates available" or clear Play Store storage |

### Quick diagnostic checklist

If the release-please workflow run is red, check in this order:

1. **Is `RELEASE_PLEASE_TOKEN` set?** Repo → Settings → Secrets and
   variables → Actions. Missing secret → workflow falls back to
   `GITHUB_TOKEN` and downstream tag-triggered jobs will not fire.
2. **Is the PAT expired?** Fine-grained PATs have a max 1-year lifetime;
   GitHub sends an email warning ~7 days before expiry.
3. **Does the PAT cover the repo?** For fine-grained tokens, the repo
   must be explicitly listed under "Repository access".
4. **Does the PAT have all four scopes?** Contents (write), Pull
   requests (write), Issues (write), Workflows (write). See
   [Creating the PAT](#creating-the-pat).
5. **Is the Release PR base `main`?** If somebody retargeted it,
   tagging will silently break.

---

## Future work (tracked separately)

- Web changelog page surfacing GitHub Releases
- "What's New" in-app modal tied to the release version
- Legal pages (privacy policy, terms of service) versioned with releases
