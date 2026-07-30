#!/bin/bash
# Database backup & restore helper (see docs/HOW-TO-BACKUP-RESTORE-DATABASE.md).
#
# Wraps the four scenarios in the runbook so the routine parts are one command
# and the dangerous parts are hard to do by accident.
#
# Usage (normally via the Makefile — `make db-backup`, `make db-restore-local`, ...):
#   bash scripts/db-backup-restore.sh <command> [options]
#
# Commands:
#   info                 Show backup retention / earliest restore point   (read-only)
#   dump                 pg_dump -Fc the target database to a file        (read-only)
#   verify               Run the post-restore verification checklist      (read-only)
#   restore-local        Restore a dump into a local pgvector container   (local only)
#   restore-new-server   Azure PITR into a NEW server                     (non-destructive)
#   restore-same-server  Replace an existing database from a dump         (DESTRUCTIVE)
#
# Connection: set DATABASE_URL, or PGHOST/PGDATABASE/PGUSER + PGPASSWORD.
# Passwords are never taken as command-line arguments and never echoed.

set -euo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; BLUE='\033[0;34m'; NC='\033[0m'

SCRIPT_NAME="$(basename "$0")"
BACKUP_DIR="${BACKUP_DIR:-backups}"
LOCAL_CONTAINER="${LOCAL_CONTAINER:-bibledb-restore}"
LOCAL_PORT="${LOCAL_PORT:-5433}"
LOCAL_IMAGE="${LOCAL_IMAGE:-pgvector/pgvector:pg16}"
LOCAL_DB="${LOCAL_DB:-bibledb}"

# Hosts we accept as "obviously local/CI" for destructive local operations.
# Mirrors _SAFE_HOSTS in api/tests/test_alembic_migrations.py deliberately —
# same rule, same names, so the two cannot drift into disagreeing.
SAFE_HOSTS=("localhost" "127.0.0.1" "postgres" "db")

log()  { echo -e "${BLUE}$*${NC}"; }
ok()   { echo -e "${GREEN}✓ $*${NC}"; }
warn() { echo -e "${YELLOW}$*${NC}"; }
die()  { echo -e "${RED}Error: $*${NC}" >&2; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || die "$1 not found. $2"
}

# require_var NAME "what it is / example"
require_var() {
  local name="$1"
  [[ -n "${!name:-}" ]] || die "$name is not set — $2"
}

# --- URL handling -----------------------------------------------------------

# Rewrite an application-style URL into one libpq (psql/pg_dump/pg_restore)
# accepts. Two transformations, both of which bite in practice:
#   postgresql+asyncpg://  -> postgresql://   (SQLAlchemy driver suffix)
#   ?ssl=require           -> ?sslmode=require (asyncpg spelling; libpq wants sslmode)
# See Rule #1 in docs/MIGRATION_GUIDELINES.md.
normalize_libpq_url() {
  # sed rather than ${var//pat/rep}: bash 5.2+ treats '&' in a replacement as
  # the matched text, which silently mangles the '&ssl=' case.
  # '([?&])ssl=' cannot match an existing 'sslmode=' (no '=' after 'ssl').
  printf '%s' "$1" | sed -E \
    -e 's|^postgres(ql)?\+[a-z0-9]+://|postgresql://|' \
    -e 's|([?&])ssl=|\1sslmode=|g'
}

# Extract the host from a URL: strip scheme, then userinfo, then port/path/query.
url_host() {
  printf '%s' "$1" | sed -e 's|^[a-zA-Z0-9+.-]*://||' -e 's|^[^@/]*@||' -e 's|[:/?].*||'
}

# Print a URL with any password replaced, so it is safe to log.
redact_url() {
  printf '%s' "$1" | sed -E 's|://([^:/@]+):[^@]*@|://\1:****@|'
}

require_database_url() {
  [[ -n "${DATABASE_URL:-}" ]] || die "DATABASE_URL is not set (or pass --url).
Set it to the database you want to act on, e.g.
  export DATABASE_URL='postgresql://user@host:5432/bibledb?sslmode=require'
Use PGPASSWORD for the password rather than putting it in the URL."
  DB_URL="$(normalize_libpq_url "$DATABASE_URL")"
  DB_HOST="$(url_host "$DB_URL")"
  [[ -n "$DB_HOST" ]] || die "Could not parse a host out of DATABASE_URL."
}

is_safe_host() {
  local host="$1" safe
  for safe in "${SAFE_HOSTS[@]}"; do
    [[ "$host" == "$safe" ]] && return 0
  done
  return 1
}

# Destructive commands require the operator to retype the exact target.
# A y/n prompt is not enough: these run in scripts and over SSH, where a
# stray "yes" is cheap and a dropped database is not.
require_confirmation() {
  local expected="$1" what="$2"
  if [[ -n "${CONFIRM:-}" ]]; then
    [[ "$CONFIRM" == "$expected" ]] || die "CONFIRM does not match.
Expected: $expected
Got:      $CONFIRM"
    return 0
  fi
  warn "About to $what"
  warn "This cannot be undone."
  echo -en "${YELLOW}Type the target exactly (${expected}) to proceed: ${NC}"
  local answer
  read -r answer </dev/tty || die "No terminal available. Re-run with CONFIRM='$expected'."
  [[ "$answer" == "$expected" ]] || die "Confirmation did not match — nothing was changed."
}

# --- commands ---------------------------------------------------------------

cmd_info() {
  need az "Install the Azure CLI: https://aka.ms/azure-cli"
  require_var PG_RG "the Azure resource group (e.g. bible-app-rg)"
  require_var PG_SERVER "the Flexible Server name"
  local rg="$PG_RG" server="$PG_SERVER"

  log "Backup configuration for $server"
  az postgres flexible-server show \
    --resource-group "$rg" --name "$server" \
    --query "{server:name, version:version, earliestRestore:backup.earliestRestoreDate, retentionDays:backup.backupRetentionDays, geoRedundant:backup.geoRedundantBackup}" \
    -o table
  echo
  warn "Point-in-time restore always creates a NEW server; it cannot restore in place."
  warn "Restores are only possible back to 'earliestRestore' (often later than retentionDays implies)."
}

cmd_dump() {
  need pg_dump "Install the postgresql-client package."
  require_database_url

  mkdir -p "$BACKUP_DIR"
  local stamp out
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out="${DUMP:-${BACKUP_DIR}/${DB_HOST%%.*}-${stamp}.dump}"

  # Optional extra pg_dump flags, e.g.
  #   DUMP_ARGS="--exclude-table-data=verses --exclude-table-data=passages"
  # to skip the embedding bulk (schema is kept; data is re-derivable by seeding).
  local -a extra=()
  [[ -n "${DUMP_ARGS:-}" ]] && read -r -a extra <<< "$DUMP_ARGS"

  log "Dumping $(redact_url "$DB_URL")"
  log "  -> $out"
  # -Fc (custom format) is required for parallel/selective restore later.
  # --no-owner/--no-acl because Azure gives no superuser, so source roles
  # will not exist verbatim on any target we restore into.
  pg_dump "$DB_URL" -Fc --no-owner --no-acl ${extra[@]+"${extra[@]}"} -f "$out"
  ok "Wrote $out ($(du -h "$out" | cut -f1))"
  warn "Dumps contain the full database. Store them accordingly; $BACKUP_DIR/ is git-ignored."
}

cmd_verify() {
  need psql "Install the postgresql-client package."
  require_database_url

  log "Verifying $(redact_url "$DB_URL")"
  psql "$DB_URL" -v ON_ERROR_STOP=1 <<'SQL'
\echo '--- extensions (vector must be present) ---'
SELECT extname, extversion FROM pg_extension ORDER BY 1;
\echo '--- row counts ---'
SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 20;
\echo '--- HNSW indexes ---'
SELECT indexname, tablename FROM pg_indexes
 WHERE schemaname = 'public' AND indexdef ILIKE '%hnsw%' ORDER BY 1;
\echo '--- INVALID indexes (must be empty) ---'
SELECT indexrelid::regclass AS invalid_index FROM pg_index WHERE NOT indisvalid;
\echo '--- migration bookkeeping ---'
SELECT to_regclass('public.schema_migrations') AS legacy_tracker,
       to_regclass('public.alembic_version')   AS alembic_tracker;
SQL

  # An invalid index is the failure this whole checklist exists to catch:
  # the restore "succeeds", searches silently fall back to sequential scans.
  local invalid
  invalid="$(psql "$DB_URL" -tAc "SELECT count(*) FROM pg_index WHERE NOT indisvalid")"
  if [[ "$invalid" != "0" ]]; then
    die "$invalid invalid index(es) present — reindex before treating this restore as good."
  fi
  ok "No invalid indexes."
}

cmd_restore_local() {
  need docker "Install Docker, or restore into a Postgres 16 + pgvector instance yourself."
  need pg_restore "Install the postgresql-client package."
  require_var DUMP "the dump file to restore, e.g. make db-restore-local DUMP=backups/x.dump"
  local dump="$DUMP"
  [[ -f "$dump" ]] || die "Dump file not found: $dump"

  local pw="${PGPASSWORD:-local}"

  if docker ps -a --format '{{.Names}}' | grep -qx "$LOCAL_CONTAINER"; then
    warn "Container '$LOCAL_CONTAINER' already exists."
    require_confirmation "$LOCAL_CONTAINER" "remove and recreate the local container '$LOCAL_CONTAINER'"
    docker rm -f "$LOCAL_CONTAINER" >/dev/null
  fi

  log "Starting $LOCAL_IMAGE as '$LOCAL_CONTAINER' on port $LOCAL_PORT"
  docker run -d --name "$LOCAL_CONTAINER" \
    -e POSTGRES_PASSWORD="$pw" -e POSTGRES_DB="$LOCAL_DB" \
    -p "${LOCAL_PORT}:5432" "$LOCAL_IMAGE" >/dev/null

  local url="postgresql://postgres@localhost:${LOCAL_PORT}/${LOCAL_DB}"
  log "Waiting for Postgres to accept connections..."
  local i
  for i in $(seq 1 60); do
    if PGPASSWORD="$pw" psql "$url" -c 'SELECT 1' >/dev/null 2>&1; then break; fi
    [[ "$i" == "60" ]] && die "Postgres did not become ready in 60s. Check: docker logs $LOCAL_CONTAINER"
    sleep 1
  done

  # HNSW index rebuilds dominate restore time; the default is far too small.
  PGPASSWORD="$pw" psql "$url" -q -c "ALTER SYSTEM SET maintenance_work_mem = '512MB';" \
                                 -c "SELECT pg_reload_conf();" >/dev/null

  log "Restoring $dump"
  PGPASSWORD="$pw" pg_restore --no-owner --no-acl -j "${JOBS:-4}" -d "$url" "$dump"

  ok "Restored into $url"
  echo "  DATABASE_URL=\"$url\" PGPASSWORD=$pw make db-restore-verify"
}

cmd_restore_new_server() {
  need az "Install the Azure CLI: https://aka.ms/azure-cli"
  require_var PG_RG "the Azure resource group"
  require_var PG_SERVER "the SOURCE server to restore from"
  require_var NEW_SERVER "a name for the new restored server"
  require_var RESTORE_POINT "the restore point in UTC, e.g. 2026-07-30T14:25:00Z (see: make db-backup-info)"
  local rg="$PG_RG" source="$PG_SERVER" target="$NEW_SERVER" point="$RESTORE_POINT"

  log "Point-in-time restore"
  echo "  source : $source"
  echo "  target : $target   (new server — the source is not modified)"
  echo "  point  : $point"

  # Non-destructive to the source, but it provisions a billable resource,
  # so still worth an explicit acknowledgement.
  require_confirmation "$target" "create a new server '$target' restored from '$source'"

  az postgres flexible-server restore \
    --resource-group "$rg" --name "$target" \
    --source-server "$source" --restore-time "$point"

  ok "Restore started for $target"
  warn "Verify it, then remember to delete it:"
  echo "  az postgres flexible-server delete -g $rg -n $target --yes"
}

cmd_restore_same_server() {
  need pg_restore "Install the postgresql-client package."
  require_database_url
  require_var DUMP "the dump file to restore from"
  local dump="$DUMP"
  [[ -f "$dump" ]] || die "Dump file not found: $dump"

  warn "════════════════════════════════════════════════════════════════"
  warn " DESTRUCTIVE: pg_restore --clean --if-exists"
  warn " Every object in the target is DROPPED and recreated from the dump."
  warn "════════════════════════════════════════════════════════════════"
  echo "  target : $(redact_url "$DB_URL")"
  echo "  dump   : $dump"
  echo
  warn "Before continuing you should have:"
  warn "  1. a fresh dump of the CURRENT state (make db-backup) — your only undo"
  warn "  2. writes stopped (scale the backend to zero), or you will restore over live traffic"
  echo

  require_confirmation "$DB_HOST" "replace the entire database on '$DB_HOST' from $dump"

  log "Restoring..."
  pg_restore --clean --if-exists --no-owner --no-acl -d "$DB_URL" "$dump"
  ok "Restore complete."
  warn "Now run: make db-restore-verify   (and bring the backend back up)"
}

usage() {
  # Print the header comment block (everything after the shebang, up to the
  # first non-comment line) so the docs and --help cannot drift apart.
  awk 'NR>1 && /^#/ { sub(/^# ?/, ""); print; next } NR>1 { exit }' "$0"
  exit "${1:-0}"
}

main() {
  local cmd="${1:-}"
  [[ -n "$cmd" ]] || usage 1
  shift || true
  case "$cmd" in
    info)                cmd_info ;;
    dump)                cmd_dump ;;
    verify)              cmd_verify ;;
    restore-local)       cmd_restore_local ;;
    restore-new-server)  cmd_restore_new_server ;;
    restore-same-server) cmd_restore_same_server ;;
    -h|--help|help)      usage 0 ;;
    *) die "Unknown command '$cmd'. Run '$SCRIPT_NAME --help'." ;;
  esac
}

# Only dispatch when executed. Sourcing exposes the helpers for testing:
#   source scripts/db-backup-restore.sh
# An `if` rather than `[[ ... ]] && main`: the latter makes the *sourced* file
# return non-zero when the condition is false, which aborts any caller running
# under `set -e`.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
