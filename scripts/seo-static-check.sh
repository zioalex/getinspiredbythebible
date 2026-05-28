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
LIB="$FE/src/lib"
LAYOUT="$APP/[locale]/layout.tsx"
MSG="$FE/messages"

# Metadata is allowed to live in src/app *or* be factored into a shared helper
# under src/lib (e.g. lib/seo.ts). Scan both so refactors aren't false-flagged.
SEO_PATHS=("$APP")
[ -d "$LIB" ] && SEO_PATHS+=("$LIB")
seo_grep() { grep -rqE "$1" "${SEO_PATHS[@]}" 2>/dev/null; }

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
seo_grep "metadataBase" \
  && pass "metadataBase set (resolves relative OG/canonical URLs)" \
  || fail "metadataBase missing — OG/canonical relative URLs won't resolve (set it in app/layout.tsx)"

seo_grep "openGraph" \
  && pass "openGraph metadata present" \
  || fail "no Open Graph metadata (og:title/description/image) under src/app or src/lib"

seo_grep "twitter:|card:[[:space:]]*\"summary|twitter" \
  && pass "twitter card metadata present" \
  || fail "no Twitter card metadata under src/app or src/lib"

seo_grep "canonical" \
  && pass "canonical alternates referenced" \
  || warn "no canonical URLs (alternates.canonical) found under src/app or src/lib"

seo_grep "x-default" \
  && pass "hreflang x-default present" \
  || warn "no hreflang x-default — add an x-default alternate for locale-agnostic crawlers"

seo_grep "application/ld\\+json|JsonLd|schema\\.org" \
  && pass "JSON-LD structured data present" \
  || warn "no JSON-LD structured data (WebSite/Organization) under src/app or src/lib"

echo ""
echo -e "${BLUE}-- Crawl / index files --${NC}"
{ [ -f "$APP/sitemap.ts" ] || [ -f "$APP/sitemap.tsx" ] || [ -f "$FE/public/sitemap.xml" ]; } \
  && pass "sitemap present (app/sitemap.ts or public/sitemap.xml)" \
  || fail "no sitemap — create frontend/src/app/sitemap.ts"

{ [ -f "$APP/robots.ts" ] || [ -f "$FE/public/robots.txt" ]; } \
  && pass "robots present (app/robots.ts or public/robots.txt)" \
  || fail "no robots — create frontend/src/app/robots.ts"

# Check each candidate independently — a single `ls` over a mixed list exits
# non-zero if *any* operand is missing, which would mask a present icon.
icon_found=""
for pat in "$APP/favicon.ico" "$APP"/icon.* "$APP"/apple-icon.* "$FE"/public/favicon* "$FE"/public/*.ico; do
  if compgen -G "$pat" >/dev/null 2>&1; then icon_found="$pat"; break; fi
done
if [ -n "$icon_found" ]; then
  pass "favicon / app icon present"
else
  fail "no favicon/app icon (app/favicon.ico | app/icon.* | public/*.ico)"
fi

echo ""
echo -e "${BLUE}-- Titles --${NC}"
grep -q "template:" "$LAYOUT" 2>/dev/null \
  && pass "title.template present in [locale]/layout.tsx" \
  || fail "no title.template — sub-pages render without a brand suffix"

# The home <title> may be composed at runtime (e.g. title.default = "Brand —
# Tagline"). When the layout builds a default title from both Metadata.title
# and Metadata.description, measure that *effective* string, not the bare key.
if command -v node >/dev/null 2>&1 && [ -f "$MSG/en.json" ]; then
  composed=""
  if grep -q "default:" "$LAYOUT" 2>/dev/null \
     && grep -q "template:" "$LAYOUT" 2>/dev/null \
     && grep -qE 't\("title"\).*t\("description"\)|homeTitle' "$LAYOUT" 2>/dev/null; then
    composed="1"
  fi
  read -r title_len eff_title < <(node -e '
    try {
      const m = require(process.argv[1]).Metadata || {};
      const t = m.title || ""; const d = m.description || "";
      const eff = process.argv[2] === "1" ? `${t} — ${d}` : t;
      process.stdout.write(eff.length + " " + eff);
    } catch(e) { process.stdout.write("-1 "); }
  ' "$MSG/en.json" "$composed" 2>/dev/null)
  if [ "$title_len" = "-1" ]; then
    warn "could not read Metadata.title from messages/en.json"
  elif [ "$title_len" -ge 15 ]; then
    pass "homepage title length is $title_len chars (\"$eff_title\")"
  else
    fail "homepage title is only $title_len chars (\"$eff_title\") — too short/generic"
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
echo -e "${BLUE}-- hreflang per-page alternates --${NC}"
# Sub-pages must emit their own alternates so hreflang points at the matching
# translated page (/it/privacy), not every locale's home (/it). Detect whether
# each sub-page builds alternates itself (directly or via a shared helper).
missing_alt=""
for sp in privacy terms changelog; do
  f="$APP/[locale]/$sp/page.tsx"
  [ -f "$f" ] || continue
  grep -qE "pageMetadata|buildAlternates|alternates" "$f" 2>/dev/null \
    || missing_alt="$missing_alt $sp"
done
if [ -z "$missing_alt" ]; then
  pass "sub-pages emit per-page alternates (canonical/hreflang track the page path)"
else
  warn "sub-pages without per-page alternates:$missing_alt — hreflang may point to locale roots"
fi

echo ""
echo -e "${BLUE}-- Manual-review reminders (not auto-checkable) --${NC}"
grep -q "use client" "$APP/[locale]/page.tsx" 2>/dev/null \
  && warn "homepage [locale]/page.tsx is a client component ('use client') — confirm enough server-rendered body text for crawlers." \
  || pass "homepage [locale]/page.tsx is server-rendered"

echo ""
echo -e "${BLUE}=== Summary: ${RED}$fails FAIL${NC}, ${YELLOW}$warns WARN${NC} ===${NC}"
if [ "$fails" -gt 0 ]; then
  echo -e "${RED}SEO regressions present (see FAIL lines above).${NC}"
  exit 1
fi
echo -e "${GREEN}No FAIL-level SEO regressions.${NC}"
exit 0
