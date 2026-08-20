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
#   server-url           Print the DATABASE_URL for an Azure server       (read-only)
#   rehearse             Alembic stamp -> check -> upgrade on a COPY      (mutates a copy)
#   delete-server        Delete a restored Azure server                   (DESTRUCTIVE)
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

log()  { echo -e "${BLUE}$*${NC}"; }
ok()   { echo -e "${GREEN}✓ $*${NC}"; }
warn() { echo -e "${YELLOW}$*${NC}"; }
die()  { echo -e "${RED}Error: $*${NC}" >&2; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || die "$1 not found. $2"
}

# Join arguments with '|' for use inside an ERE alternation.
join_alt() {
  local IFS='|'
  echo "$*"
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

# Azure Flexible Server has extensions the local pgvector image does not ship.
# pg_cron is the one that always bites: the dump carries
# `CREATE EXTENSION pg_cron`, a `cron` schema, and the contents of cron.job /
# cron.job_run_details. None of it exists locally, every one of those entries
# fails, and pg_restore then exits non-zero — which under `set -e` aborts the
# whole restore even though nothing this application reads is missing.
#
# Filtering the table of contents is better than ignoring the exit code: the
# known-absent objects are never attempted, so any error that *does* survive is
# a real one worth stopping for.
#
# Emits a temp file path (caller deletes it), or nothing when there is nothing
# to filter. Override with SKIP_EXTENSIONS / SKIP_SCHEMAS; set SKIP_EXTENSIONS
# to the empty string to restore the dump verbatim.
build_local_toc() {
  local dump="$1" url="${2:-}" pw="${3:-}"
  local -a exts schemas alts=()
  read -r -a exts    <<< "${SKIP_EXTENSIONS-pg_cron}"
  read -r -a schemas <<< "${SKIP_SCHEMAS-cron}"

  # Every extension the dump creates that this server cannot provide is added
  # to the list automatically. The hardcoded pg_cron default only covers the
  # one we know about; auto-detection means the next Azure-only extension
  # produces a skip rather than 20 failed objects and a re-run. Skipped
  # entirely when SKIP_EXTENSIONS is explicitly empty (restore verbatim).
  if [[ -n "$url" && -n "${SKIP_EXTENSIONS-unset}" ]]; then
    local -a missing=()
    local available dumped ext
    available="$(PGPASSWORD="$pw" psql "$url" -tAc \
      "SELECT name FROM pg_available_extensions" 2>/dev/null || true)"
    if [[ -n "$available" ]]; then
      dumped="$(pg_restore -l "$dump" | sed -nE 's/.*[[:space:]]EXTENSION[[:space:]]+-[[:space:]]+([A-Za-z0-9_]+).*/\1/p' | sort -u)"
      for ext in $dumped; do
        grep -qxF "$ext" <<< "$available" || missing+=("$ext")
      done
    fi
    if [[ ${#missing[@]} -gt 0 ]]; then
      warn "Extensions in the dump that this server cannot provide: ${missing[*]}" >&2
      exts+=("${missing[@]}")
    fi
  fi
  # De-duplicate; the default and the auto-detected list overlap on pg_cron.
  [[ ${#exts[@]} -gt 0 ]] && mapfile -t exts < <(printf '%s\n' "${exts[@]}" | sort -u)

  # A TOC line is "<id>; <oid> <oid> <DESCRIPTION> <schema> <name> <owner>",
  # where objects belonging to no schema (extensions, and the schemas
  # themselves) carry "-" in the schema column.
  # Extensions: match by name anywhere on the line.
  # Schema-owned objects: match only in the schema position — right after the
  # uppercase description — so a public table that happens to be named "cron"
  # is not swept up with them.
  # The schemas' own entries ("SCHEMA - cron postgres", "ACL - cron ...") sit in
  # the name column instead, hence the third alternative.
  [[ ${#exts[@]}    -gt 0 ]] && alts+=("(^|[[:space:]])($(join_alt "${exts[@]}"))([[:space:]]|\$)")
  if [[ ${#schemas[@]} -gt 0 ]]; then
    alts+=("[[:space:]][A-Z][A-Z ]*[[:space:]]($(join_alt "${schemas[@]}"))[[:space:]]")
    alts+=("[[:space:]]-[[:space:]]($(join_alt "${schemas[@]}"))([[:space:]]|\$)")
  fi
  [[ ${#alts[@]} -eq 0 ]] && return 0

  local skip_re toc count
  skip_re="$(join_alt "${alts[@]}")"
  toc="$(mktemp)"
  pg_restore -l "$dump" | grep -vE "$skip_re" > "$toc"
  count="$(pg_restore -l "$dump" | grep -cE "$skip_re" || true)"

  if [[ "$count" == "0" ]]; then
    rm -f "$toc"
    return 0
  fi
  warn "Skipping $count entr$([[ "$count" == "1" ]] && echo y || echo ies) not available locally" >&2
  warn "  extensions: ${exts[*]:-none}   schemas: ${schemas[*]:-none}" >&2
  printf '%s' "$toc"
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
  local -a toc_args=()
  local toc log_file
  toc="$(build_local_toc "$dump" "$url" "$pw")"
  [[ -n "$toc" ]] && toc_args=(-L "$toc")
  log_file="$(mktemp)"

  if ! PGPASSWORD="$pw" pg_restore --no-owner --no-acl -j "${JOBS:-4}" \
       ${toc_args[@]+"${toc_args[@]}"} -d "$url" "$dump" 2>&1 | tee "$log_file"; then
    echo
    warn "Distinct errors reported by pg_restore:"
    # The raw output repeats the same handful of causes once per failed object.
    # Collapsing to distinct reasons is what makes this diagnosable at a glance.
    grep -oE 'ERROR:.*' "$log_file" | sort | uniq -c | sort -rn | head -20 | sed 's/^/    /'
    echo
    warn "Full output: $log_file"
    warn "If a cause is an extension Azure has and this image does not, add it to"
    warn "SKIP_EXTENSIONS and its schema to SKIP_SCHEMAS, then re-run:"
    warn "  SKIP_EXTENSIONS='pg_cron <other>' SKIP_SCHEMAS='cron <other>' make db-restore-local DUMP=$dump"
    die "Restore incomplete — do not rehearse a migration against this copy."
  fi
  rm -f "$log_file"
  [[ -n "$toc" ]] && rm -f "$toc"

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
  echo
  echo "Next:"
  echo "  make az-pg-add-ip SERVER=$target        # open the firewall on the COPY"
  echo "  make db-server-url SERVER=$target       # build its DATABASE_URL"
  echo "  make db-delete-server SERVER=$target    # when you are done — it is billable"
}

cmd_server_url() {
  need az "Install the Azure CLI: https://aka.ms/azure-cli"
  require_var PG_RG "the Azure resource group"
  require_var SERVER "the server to build a URL for, e.g. make db-server-url SERVER=${PG_SERVER:-<server>}-restore-20260810"
  # shellcheck disable=SC2153  # SERVER is an environment input (see the Makefile
  # targets), not a misspelling of the unrelated local `server` in cmd_info.
  local target="$SERVER" fqdn

  fqdn="$(az postgres flexible-server show \
    --resource-group "$PG_RG" --name "$target" \
    --query fullyQualifiedDomainName -o tsv 2>/dev/null || true)"
  [[ -n "$fqdn" ]] || die "No server '$target' in resource group '$PG_RG' (or the restore is still provisioning)."

  # sslmode, never ssl — see Rule #1 in docs/MIGRATION_GUIDELINES.md.
  # No password: a PITR copy keeps the source server's admin credentials, and
  # this URL is meant to be pasted into a shell where PGPASSWORD supplies it.
  echo "postgresql://${DB_USER:-bible}@${fqdn}:5432/${PG_DB:-bibledb}?sslmode=require"
  warn "Password: export PGPASSWORD — a PITR copy keeps the SOURCE server's admin credentials." >&2
  warn "asyncpg and libpq both read PGPASSWORD, so it never needs to go in the URL." >&2
}

cmd_delete_server() {
  need az "Install the Azure CLI: https://aka.ms/azure-cli"
  require_var PG_RG "the Azure resource group"
  require_var SERVER "the restored server to delete, e.g. make db-delete-server SERVER=..."
  # shellcheck disable=SC2153  # SERVER is an environment input (see the Makefile
  # targets), not a misspelling of the unrelated local `server` in cmd_info.
  local target="$SERVER"

  # The whole point of this target is tearing down rehearsal copies, so the one
  # thing it must never accept is the production server name.
  [[ "$target" != "${PG_SERVER:-}" ]] || die "Refusing to delete '$target' — that is PG_SERVER (production).
This target exists to delete restored *copies*. Deleting the live server is
not something to do through a convenience wrapper."

  warn "Deleting an Azure server also deletes its automatic backups."
  require_confirmation "$target" "permanently delete the Azure server '$target'"
  az postgres flexible-server delete --resource-group "$PG_RG" --name "$target" --yes
  ok "Deleted $target"
}

# Stage 1 of the Alembic prod-adoption sequence (BITB-089): prove the r0001
# baseline matches a real copy of production before stamping production itself.
#
# stamp-then-check, not check alone: `alembic check` runs autogenerate, and
# autogenerate refuses to compare anything while the database is not at head
# ("Target database is not up to date."). A restored copy of prod carries the
# schema but none of Alembic's bookkeeping, so it must be stamped first — which
# also rehearses the exact command Stage 2 runs against production.
cmd_rehearse() {
  need alembic "Install the API requirements: pip install -r api/requirements.txt"
  require_database_url
  local baseline="${BASELINE:-r0001}"

  # A PITR copy's FQDN is "<server>.postgres.database.azure.com", so the
  # production server name is a prefix of the production host and of nothing
  # else. There is deliberately no override: stamping production is a
  # documented one-time operator step, and `upgrade head` against production is
  # the deploy pipeline's job, not a laptop's.
  if [[ -n "${PG_SERVER:-}" && "$DB_HOST" == "$PG_SERVER".* ]]; then
    die "Refusing to rehearse against '$DB_HOST' — that is production.
Restore a copy first (make db-restore-new-server, or make db-restore-local),
then point DATABASE_URL at the copy. For production itself, follow the
operator runbook in docs/MIGRATION_GUIDELINES.md."
  fi

  log "Rehearsing the Alembic baseline against $(redact_url "$DB_URL")"
  export DATABASE_URL="$DB_URL"
  cd api || die "Run this from the repository root."

  # Connect via `alembic current` first, and translate a failure into something
  # actionable. Alembic surfaces a connection problem as a ~40-line asyncpg
  # traceback, and the most common cause here is simply a missing password:
  # DATABASE_URL deliberately carries none (repo convention), and asyncpg falls
  # back to PGPASSWORD -- which is easy to forget to export.
  # stdout and stderr stay separate on purpose: alembic logs INFO lines to
  # stderr, and merging them would make `tail -n1` read a log line as the
  # revision id -- reporting an unstamped database as stamped.
  local current raw errfile
  errfile="$(mktemp)"
  if ! raw="$(alembic current 2>"$errfile")"; then
    tail -n 3 "$errfile" >&2
    rm -f "$errfile"
    echo >&2
    die "Could not connect to $(redact_url "$DB_URL").
If this is the local restore container, its password is 'local':
  export PGPASSWORD=local
asyncpg reads PGPASSWORD when the URL carries no password (as it should not).
For an Azure copy, export the source server's admin password instead."
  fi
  rm -f "$errfile"
  current="$(printf '%s' "$raw" | tail -n1 | tr -d '[:space:]')"
  if [[ -z "$current" ]]; then
    log "No alembic_version row — stamping $baseline (writes one row, zero DDL)"
    alembic stamp "$baseline"
  else
    log "Already stamped at $current — leaving it alone"
  fi

  log "alembic check (the gate — read-only, emits no DDL)"
  if ! alembic check; then
    echo
    die "The baseline does not match this copy of production.
Reconcile the difference with a reviewed revision — do NOT stamp production
until this is clean. See docs/MIGRATION_GUIDELINES.md, Stage 1."
  fi

  log "alembic upgrade head (must be a no-op)"
  alembic upgrade head
  alembic current

  ok "Baseline verified against this copy. Production can be stamped (Stage 2)."
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
    server-url)          cmd_server_url ;;
    delete-server)       cmd_delete_server ;;
    rehearse)            cmd_rehearse ;;
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
