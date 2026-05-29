---
name: seo-audit
description: Run a repeatable SEO audit of the Vox Quieta frontend (Next.js App Router + next-intl) and the deployed voxquieta.org site. Use when the user asks to audit SEO, check meta tags / titles / descriptions, verify sitemap / robots / canonical / hreflang, find missing alt text, or check for broken links and 4XX pages. Produces a prioritized report separating real issues from boilerplate.
---

# SEO Audit (Vox Quieta)

Audit the site's discoverability and produce a prioritized, evidence-backed
report. The frontend is Next.js 16 App Router + `next-intl`, locale-prefixed
(`localePrefix: "always"`), 11 locales, deployed at `https://voxquieta.org`.
This skill is **read-only** — it inspects and reports; it never edits the site.

## Steps

1. **Static codebase scan (always).** Run:

   ```
   bash scripts/seo-static-check.sh
   ```

   It prints PASS/FAIL/WARN for metadataBase, Open Graph / Twitter, sitemap,
   robots, favicon, `title.template`, homepage title length, per-locale metadata
   coverage (all 11 `frontend/messages/*.json`), image alt-text exposure, and
   manual-review reminders (hreflang on sub-pages, client-rendered homepage).
   Exit code is non-zero if any FAIL — note which checks fail.

2. **Live check (if the domain is reachable).** Try:

   ```
   bash scripts/seo-live-check.sh
   ```

   It reports HTTP status for key routes (including an un-prefixed `/privacy` and
   a bogus path to confirm 404 behaviour), the rendered `<head>` meta of the
   homepage + a sub-page, robots.txt/sitemap.xml contents, and a server-rendered
   word-count gauge. **The Claude Code web sandbox usually blocks this**
   (`403 host_not_allowed`). If it fails, ask the user to run the script on a
   networked machine and paste the output, or to provide the "live-site data
   needed" list (see the audit plan / README of this skill).

3. **Manual judgement passes** (the scripts can't decide these):
   - **hreflang correctness** — `frontend/src/app/[locale]/layout.tsx`
     `alternates.languages` point to locale *roots* (`/en`, `/it`, …); inherited
     by sub-pages, so `/en/privacy` mislabels its alternates. Confirm.
   - **Crawlability** — `frontend/src/app/[locale]/page.tsx` is `"use client"`;
     `generateMetadata` still emits title/description server-side, but body text
     is client-rendered. Check how much indexable content the homepage exposes.
   - **Links** — internal links use `@/i18n/navigation` `Link` (locale-safe).
     Spot-check external links, esp. `https://disciplestoday.org`
     (`ChurchFinderModal.tsx`), for liveness.

4. **Write the report.** Use this structure:
   - A **verdict table** mapping each reported claim (broken links, 4XX, missing
     alt, missing descriptions, duplicate/missing meta, long/unoptimized titles)
     to *real here? yes / partly / no* with one-line evidence (`file:line`).
     Call out boilerplate that doesn't apply (this site has **no images**, so
     "missing alt text" usually doesn't apply).
   - **Findings** grouped: metadata infra, titles, crawl/index files, routing/4XX,
     links — each with `file:line` evidence.
   - **Prioritized roadmap** (P0/P1/P2), reusing the existing per-locale
     `generateMetadata` + `messages/*.json` pattern. Do not propose fixes outside
     SEO scope.

## Notes

- Keep findings grounded in `file:line` evidence or script/live output — no
  floating claims.
- For deeper or delegated runs, the `seo-auditor` subagent
  (`.claude/agents/seo-auditor.md`) contains the same checklist and can run
  autonomously inside a larger task.
- Reference doc with the full current-state findings:
  the SEO audit plan written under `~/.claude/plans/` (if present).
