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
release-please opens/updates a "Release PR"
        │
        ▼  (maintainer merges the Release PR)
release-please pushes a semver tag  (e.g. v0.2.0)
        │
        ▼
android-publish.yml fires on push: tags: v*.*.*
        │
        ▼
Internal track uploaded to Google Play
```

No manual `git tag` is required.
**Do NOT push `vX.Y.Z` tags by hand** — release-please manages them.

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
- Trigger `android-publish.yml` → upload to the **internal** Play Store track

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
3. The workflow builds a signed AAB and uploads it to the **internal** track on
   Google Play

### Manual promotion to beta / production

`android-publish.yml` also has a `workflow_dispatch` trigger with a `track`
input (`internal` | `beta` | `production`). To promote a build:

1. Go to **Repository → Actions → Android Publish**.
2. Click **Run workflow**.
3. Select the desired track and click **Run workflow**.

> **Note:** The `workflow_dispatch` path does not bump the version — it uses the
> `versionName` and `versionCode` from `android/app/build.gradle.kts`. For a
> manual dispatch to have the correct version, ensure `build.gradle.kts` matches
> the version you intend to publish, or use the tag-triggered path instead.

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

## Future work (tracked separately)

- Web changelog page surfacing GitHub Releases
- "What's New" in-app modal tied to the release version
- Legal pages (privacy policy, terms of service) versioned with releases
