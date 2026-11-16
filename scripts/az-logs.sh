#!/usr/bin/env bash
# Azure Container Apps log helpers behind the `make az-logs-*` targets (BITB-319).
#
#   az-logs.sh tail  <app> <console|system>   live stream (Ctrl+C to stop)
#   az-logs.sh query <app>                    past logs from Log Analytics
#   az-logs.sh chat-stream-errors             hourly counts of chat-stream failure signals
#
# Why not a bare `az containerapp logs show --follow`: the logstream API answers
# "Got bad status from the logstream API: 500" when the app has no running replica
# (scaled to zero) or when it cannot pick one of several revisions/replicas by itself.
# `tail` therefore resolves the latest ready revision and a running replica first and
# passes both explicitly. A live stream only shows what happens while it is open, so
# investigating a past failure needs `query`, which reads the stored console logs
# (ContainerAppConsoleLogs_CL, the same table the BITB-056 error alerts use).
#
# Environment (all optional; GNU make exports command-line variables, so
# `make az-logs-backend-query HOURS=6 FILTER="Chat stream"` just works):
#   CA_RG    resource group                        (default: bible-app-rg)
#   HOURS    query window in hours, 1-720          (default: 24)
#   LEVEL    level regex: ERROR|WARNING|INFO|DEBUG|CRITICAL joined by '|' (default: ERROR|WARNING)
#   FILTER   substring a log line must contain     (default: none)
#   LIMIT    max rows, 1-10000                     (default: 200)
#   DAYS     window for chat-stream-errors, 1-30   (default: 7)
#   LA_WORKSPACE_ID  Log Analytics workspace (customer) ID; looked up in CA_RG if unset
set -euo pipefail

RG="${CA_RG:-bible-app-rg}"

die() {
	echo "Error: $*" >&2
	exit 1
}

usage() {
	sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//' >&2
	exit 2
}

# int_in_range <name> <value> <min> <max>
int_in_range() {
	if ! [[ "$2" =~ ^[0-9]+$ ]] || ((10#$2 < $3 || 10#$2 > $4)); then
		die "$1 must be an integer between $3 and $4 (got '$2')"
	fi
}

# KQL single-quoted string literal: escape backslashes, then quotes.
kql_str() {
	local s="${1//\\/\\\\}"
	printf "'%s'" "${s//\'/\\\'}"
}

workspace_id() {
	if [[ -n "${LA_WORKSPACE_ID:-}" ]]; then
		echo "$LA_WORKSPACE_ID"
		return
	fi
	local ws
	ws=$(az monitor log-analytics workspace list --resource-group "$RG" \
		--query "[0].customerId" --output tsv) || die "could not list Log Analytics workspaces in $RG (az login?)"
	[[ -n "$ws" ]] || die "no Log Analytics workspace found in $RG (set LA_WORKSPACE_ID)"
	echo "$ws"
}

run_query() {
	local ws
	ws=$(workspace_id) || exit 1 # die() inside $(...) only leaves the subshell
	az monitor log-analytics query --workspace "$ws" --analytics-query "$1" --output table
}

cmd_tail() {
	local app="${1:-}" kind="${2:-}"
	[[ -n "$app" ]] || usage
	case "$kind" in
	console | system) ;;
	*) die "log type must be console or system (got '$kind')" ;;
	esac
	local hint="Live streaming failed. For past logs use: make az-logs-${app#bible-app-}-query (see DEPLOYMENT.md)."

	if [[ "$kind" == system ]]; then
		# System logs are app-level (scaling, revision provisioning): no replica to pick.
		az containerapp logs show --name "$app" --resource-group "$RG" --type system --follow ||
			die "$hint"
		return
	fi

	local revision replica
	revision=$(az containerapp show --name "$app" --resource-group "$RG" \
		--query "properties.latestReadyRevisionName" --output tsv) ||
		die "could not read $app in $RG (az login? right subscription?)"
	[[ -n "$revision" ]] || die "$app has no ready revision"
	replica=$(az containerapp replica list --name "$app" --resource-group "$RG" \
		--revision "$revision" --query "[0].name" --output tsv) ||
		die "could not list replicas of $revision"
	if [[ -z "$replica" ]]; then
		die "revision $revision has no running replica (scaled to zero). Send a request to wake it, or read past logs with: make az-logs-${app#bible-app-}-query"
	fi
	echo "Streaming $app console logs from $revision / $replica (Ctrl+C to stop)..." >&2
	az containerapp logs show --name "$app" --resource-group "$RG" \
		--revision "$revision" --replica "$replica" --type console --follow ||
		die "$hint"
}

cmd_query() {
	local app="${1:-}"
	[[ -n "$app" ]] || usage
	local hours="${HOURS:-24}" limit="${LIMIT:-200}" level="${LEVEL:-ERROR|WARNING}" filter="${FILTER:-}"
	int_in_range HOURS "$hours" 1 720
	int_in_range LIMIT "$limit" 1 10000
	[[ "$level" =~ ^(DEBUG|INFO|WARNING|ERROR|CRITICAL)(\|(DEBUG|INFO|WARNING|ERROR|CRITICAL))*$ ]] ||
		die "LEVEL must be levels joined by '|', e.g. ERROR|WARNING (got '$level')"

	local kql
	kql="ContainerAppConsoleLogs_CL
| where TimeGenerated > ago(${hours}h)
| where ContainerAppName_s == $(kql_str "$app")
| where Log_s matches regex @'\\|\\s*(${level})\\s*\\|'"
	if [[ -n "$filter" ]]; then
		kql+="
| where Log_s contains $(kql_str "$filter")"
	fi
	kql+="
| project TimeGenerated, RevisionName_s, Log_s
| order by TimeGenerated desc
| take ${limit}"
	run_query "$kql"
}

cmd_chat_stream_errors() {
	local days="${DAYS:-7}"
	int_in_range DAYS "$days" 1 30
	# Signals that can end a chat turn without its final `completion` event, or degrade it
	# (BITB-320/321). Labels mirror deployment/azure-monitor/queries/backend-error-filter.kql.
	run_query "ContainerAppConsoleLogs_CL
| where TimeGenerated > ago(${days}d)
| where ContainerAppName_s == 'bible-app-backend'
| extend Signal = case(
    Log_s has 'Chat stream failed' or Log_s has 'Chat stream runtime error', 'chat_stream_unhandled',
    Log_s has 'all LLM models exhausted', 'llm_all_models_exhausted',
    Log_s has 'Client-side fallback to', 'llm_client_fallback',
    Log_s has 'Content safety violation in chat stream', 'content_safety_block',
    Log_s has 'Llama Guard API returned malformed response shape', 'llama_guard_malformed',
    Log_s has 'Primary Llama Guard model failed', 'llama_guard_primary_failed',
    Log_s has 'Chat stream client disconnected', 'client_disconnected',
    Log_s has 'Chat finalize requested', 'client_finalize',
    '')
| where Signal != ''
| summarize Count = count() by bin(TimeGenerated, 1h), Signal, RevisionName_s
| order by TimeGenerated desc, Signal asc"
}

case "${1:-}" in
tail) cmd_tail "${2:-}" "${3:-}" ;;
query) cmd_query "${2:-}" ;;
chat-stream-errors) cmd_chat_stream_errors ;;
*) usage ;;
esac
