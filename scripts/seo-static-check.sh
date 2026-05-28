#!/bin/bash
# SEO static scan for the Vox Quieta frontend (Next.js App Router + next-intl).
# Inspects the codebase only (no network) and reports a PASS/FAIL/WARN table.
# Exits non-zero if any FAIL is found, so it can gate CI.
#
# Usage: bash scripts/seo-static-check.sh
# Companion: scripts/seo-live-check.sh (checks the deployed site over HTTP).

set -uo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; BLUE='\033[0;34m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FE="$REPO_ROOT/frontend"
APP="$FE/src/app"
LAYOUT="$APP/[locale]/layout.tsx"
MSG="$FE/messages"

EXPECTED_LOCALES=(en it de es fr pt ar ru zh hi ko)

fails=0; warns=0
pass() { echo -e "  ${GREEN}PASS${NC}  $1"; }
fail() { echo -e "  ${RED}FAIL${NC}  $1"; fails=$((fails+1)); }
warn() { echo -e "  ${YELLOW}WARN${NC}  $1"; warns=$((warns+1)); }

echo -e "${BLUE}=== Vox Quieta SEO static scan ===${NC}"
echo "frontend: $FE"
echo ""

if [ ! -d "$APP" ]; then
  echo -e "${RED}Could not find $APP — run this from the repo.${NC}"; exit 2
fi

echo -e "${BLUE}-- Metadata infrastructure --${NC}"
grep -q "metadataBase" "$LAYOUT" 2>/dev/null \
  && pass "metadataBase set in [locale]/layout.tsx" \
  || fail "metadataBase missing — OG/canonical relative URLs won't resolve ([locale]/layout.tsx)"

grep -rq "openGraph" "$APP" 2>/dev/null \
  && pass "openGraph metadata present" \
  || fail "no Open Graph metadata (og:title/description/image) under src/app"

grep -rqE "twitter:|card:[[:space:]]*\"summary" "$APP" 2>/dev/null || grep -rq "twitter" "$APP" 2>/dev/null \
  && pass "twitter card metadata present" \
  || fail "no Twitter card metadata under src/app"

grep -rq "canonical" "$APP" 2>/dev/null \
  && pass "canonical alternates referenced" \
  || warn "no canonical URLs (alternates.canonical) found under src/app"

grep -rq "application/ld+json\|JsonLd\|schema.org" "$APP" 2>/dev/null \
  && pass "JSON-LD structured data present" \
  || warn "no JSON-LD structured data (WebSite/Organization) under src/app"

echo ""
echo -e "${BLUE}-- Crawl / index files --${NC}"
{ [ -f "$APP/sitemap.ts" ] || [ -f "$APP/sitemap.tsx" ] || [ -f "$FE/public/sitemap.xml" ]; } \
  && pass "sitemap present (app/sitemap.ts or public/sitemap.xml)" \
  || fail "no sitemap — create frontend/src/app/sitemap.ts"

{ [ -f "$APP/robots.ts" ] || [ -f "$FE/public/robots.txt" ]; } \
  && pass "robots present (app/robots.ts or public/robots.txt)" \
  || fail "no robots — create frontend/src/app/robots.ts"

if ls "$APP"/favicon.ico "$APP"/icon.* "$APP"/apple-icon.* "$FE"/public/favicon* "$FE"/public/*.ico >/dev/null 2>&1; then
  pass "favicon / app icon present"
else
  fail "no favicon/app icon (app/favicon.ico | app/icon.* | public/*.ico)"
fi

echo ""
echo -e "${BLUE}-- Titles --${NC}"
grep -q "template:" "$LAYOUT" 2>/dev/null \
  && pass "title.template present in [locale]/layout.tsx" \
  || fail "no title.template — sub-pages render without a brand suffix"

if command -v node >/dev/null 2>&1 && [ -f "$MSG/en.json" ]; then
  title_len=$(node -e 'try{const t=require(process.argv[1]).Metadata?.title||"";process.stdout.write(String(t.length))}catch(e){process.stdout.write("-1")}' "$MSG/en.json" 2>/dev/null)
  if [ "$title_len" = "-1" ]; then
    warn "could not read Metadata.title from messages/en.json"
  elif [ "$title_len" -ge 15 ]; then
    pass "homepage title length is $title_len chars (en.json)"
  else
    fail "homepage title is only $title_len chars (\"$(node -e 'process.stdout.write(require(process.argv[1]).Metadata?.title||"")' "$MSG/en.json" 2>/dev/null)\") — too short/generic"
  fi
else
  warn "node not available or messages/en.json missing — skipped title-length check"
fi

echo ""
echo -e "${BLUE}-- i18n metadata coverage (11 locales) --${NC}"
if command -v node >/dev/null 2>&1; then
  missing=""
  for loc in "${EXPECTED_LOCALES[@]}"; do
    f="$MSG/$loc.json"
    if [ ! -f "$f" ]; then missing="$missing $loc(file)"; continue; fi
    ok=$(node -e 'try{const m=require(process.argv[1]);process.stdout.write((m.Metadata&&m.Metadata.title&&m.Metadata.description)?"1":"0")}catch(e){process.stdout.write("0")}' "$f" 2>/dev/null)
    [ "$ok" = "1" ] || missing="$missing $loc"
  done
  if [ -z "$missing" ]; then
    pass "all 11 locales have Metadata.title + Metadata.description"
  else
    fail "locales missing Metadata.title/description:$missing"
  fi
else
  warn "node not available — skipped per-locale metadata check"
fi

echo ""
echo -e "${BLUE}-- Images / ALT text --${NC}"
img_tags=$(grep -rlE "<img[[:space:]>]|from \"next/image\"" "$FE/src" 2>/dev/null || true)
if [ -z "$img_tags" ]; then
  pass "no <img>/next/image usage (no alt-text exposure in JSX)"
else
  warn "image usage found — verify alt attributes in: $img_tags"
fi
empty_alt=$(grep -rlE '!\[\]\(' "$FE/public" 2>/dev/null || true)
if [ -z "$empty_alt" ]; then
  pass "no markdown images with empty alt in public/ content"
else
  fail "markdown images with empty alt (![]()) in: $empty_alt"
fi

echo ""
echo -e "${BLUE}-- Manual-review reminders (not auto-checkable) --${NC}"
warn "hreflang: layout alternates.languages point to locale roots (/en, /it, ...). On sub-pages (/en/privacy) they mislabel — verify per-page alternates."
warn "homepage [locale]/page.tsx is a client component ('use client') — confirm enough server-rendered body text for crawlers."

echo ""
echo -e "${BLUE}=== Summary: ${RED}$fails FAIL${NC}, ${YELLOW}$warns WARN${NC} ===${NC}"
if [ "$fails" -gt 0 ]; then
  echo -e "${RED}SEO regressions present (see FAIL lines above).${NC}"
  exit 1
fi
echo -e "${GREEN}No FAIL-level SEO regressions.${NC}"
exit 0
