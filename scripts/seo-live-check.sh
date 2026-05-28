#!/bin/bash
# SEO live check for a deployed site (default: voxquieta.org).
# Run this from a network that can reach the domain — the Claude Code web
# sandbox blocks it (egress policy returns 403 host_not_allowed).
#
# Usage:
#   bash scripts/seo-live-check.sh [BASE_URL] [LOCALE]
#   BASE_URL=https://voxquieta.org LOCALES="en it de" bash scripts/seo-live-check.sh
#
# Prints HTTP statuses for key routes and the <head> meta of the homepage +
# a sub-page, then a copy-paste summary to hand back to Claude.

set -uo pipefail

BASE_URL="${1:-${BASE_URL:-https://voxquieta.org}}"
BASE_URL="${BASE_URL%/}"
PRIMARY_LOCALE="${2:-en}"
read -r -a LOCALES <<< "${LOCALES:-en it de es fr pt ar ru zh hi ko}"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; BLUE='\033[0;34m'; NC='\033[0m'
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
CURL=(curl -sS --max-time 25 -A "$UA")

if ! command -v curl >/dev/null 2>&1; then
  echo -e "${RED}curl not found — install it or provide the data manually.${NC}"; exit 2
fi

echo -e "${BLUE}=== Vox Quieta SEO live check ===${NC}"
echo "base: $BASE_URL   primary locale: $PRIMARY_LOCALE"
echo ""

# --- status codes -----------------------------------------------------------
echo -e "${BLUE}-- HTTP status (no-follow / follow / redirects -> final) --${NC}"
status() {
  local path="$1" url="$BASE_URL$1"
  local nf fl nr eff
  nf=$("${CURL[@]}" -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "ERR")
  fl=$("${CURL[@]}" -L -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "ERR")
  nr=$("${CURL[@]}" -L -o /dev/null -w "%{num_redirects}" "$url" 2>/dev/null || echo "?")
  eff=$("${CURL[@]}" -L -o /dev/null -w "%{url_effective}" "$url" 2>/dev/null || echo "?")
  local color="$GREEN"
  case "$fl" in 2*) color="$GREEN";; 3*) color="$YELLOW";; *) color="$RED";; esac
  printf "  ${color}%-3s${NC}/%-3s  r=%-2s  %-32s -> %s\n" "$nf" "$fl" "$nr" "$path" "$eff"
}

status "/"
for loc in "${LOCALES[@]}"; do status "/$loc"; done
for sub in privacy terms changelog; do status "/$PRIMARY_LOCALE/$sub"; done
status "/privacy"                              # un-prefixed -> expect 4XX
status "/$PRIMARY_LOCALE/__seo_probe_404__"    # bogus -> expect 404
status "/robots.txt"
status "/sitemap.xml"
status "/favicon.ico"

# --- head meta ---------------------------------------------------------------
attr() { # extract attribute value: attr <html> <tag-substr> <attr>
  grep -oiE "<[a-z]+[^>]*$2[^>]*>" <<< "$1" \
    | grep -oiE "$3=\"[^\"]*\"" | sed -E "s/^[^\"]*\"//; s/\"$//" | head -20
}

headcheck() {
  local path="$1" url="$BASE_URL$1"
  echo ""
  echo -e "${BLUE}-- <head> meta for $path --${NC}"
  local html xrobots
  html=$("${CURL[@]}" -L "$url" 2>/dev/null || echo "")
  xrobots=$("${CURL[@]}" -L -D - -o /dev/null "$url" 2>/dev/null | grep -i "^x-robots-tag:" || true)
  if [ -z "$html" ]; then echo -e "  ${RED}(no body — request failed/blocked)${NC}"; return; fi

  local title desc canon
  title=$(grep -oiE "<title[^>]*>[^<]*</title>" <<< "$html" | sed -E "s/<[^>]+>//g" | head -1)
  desc=$(grep -oiE "<meta[^>]*name=\"description\"[^>]*>" <<< "$html" | grep -oiE "content=\"[^\"]*\"" | sed -E "s/^content=\"//; s/\"$//" | head -1)
  canon=$(grep -oiE "<link[^>]*rel=\"canonical\"[^>]*>" <<< "$html" | grep -oiE "href=\"[^\"]*\"" | head -1)

  printf "  title       (%s) : %s\n" "${#title}" "${title:-<none>}"
  [ "${#title}" -gt 60 ] && echo -e "    ${YELLOW}^ title > 60 chars${NC}"
  [ -z "$title" ] && echo -e "    ${RED}^ missing <title>${NC}"
  printf "  description  (%s) : %s\n" "${#desc}" "${desc:-<none>}"
  [ "${#desc}" -gt 160 ] && echo -e "    ${YELLOW}^ description > 160 chars${NC}"
  [ -z "$desc" ] && echo -e "    ${RED}^ missing meta description${NC}"
  printf "  canonical        : %s\n" "${canon:-<none>}"

  echo "  open graph:"; attr "$html" "og:" "content" | sed "s/^/    /" | head -8
  grep -qi "og:" <<< "$html" || echo -e "    ${RED}<none — no Open Graph tags>${NC}"
  echo "  twitter:";    attr "$html" "twitter:" "content" | sed "s/^/    /" | head -6
  grep -qi "twitter:" <<< "$html" || echo -e "    ${RED}<none — no Twitter card tags>${NC}"
  echo "  hreflang:"
  grep -oiE "<link[^>]*rel=\"alternate\"[^>]*>" <<< "$html" \
    | grep -oiE "hreflang=\"[^\"]*\"[^>]*href=\"[^\"]*\"|href=\"[^\"]*\"[^>]*hreflang=\"[^\"]*\"" \
    | sed "s/^/    /" | head -15
  grep -qi "hreflang" <<< "$html" || echo -e "    ${RED}<none — no hreflang alternates>${NC}"
  [ -n "$xrobots" ] && echo "  $xrobots"

  # crude body-text gauge (server-rendered indexable content)
  local words
  words=$(sed -E "s/<script[^>]*>.*<\/script>//g; s/<[^>]+>/ /g" <<< "$html" | tr -s " " "\n" | grep -cE "[A-Za-z]{2,}" || true)
  words="${words:-0}"
  printf "  ~server-rendered words: %s %s\n" "$words" "$([ "$words" -lt 80 ] && echo "(thin — likely client-rendered)" || echo)"
}

headcheck "/$PRIMARY_LOCALE"
headcheck "/$PRIMARY_LOCALE/privacy"

echo ""
echo -e "${BLUE}-- robots.txt --${NC}"
"${CURL[@]}" -L "$BASE_URL/robots.txt" 2>/dev/null | head -20 || echo "  (unavailable)"
echo ""
echo -e "${BLUE}-- sitemap.xml (first lines) --${NC}"
"${CURL[@]}" -L "$BASE_URL/sitemap.xml" 2>/dev/null | head -15 || echo "  (unavailable)"

echo ""
echo -e "${GREEN}Done. Paste the output above back to Claude for analysis.${NC}"
