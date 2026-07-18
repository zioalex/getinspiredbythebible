# -----------------------------------------------------------------------------
# Production monitoring & alerting (native Azure baseline)
# -----------------------------------------------------------------------------
#
# This is the *backup* delivery channel for production alerts. The primary
# channel is Telegram via .github/workflows/prod-monitor.yml, which catches
# functional failures (e.g. in-band SSE error chunks the way the OpenRouter
# 401 incident manifested). This Azure-native baseline covers the case where
# GitHub Actions itself is degraded. BITB-056 also pushes this baseline to
# Telegram (via the Logic App bridge below) so the backup channel matches.
#
# All resources are gated on var.alert_email being non-empty; leave it empty
# in non-prod to skip the email action group and downstream alerts entirely.
#
# Resources defined here:
#   - azurerm_monitor_action_group.ops_email
#       Email action group (+ Telegram logic_app_receiver when telegram_chat_id set).
#   - azurerm_key_vault.alerts + azurerm_logic_app_workflow/_trigger/_action_custom.telegram_* (BITB-056)
#       Bridge that reposts the common alert schema to Telegram. The bot token lives in
#       Key Vault (set out-of-band by the deploy workflow) and is read at run time via the
#       Logic App's managed identity, so it never enters terraform state. Gated on
#       telegram_enabled (= alerts_enabled && telegram_chat_id != "").
#   - azurerm_monitor_metric_alert.backend_availability
#       Wires the existing azurerm_application_insights_standard_web_test
#       (defined in main.tf) to the action group. Without this, the web test
#       runs but never alerts.
#   - azurerm_monitor_metric_alert.backend_restarts
#       Fires when the backend container app reports >0 restarts in 15 min.
#   - azurerm_monitor_scheduled_query_rules_alert_v2.backend_errors (BITB-056)
#       ERROR-level backend log lines, categorised; shares backend-error-filter.kql
#       with the prod-monitor.yml log-scan job. Sev2 for hard-failure categories.
#   - azurerm_monitor_scheduled_query_rules_alert_v2.backend_error_rate_other (BITB-056)
#       Sev3 companion: 5+ uncategorised ERROR lines in 10 min.
#   - azurerm_monitor_metric_alert.db_cpu/db_memory/db_storage/db_connections_failed (BITB-056)
#       Postgres flexible-server resource saturation (the conc~32 threshold knee) + disk-full.
#   - azurerm_monitor_scheduled_query_rules_alert_v2.scripture_search_latency_p95 (BITB-056)
#       Semantic-search p95 > 2000ms — the user-facing signal of the DB saturation knee.
#   - azurerm_monitor_scheduled_query_rules_alert_v2.scripture_fetch_errors (BITB-041)
#       Fires when verse/chapter fetch failures (timeout/db_error/empty_text) occur.
#   - azurerm_monitor_scheduled_query_rules_alert_v2.scripture_fetch_latency_p95 (BITB-041)
#       Fires when p95 latency of verse/chapter DB reads exceeds 1000ms.
#   - azurerm_monitor_scheduled_query_rules_alert_v2.scripture_grounding_errors
#       Fires when scripture search / cited-verse resolution / grounding logs an
#       error. These code paths swallow exceptions (fail open to a verse-less
#       answer), so without this alert a broken search can run silently — exactly
#       how the "# nosec inside SQL" syntax-error regression went unnoticed.
#   - azurerm_monitor_scheduled_query_rules_alert_v2.verse_grounding_paraphrase_brackets (BITB-053)
#       Observation alert: bracketed unquoted-paraphrase appends
#       (chat.verse_grounding.paraphrase_detections, bracketed=true applied=true)
#       clustering inside parenthetical references. Buffered (>5 per 15-min bin)
#       and clustered (2 of 3 evaluations) so a single stray event never pages.
#       Cosmetic; dormant until grounding_paraphrases_mode is set to "append" per
#       docs/HOW-TO-ROLLOUT-PARAPHRASE-GROUNDING.md.
#   - azurerm_monitor_scheduled_query_rules_alert_v2.embedding_fallback_rate (BITB-057 Phase 2)
#       Fires when the embedding provider's circuit breaker records any retry,
#       timeout, or open-circuit event (providers/embedding_resilience.py). Chat
#       degrades to verse-less responses silently while this persists.
#   - azurerm_monitor_scheduled_query_rules_alert_v2.content_safety_fallback_rate (BITB-061)
#       Fires when any content-safety provider (Llama Guard, OpenAI Moderation, Azure)
#       degrades to the local keyword-only filter (utils/content_safety.py). The
#       keyword filter still blocks/allows correctly, but this is the only signal
#       that the ML-backed safety net is temporarily degraded for a crisis-sensitive
#       product.
#   - azurerm_monitor_scheduled_query_rules_alert_v2.llama_guard_primary_failure_rate
#       Sev3 companion to content_safety_fallback_rate: fires when the PRIMARY Llama
#       Guard model's failure rate stays >=90% (min 5 calls/bin, sustained across 2 of
#       3 evaluations) — i.e. stuck failing on most/all requests, not the ~49% baseline
#       it fails at under normal load (secondary recovers those; see BITB-061/070).
#       content_safety_fallback_rate stays silent in this case since it only fires when
#       BOTH models fail.

locals {
  alerts_enabled = var.alert_email != "" && var.enable_application_insights
  # BITB-056: the Azure-native action group also pushes to Telegram (so the backup
  # channel matches prod-monitor.yml) when a chat id is supplied. The bot token is
  # NOT a TF var — it lives in Key Vault (set out-of-band by the deploy workflow) and
  # is fetched by the Logic App at run time via managed identity, so it never enters
  # terraform state.
  telegram_enabled = local.alerts_enabled && var.telegram_chat_id != ""
}

resource "azurerm_monitor_action_group" "ops_email" {
  count               = local.alerts_enabled ? 1 : 0
  name                = "${local.name_prefix}-ops-email"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "ops"

  email_receiver {
    name                    = "ops-email"
    email_address           = var.alert_email
    use_common_alert_schema = true
  }

  # BITB-056: deliver the same alerts to Telegram via the Logic App bridge below.
  # Gated on telegram_enabled so apply still succeeds when the Telegram vars are unset
  # (email-only). use_common_alert_schema keeps the payload shape the Logic App parses.
  dynamic "logic_app_receiver" {
    for_each = local.telegram_enabled ? [1] : []
    content {
      name                    = "telegram"
      resource_id             = azurerm_logic_app_workflow.telegram_alert[0].id
      callback_url            = azurerm_logic_app_trigger_http_request.telegram_alert[0].callback_url
      use_common_alert_schema = true
    }
  }

  tags = local.tags
}

# -----------------------------------------------------------------------------
# Azure Monitor -> Telegram bridge (BITB-056)
# -----------------------------------------------------------------------------
# Action-group webhooks post the Azure common alert schema, which Telegram's
# sendMessage API cannot consume directly. This Consumption Logic App accepts the
# alert payload on an HTTP trigger and reposts a formatted message to Telegram, so
# the Azure-native baseline (the channel that exists for when GitHub Actions is
# degraded) lands in the same chat as prod-monitor.yml. Gated on telegram_enabled.
#
# Secret handling: the bot token is NEVER a Terraform value. It is written to the
# Key Vault below by the deploy workflow (`az keyvault secret set`, from the
# TELEGRAM_BOT_TOKEN repo secret) and the Logic App fetches it at run time using its
# system-assigned managed identity. Terraform state therefore contains no token —
# only the vault name and a managed-identity grant.

data "azurerm_client_config" "current" {}

# Vault that holds the Telegram bot token. The secret VALUE is set out-of-band by
# the deploy workflow, so it is not declared as an azurerm_key_vault_secret (that
# would put the value back into state).
resource "azurerm_key_vault" "alerts" {
  count                      = local.telegram_enabled ? 1 : 0
  name                       = "${local.name_prefix}-akv-${local.resource_suffix}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 7
  purge_protection_enabled   = false

  tags = local.tags
}

# Deployer (the Terraform/az service principal) may set/read the token secret so the
# workflow's `az keyvault secret set` step works. Standalone resource (not an inline
# access_policy block) so it doesn't conflict with telegram_logic_app below — the
# azurerm provider forbids mixing inline and standalone access policies on one vault.
resource "azurerm_key_vault_access_policy" "telegram_deployer" {
  count        = local.telegram_enabled ? 1 : 0
  key_vault_id = azurerm_key_vault.alerts[0].id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = ["Get", "List", "Set", "Delete", "Purge"]
}

resource "azurerm_logic_app_workflow" "telegram_alert" {
  count               = local.telegram_enabled ? 1 : 0
  name                = "${local.name_prefix}-telegram-alert"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  # System-assigned managed identity used to read the bot token from Key Vault.
  identity {
    type = "SystemAssigned"
  }

  tags = local.tags
}

# Grant the Logic App's managed identity read access to the token secret only.
resource "azurerm_key_vault_access_policy" "telegram_logic_app" {
  count        = local.telegram_enabled ? 1 : 0
  key_vault_id = azurerm_key_vault.alerts[0].id
  tenant_id    = azurerm_logic_app_workflow.telegram_alert[0].identity[0].tenant_id
  object_id    = azurerm_logic_app_workflow.telegram_alert[0].identity[0].principal_id

  secret_permissions = ["Get"]
}

# Let the Logic App's managed identity read query results from the workspace, so the
# Get_results action below can fetch the rows the alert matched (via the alert's
# linkToFilteredSearchResultsAPI, token audience https://api.loganalytics.io) and
# inline the sample + RequestIds into the Telegram message. Read-only, workspace-scoped.
#
# NOTE: creating a role assignment requires Microsoft.Authorization/roleAssignments/write
# at this scope, which the deploy SP's Contributor role does NOT include (Azure excludes
# it from Contributor by design). setup-github-spn.sh grants the deploy SP an extra
# narrow "User Access Administrator" role on this workspace for exactly this reason -
# see the "Service Principal" section in deployment/README.md. If you add another
# azurerm_role_assignment on a different resource, it needs the same extra grant on its
# scope or terraform apply will fail with AuthorizationFailed.
resource "azurerm_role_assignment" "telegram_logic_app_logs_reader" {
  count                = local.telegram_enabled ? 1 : 0
  scope                = azurerm_log_analytics_workspace.main.id
  role_definition_name = "Log Analytics Reader"
  principal_id         = azurerm_logic_app_workflow.telegram_alert[0].identity[0].principal_id
}

resource "azurerm_logic_app_trigger_http_request" "telegram_alert" {
  count        = local.telegram_enabled ? 1 : 0
  name         = "When_an_Azure_alert_fires"
  logic_app_id = azurerm_logic_app_workflow.telegram_alert[0].id

  # Permissive schema: the action group sends the common alert schema; we only read
  # a few fields from it, so accept any object rather than pinning the full schema.
  schema = jsonencode({
    type = "object"
  })
}

# Step 1: read the bot token from Key Vault using the Logic App's managed identity.
# Defined as a custom action because azurerm_logic_app_action_http cannot express
# ManagedServiceIdentity authentication. secureData hides the token from run history.
resource "azurerm_logic_app_action_custom" "telegram_get_token" {
  count        = local.telegram_enabled ? 1 : 0
  name         = "Get_token"
  logic_app_id = azurerm_logic_app_workflow.telegram_alert[0].id

  # The trigger and both actions each read-modify-write the same workflow definition;
  # serialize their creation so the azurerm provider doesn't race on parallel writes.
  depends_on = [azurerm_logic_app_trigger_http_request.telegram_alert]

  body = jsonencode({
    type = "Http"
    inputs = {
      method = "GET"
      uri    = "${azurerm_key_vault.alerts[0].vault_uri}secrets/telegram-bot-token?api-version=7.4"
      authentication = {
        type     = "ManagedServiceIdentity"
        audience = "https://vault.azure.net"
      }
    }
    runtimeConfiguration = {
      secureData = {
        properties = ["outputs"]
      }
    }
    runAfter = {}
  })
}

# Step 1b (parallel with Get_token): fetch the rows the alert matched so the
# message can inline the sample + RequestIds. Log-search alerts carry the result
# set as a re-runnable REST URL in the common alert schema
# (alertContext.condition.allOf[0].linkToFilteredSearchResultsAPI, an
# api.loganalytics.io query URL); we GET it with the Logic App's managed identity.
# Each log rule projects a single AlertSummary column, so the result is rows[0][0].
#
# Tolerant by design: metric alerts (and anything without that link) have no such
# URL, so this action fails/short-circuits — Send_to_Telegram's runAfter accepts
# Failed/Skipped and the message simply omits the sample line. Outputs are NOT
# marked secureData (unlike Get_token): the message reader needs body('Get_results').
#
# NOTE: if a future common-schema revision renames linkToFilteredSearchResultsAPI,
# switch this to POST https://api.loganalytics.io/v1/workspaces/{customerId}/query
# with the payload's searchQuery + window (both are in the schema).
resource "azurerm_logic_app_action_custom" "telegram_get_results" {
  count        = local.telegram_enabled ? 1 : 0
  name         = "Get_results"
  logic_app_id = azurerm_logic_app_workflow.telegram_alert[0].id

  # Serialize creation after Get_token (the trigger and each action read-modify-write
  # the same workflow definition); runtime order is independent and set by runAfter.
  depends_on = [azurerm_logic_app_action_custom.telegram_get_token]

  body = jsonencode({
    type = "Http"
    inputs = {
      method = "GET"
      uri    = "@{triggerBody()?['data']?['alertContext']?['condition']?['allOf'][0]?['linkToFilteredSearchResultsAPI']}"
      authentication = {
        type     = "ManagedServiceIdentity"
        audience = "https://api.loganalytics.io"
      }
    }
    # Runs at workflow start, in parallel with Get_token.
    runAfter = {}
  })
}

# Step 2: post to Telegram. The token is injected from the Get_token output at run
# time (@{body('Get_token')?['value']}) — it is never stored in the definition.
# Plain text (no parse_mode) so a stray '<' or '&' in a dynamic field can't make
# Telegram reject the message; coalesce guards fields absent for some alert types.
resource "azurerm_logic_app_action_custom" "telegram_send" {
  count        = local.telegram_enabled ? 1 : 0
  name         = "Send_to_Telegram"
  logic_app_id = azurerm_logic_app_workflow.telegram_alert[0].id

  # Serialize creation after Get_results (which chains off Get_token) to avoid
  # parallel workflow-definition writes.
  depends_on = [azurerm_logic_app_action_custom.telegram_get_results]

  body = jsonencode({
    type = "Http"
    inputs = {
      method  = "POST"
      uri     = "https://api.telegram.org/bot@{body('Get_token')?['value']}/sendMessage"
      headers = { "Content-Type" = "application/json" }
      body = {
        chat_id = var.telegram_chat_id
        # Plain text (no parse_mode). Two lines are appended to the base alert:
        #   1. the inline sample — but ONLY when the fetched result's first column is
        #      named "AlertSummary". Every log rule ends with `| project AlertSummary`
        #      (single column), so this is exact for them and empty for metric rules
        #      (whose first column is a count/measure), avoiding a stray bare number.
        #   2. a one-click "Details:" deep link (linkToFilteredSearchResultsUI).
        # Both degrade to '' when Get_results failed/was skipped or the field is absent.
        text = "@{concat('🚨 ', coalesce(triggerBody()?['data']?['essentials']?['monitorCondition'], 'Alert'), ' — ', coalesce(triggerBody()?['data']?['essentials']?['severity'], ''), ' ', coalesce(triggerBody()?['data']?['essentials']?['alertRule'], 'Azure Monitor alert'), decodeUriComponent('%0A'), coalesce(triggerBody()?['data']?['essentials']?['description'], ''), decodeUriComponent('%0A'), 'Fired: ', coalesce(triggerBody()?['data']?['essentials']?['firedDateTime'], ''), if(equals(coalesce(body('Get_results')?['tables']?[0]?['columns']?[0]?['name'], ''), 'AlertSummary'), concat(decodeUriComponent('%0A'), coalesce(body('Get_results')?['tables']?[0]?['rows']?[0]?[0], '')), ''), decodeUriComponent('%0A'), 'Details: ', coalesce(triggerBody()?['data']?['alertContext']?['condition']?['allOf'][0]?['linkToFilteredSearchResultsUI'], ''))}"
      }
    }
    runtimeConfiguration = {
      secureData = {
        properties = ["inputs"]
      }
    }
    # Wait for the token; tolerate any Get_results outcome so a missing/failed
    # results fetch never blocks the alert from reaching Telegram.
    runAfter = {
      Get_token   = ["Succeeded"]
      Get_results = ["Succeeded", "Failed", "Skipped"]
    }
  })
}

# Wire the existing standard web test to the action group so a region failing
# to reach /health/ready triggers an email.
resource "azurerm_monitor_metric_alert" "backend_availability" {
  count               = local.alerts_enabled ? 1 : 0
  name                = "${local.name_prefix}-availability-failed"
  resource_group_name = azurerm_resource_group.main.name
  scopes = [
    azurerm_application_insights_standard_web_test.backend_availability[0].id,
    azurerm_application_insights.main[0].id,
  ]
  description = "Backend availability test failing from one or more regions."
  severity    = 1
  frequency   = "PT1M"
  window_size = "PT5M"

  application_insights_web_test_location_availability_criteria {
    web_test_id           = azurerm_application_insights_standard_web_test.backend_availability[0].id
    component_id          = azurerm_application_insights.main[0].id
    failed_location_count = 2
  }

  action {
    action_group_id = azurerm_monitor_action_group.ops_email[0].id
  }

  tags = local.tags
}

# Wire the CORS-preflight web test (BITB-064) to the action group so a
# browser-only preflight failure (like the 2026-07-05 _IncludedRouter 500)
# pages via the always-on Azure-native path, independent of the GitHub cron
# cross-origin-smoke probe.
resource "azurerm_monitor_metric_alert" "backend_preflight_availability" {
  count               = local.alerts_enabled ? 1 : 0
  name                = "${local.name_prefix}-preflight-failed"
  resource_group_name = azurerm_resource_group.main.name
  scopes = [
    azurerm_application_insights_standard_web_test.backend_preflight[0].id,
    azurerm_application_insights.main[0].id,
  ]
  description = "Backend CORS-preflight (OPTIONS /api/v1/chat/stream) availability test failing from one or more regions — the browser-only failure signature of the _IncludedRouter/OTel incident."
  severity    = 1
  frequency   = "PT1M"
  window_size = "PT5M"

  application_insights_web_test_location_availability_criteria {
    web_test_id           = azurerm_application_insights_standard_web_test.backend_preflight[0].id
    component_id          = azurerm_application_insights.main[0].id
    failed_location_count = 2
  }

  action {
    action_group_id = azurerm_monitor_action_group.ops_email[0].id
  }

  tags = local.tags
}

# Backend container app restart alert. Restarts are normal during deploys but
# unexpected ones often signal OOM/crash-loop.
resource "azurerm_monitor_metric_alert" "backend_restarts" {
  count               = local.alerts_enabled ? 1 : 0
  name                = "${local.name_prefix}-backend-restarts"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_container_app.backend.id]
  description         = "Backend Container App reported one or more restarts in the last 15 minutes."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "microsoft.app/containerapps"
    metric_name      = "RestartCount"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 0
  }

  action {
    action_group_id = azurerm_monitor_action_group.ops_email[0].id
  }

  tags = local.tags
}

# Backend probe-failure alert.
#
# Container Apps logs readiness/liveness probe failures to ContainerAppSystemLogs_CL
# as ReplicaUnhealthy events. These never reach ContainerAppConsoleLogs_CL (so
# backend_errors can't see them) and do NOT increment RestartCount when the pod keeps
# failing readiness without being restarted (so backend_restarts can't see them either).
# That blind spot let a multi-week readiness incident — /health/ready timing out on slow
# upstream dependencies — run with no alert. This watches the platform probe signal
# directly. The query gates on a burst (> 10 in 15m) so single-replica blips during a
# deploy (a few "connection refused" at container start) do not page.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "backend_probe_failures" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-backend-probe-failures"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT5M"
  window_duration      = "PT15M"
  scopes               = [azurerm_log_analytics_workspace.main.id]
  severity             = 2
  description          = "The backend container failed its readiness/liveness probe (ReplicaUnhealthy) more than 10 times in the last 15 minutes. Usually /health/ready timing out on a slow dependency, or the container is unhealthy. These ContainerAppSystemLogs_CL events do not trigger RestartCount, so this is the only alert that covers them. The payload carries a sample probe-failure line."

  criteria {
    query                   = <<-KQL
      ContainerAppSystemLogs_CL
      | where ContainerAppName_s == "bible-app-backend"
      | where Reason_s == "ReplicaUnhealthy"
      | where Log_s has "probe failed"
      | summarize cnt = count(), Sample = any(Log_s)
      | where cnt > 10
      // Single AlertSummary column so the Telegram Logic App can read rows[0][0]
      // generically (see azurerm_logic_app_action_custom.telegram_get_results).
      | project AlertSummary = strcat('x', tostring(cnt), ' | ', substring(Sample, 0, 400))
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.ops_email[0].id]
  }

  tags = local.tags
}

# Backend error-log alert (BITB-056).
#
# Fires on ERROR-level backend log lines only. The error definition (the level
# filter + known-benign exclusion + RequestId/ErrorCategory extraction) lives in a
# single checked-in file shared with the prod-monitor.yml log-scan job so the two
# channels cannot drift; this rule just appends an aggregation tail. The previous
# version matched keyword substrings (traceback|internal server error|...) regardless
# of level, so it paged at Sev2 on handled/transient WARNINGs and multi-line stack
# dumps while carrying no sample/count/request-id to act on.
#
# This rule covers the hard-failure categories (everything except "other_error");
# uncategorised ERROR noise is handled at Sev3 by backend_error_rate_other below.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "backend_errors" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-backend-error-logs"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT5M"
  window_duration      = "PT10M"
  scopes               = [azurerm_log_analytics_workspace.main.id]
  severity             = 2
  description          = "Backend logged an actionable ERROR in the last 10 minutes. Category is one of: db_pool_timeout (DB connection-pool/server saturation), llm_all_models_down, chat_unhandled / chat_stream_unhandled (unhandled 5xx), verse_context_failed, scripture_search_failed, llm_provider_error. Per-category count, a sample log line and up to 5 RequestIds are inlined below, with a Details link to the full results."

  criteria {
    # Shared filter (ERROR-level + category extraction) + this rule's aggregation tail.
    query                   = <<-KQL
      ${file("${path.module}/azure-monitor/queries/backend-error-filter.kql")}
      | summarize cnt = count(), Sample = any(Log_s), RequestIds = make_set(RequestId, 5) by ErrorCategory
      | where ErrorCategory != "other_error"
      // Roll every matched category into one AlertSummary string (read as rows[0][0]
      // by the Telegram Logic App). Total>0 guards the empty-input case: a no-`by`
      // summarize over zero rows still emits one row, which would otherwise fire.
      | summarize AlertSummary = strcat_array(make_list(strcat('[', ErrorCategory, '] x', tostring(cnt), ' reqs=', strcat_array(RequestIds, ','), ' | ', substring(Sample, 0, 400))), '\n'), Total = sum(cnt)
      | where Total > 0
      | project AlertSummary
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.ops_email[0].id]
  }

  tags = local.tags
}

# Uncategorised ERROR-rate alert (BITB-056). Sev3 informational companion to
# backend_errors: surfaces a sustained spike of ERROR lines that don't match a known
# hard-failure category, without paging at Sev2 on a single blip. Threshold of 5 over
# 10 minutes is conservative; tune once a baseline is observed.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "backend_error_rate_other" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-backend-error-rate-other"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT5M"
  window_duration      = "PT10M"
  scopes               = [azurerm_log_analytics_workspace.main.id]
  severity             = 3
  description          = "5+ uncategorised backend ERROR lines (ErrorCategory=other_error) in the last 10 minutes. Informational: the sample and RequestIds are inlined below (Details link for the full results) — use them to decide whether this warrants a new explicit category in backend-error-filter.kql."

  criteria {
    query                   = <<-KQL
      ${file("${path.module}/azure-monitor/queries/backend-error-filter.kql")}
      | where ErrorCategory == "other_error"
      | summarize cnt = count(), Sample = any(Log_s), RequestIds = make_set(RequestId, 5)
      | where cnt >= 5
      // Single AlertSummary column for the Telegram Logic App (rows[0][0]). The
      // cnt>=5 guard above already drops the empty-input row, so no extra guard.
      | project AlertSummary = strcat('x', tostring(cnt), ' reqs=', strcat_array(RequestIds, ','), ' | ', substring(Sample, 0, 400))
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.ops_email[0].id]
  }

  tags = local.tags
}

# Verse/chapter fetch error-rate alert (BITB-041).
# Fires when scripture.fetch.errors custom metric records any failure
# (timeout / db_error / empty_text) in the last 10 minutes.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "scripture_fetch_errors" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-scripture-fetch-errors"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT5M"
  window_duration      = "PT10M"
  scopes               = [azurerm_application_insights.main[0].id]
  severity             = 2
  description          = "Verse/chapter fetch errors (timeout, DB failure, or placeholder data) in the last 10 minutes."

  criteria {
    query                   = <<-KQL
      customMetrics
      | where timestamp > ago(10m)
      | where name == "scripture.fetch.errors"
      | summarize total = sum(valueSum) by bin(timestamp, 5m)
      | where total > 0
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.ops_email[0].id]
  }

  tags = local.tags
}

# Scripture grounding / search failure alert.
# The chat scripture pipeline fails open: _search_scripture, _resolve_cited_verses
# and _apply_verse_grounding each catch exceptions and degrade to a verse-less
# answer (no 5xx). This rule surfaces those swallowed failures by matching the
# exact log signatures they emit, so a broken search/grounding path can no longer
# run silently. Runs every 5 minutes over the last 10 minutes of backend logs.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "scripture_grounding_errors" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-scripture-grounding-errors"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT5M"
  window_duration      = "PT10M"
  scopes               = [azurerm_log_analytics_workspace.main.id]
  severity             = 2
  description          = "Scripture search, cited-verse resolution, or verse grounding logged an error in the last 10 minutes (these paths fail open, so errors are otherwise invisible)."

  criteria {
    query                   = <<-KQL
      ContainerAppConsoleLogs_CL
      | where TimeGenerated > ago(10m)
      | where ContainerAppName_s == "${azurerm_container_app.backend.name}"
      | where Log_s matches regex "(?i)(scripture search failed|failed to resolve cited verse|verse grounding skipped|PostgresSyntaxError|InFailedSQLTransactionError|current transaction is aborted)"
      | extend RequestId = extract(@"\|\s*\[([^\]]*)\]\s*\|", 1, Log_s)
      | summarize cnt = count(), Sample = any(Log_s), RequestIds = make_set(RequestId, 5)
      | where cnt > 0
      // Single AlertSummary column for the Telegram Logic App (rows[0][0]); cnt>0
      // guards the empty-input row that a no-`by` summarize always emits.
      | project AlertSummary = strcat('x', tostring(cnt), ' reqs=', strcat_array(RequestIds, ','), ' | ', substring(Sample, 0, 400))
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.ops_email[0].id]
  }

  tags = local.tags
}

# Scripture pipeline error metric alert (BITB-055).
# Fires when any of the three fail-open exception handlers in the chat
# scripture pipeline (search / resolve / grounding) increments the
# scripture.pipeline.errors custom metric. Metric-based alerts are more
# reliable than the log-based scripture_grounding_errors rule above because
# they fire on the counter increment — not on a log keyword that may land on
# a different line from the | ERROR | level marker. Keep both as defence-in-depth.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "scripture_pipeline_errors" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-scripture-pipeline-errors"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT5M"
  window_duration      = "PT10M"
  scopes               = [azurerm_application_insights.main[0].id]
  severity             = 2
  description          = "A fail-open exception in the chat scripture pipeline (search/resolve/grounding) was caught and the response was silently degraded to verse-less. Emitted by scripture.pipeline.errors custom metric."

  criteria {
    query                   = <<-KQL
      customMetrics
      | where timestamp > ago(10m)
      | where name == "scripture.pipeline.errors"
      | summarize total = sum(valueSum) by bin(timestamp, 5m)
      | where total > 0
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.ops_email[0].id]
  }

  tags = local.tags
}

# Verseless response SLI alert (BITB-055).
# Fires when a meaningful number of chat requests with include_search=True
# are served with zero DB context verses AND zero resolved citations over 15
# minutes — the exact silent-degradation signature of a broken retrieval path.
# Threshold of 10 is conservative; tune down once a baseline is observed.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "chat_verseless_responses" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-chat-verseless-responses"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT5M"
  window_duration      = "PT15M"
  scopes               = [azurerm_application_insights.main[0].id]
  severity             = 2
  description          = "More than 10 chat responses served with zero DB context verses AND zero resolved citations in the last 15 minutes (chat.responses.verseless metric). This is the silent-degradation signature of a broken scripture retrieval path."

  criteria {
    query                   = <<-KQL
      customMetrics
      | where timestamp > ago(15m)
      | where name == "chat.responses.verseless"
      | summarize total = sum(valueSum) by bin(timestamp, 5m)
      | where total > 10
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 3
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.ops_email[0].id]
  }

  tags = local.tags
}

# Verse/chapter fetch p95 latency alert (BITB-041).
# Fires when p95 of db.query.duration_ms for verse/chapter ops exceeds 1000ms.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "scripture_fetch_latency_p95" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-scripture-fetch-latency-p95"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT5M"
  window_duration      = "PT15M"
  scopes               = [azurerm_application_insights.main[0].id]
  severity             = 3
  description          = "p95 latency of verse/chapter DB reads exceeded 1000ms over the last 15 minutes."

  criteria {
    query                   = <<-KQL
      customMetrics
      | where timestamp > ago(15m)
      | where name == "db.query.duration_ms"
      | extend op = tostring(customDimensions["operation"])
      | where op in ("get_verse", "get_chapter")
      | summarize p95 = percentile(value, 95) by bin(timestamp, 5m)
      | where p95 > 1000
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.ops_email[0].id]
  }

  tags = local.tags
}

# -----------------------------------------------------------------------------
# Database saturation / threshold-failure alerts (BITB-056)
# -----------------------------------------------------------------------------
# A concurrency load test of /api/v1/scripture/search showed a clean latency knee
# at concurrency ~32 (p95 4-8x baseline, ~0% errors) on the 2-vCore burstable
# B_Standard_B2s: pgvector HNSW search is CPU-bound, so DB CPU is the wall and the
# connection pool (size 10 + overflow 10) adds queue-wait above it. Previously NONE
# of the DB server's own metrics were alerted. These rules add the *leading* signals
# so the threshold is visible before users see errors. (Root-cause hardening — storage
# auto-grow, DB tier, pool retune — is tracked in main.tf and the BITB-056 story.)

# Primary leading signal: CPU is the wall for the CPU-bound HNSW search workload.
resource "azurerm_monitor_metric_alert" "db_cpu" {
  count               = local.alerts_enabled ? 1 : 0
  name                = "${local.name_prefix}-db-cpu-high"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_postgresql_flexible_server.main.id]
  description         = "PostgreSQL CPU averaged >85% over 15 minutes — the leading indicator of the CPU-bound search saturation knee (measured at concurrency ~32). Sustained high CPU degrades search/chat latency before errors appear; consider a tier bump."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.DBforPostgreSQL/flexibleServers"
    metric_name      = "cpu_percent"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 85
  }

  action {
    action_group_id = azurerm_monitor_action_group.ops_email[0].id
  }

  tags = local.tags
}

resource "azurerm_monitor_metric_alert" "db_memory" {
  count               = local.alerts_enabled ? 1 : 0
  name                = "${local.name_prefix}-db-memory-high"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_postgresql_flexible_server.main.id]
  description         = "PostgreSQL memory averaged >90% over 15 minutes. On a 4GB burstable this risks cache thrash (HNSW indexes spilling out of shared_buffers) and OOM."
  severity            = 3
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.DBforPostgreSQL/flexibleServers"
    metric_name      = "memory_percent"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 90
  }

  action {
    action_group_id = azurerm_monitor_action_group.ops_email[0].id
  }

  tags = local.tags
}

# Disk-full is a hard write-failure cliff. auto_grow is being enabled (main.tf), but
# keep this as a backstop in case growth lags a fast fill.
resource "azurerm_monitor_metric_alert" "db_storage" {
  count               = local.alerts_enabled ? 1 : 0
  name                = "${local.name_prefix}-db-storage-high"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_postgresql_flexible_server.main.id]
  description         = "PostgreSQL storage averaged >85% over 30 minutes. Past full, writes fail and the server can go read-only. auto_grow should absorb this; investigate if it is climbing despite auto-grow."
  severity            = 2
  frequency           = "PT15M"
  window_size         = "PT30M"

  criteria {
    metric_namespace = "Microsoft.DBforPostgreSQL/flexibleServers"
    metric_name      = "storage_percent"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 85
  }

  action {
    action_group_id = azurerm_monitor_action_group.ops_email[0].id
  }

  tags = local.tags
}

# The hard form of the threshold cliff: the server rejecting connections.
resource "azurerm_monitor_metric_alert" "db_connections_failed" {
  count               = local.alerts_enabled ? 1 : 0
  name                = "${local.name_prefix}-db-connections-failed"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_postgresql_flexible_server.main.id]
  description         = "PostgreSQL rejected one or more connections in the last 15 minutes (connections_failed > 0). This is the hard threshold breach — clients could not get a DB connection."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.DBforPostgreSQL/flexibleServers"
    metric_name      = "connections_failed"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 0
  }

  action {
    action_group_id = azurerm_monitor_action_group.ops_email[0].id
  }

  tags = local.tags
}

# Direct user-facing signal of the measured knee: semantic-search p95. The load test
# baseline p95 was ~0.5s and the degraded knee at concurrency ~32 was ~1.9-2.1s, so a
# sustained p95 > 2000ms means we are at/over the saturation threshold. Uses the
# existing db.search.duration_ms histogram (api/scripture/repository.py) — no app change.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "scripture_search_latency_p95" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-scripture-search-latency-p95"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT5M"
  window_duration      = "PT15M"
  scopes               = [azurerm_application_insights.main[0].id]
  severity             = 2
  description          = "p95 of pgvector semantic search (db.search.duration_ms) exceeded 2000ms over the last 15 minutes — the search saturation knee measured at concurrency ~32. Indicates the DB is CPU-bound under load; check the db-cpu-high alert and consider a tier bump / pool retune."

  criteria {
    query                   = <<-KQL
      customMetrics
      | where timestamp > ago(15m)
      | where name == "db.search.duration_ms"
      | summarize p95 = percentile(value, 95) by bin(timestamp, 5m)
      | where p95 > 2000
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.ops_email[0].id]
  }

  tags = local.tags
}

# Unquoted-paraphrase nested-parens observation alert (BITB-053).
# In "append" mode, pass 2 of verse grounding appends canonical verse text right
# after a reference. When the reference is parenthesised — e.g. "(Isaia 41:10)" —
# the append lands before the closing bracket and nests:
# (Isaia 41:10 ("Non temere…")). This is cosmetic (offsets are safe), so rather
# than re-engineer the insertion point blindly we measure it via the
# chat.verse_grounding.paraphrase_detections counter (bracketed + applied
# dimensions). NOTE: grounding_paraphrases_mode ships as "detect" (count only,
# no text edits — applied=false), so this alert stays dormant until the mode is
# switched to "append" per docs/HOW-TO-ROLLOUT-PARAPHRASE-GROUNDING.md — at
# which point this rule is the guardrail that tells us if the edge is real.
#
# Buffer + clustering (deliberately not a hair-trigger on a single event):
#   - buffer: a 15-minute bin must accrue > 5 bracketed appends to count as a
#     breach, so one-off coincidences are ignored.
#   - clustering: the breach must recur in at least 2 of the last 3 fifteen-minute
#     evaluations before paging, so a lone noisy bin does not alert.
# Severity 3. Retune the bin threshold / failing-period ratio once a baseline
# exists, or remove the rule if the edge proves negligible.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "verse_grounding_paraphrase_brackets" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-verse-grounding-paraphrase-brackets"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT15M"
  window_duration      = "PT1H"
  scopes               = [azurerm_application_insights.main[0].id]
  severity             = 3
  description          = "BITB-053 unquoted-paraphrase appends are clustering inside parenthetical references (nested-parens artifact): >5 bracketed applied appends per 15-min bin, sustained across 2 of the last 3 evaluations. Cosmetic; observation alert active only while grounding_paraphrases_mode is 'append'."

  criteria {
    query                   = <<-KQL
      customMetrics
      | where timestamp > ago(1h)
      | where name == "chat.verse_grounding.paraphrase_detections"
      | extend bracketed = tostring(customDimensions["bracketed"])
      | extend applied = tostring(customDimensions["applied"])
      | where bracketed == "true" and applied == "true"
      | summarize total = sum(valueSum) by bin(timestamp, 15m)
      | where total > 5
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 2
      number_of_evaluation_periods             = 3
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.ops_email[0].id]
  }

  tags = local.tags
}

# Embedding provider resilience alert (BITB-057 Phase 2).
# Fires when the embedding.fallback_total custom metric records any retry,
# timeout, or circuit-open event (providers/embedding_resilience.py) in the
# last 10 minutes. A sustained rate here means the embedding provider is
# degraded/down — chat requests degrade to verse-less responses per the
# EmbeddingCircuitOpenError handling in chat/service.py, which is otherwise
# silent (no 5xx), so this metric is the signal.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "embedding_fallback_rate" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-embedding-fallback-rate"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT5M"
  window_duration      = "PT10M"
  scopes               = [azurerm_application_insights.main[0].id]
  severity             = 2
  description          = "Embedding provider retries, timeouts, or circuit-open events (embedding.fallback_total metric) in the last 10 minutes. Chat requests are degrading to verse-less responses while this persists — see providers/embedding_resilience.py."

  criteria {
    query                   = <<-KQL
      customMetrics
      | where timestamp > ago(10m)
      | where name == "embedding.fallback_total"
      | summarize total = sum(valueSum) by bin(timestamp, 5m)
      | where total > 0
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.ops_email[0].id]
  }

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Backend catch-all error alerts (BITB-065).
#
# Before this, no alert keyed on backend HTTP 5xx or unhandled exceptions —
# the existing rules watch DB metrics, custom counters, and specific app ERROR
# log strings, but never the App Insights requests/exceptions tables or a
# generic 500. The 2026-07-05 _IncludedRouter incident (HTTP 500 on every CORS
# preflight) fell straight through that net. These three rules are the
# catch-all layer.
#
# IMPORTANT nuance from that incident: the crash was inside the OpenTelemetry
# ASGI middleware, in default_span_details(), BEFORE the request span is
# started — so App Insights recorded NO requests row for it. A requests-table
# 5xx alert therefore cannot see that specific class; the reliable signal is
# the uvicorn "Exception in ASGI application" console line (backend_asgi_exceptions
# below). All three are kept as defence-in-depth for the broader 5xx surface.
# ---------------------------------------------------------------------------

# HTTP 5xx rate (App Insights requests table). Catches any endpoint/method the
# app layer answers with a 5xx (or success == false). KQL mirrors the workbook
# "Failed Requests" tile. Threshold is conservative (a handful in 10m) to avoid
# single-blip noise; tune once a baseline is observed. Severity 1: a 5xx spike
# is a user-facing outage.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "backend_5xx_rate" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-backend-5xx-rate"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT5M"
  window_duration      = "PT10M"
  scopes               = [azurerm_application_insights.main[0].id]
  severity             = 1
  description          = "Backend returned HTTP 5xx (or success == false) on 3+ requests in the last 10 minutes. Broad catch-all for server-side failures not covered by the specific metric/log alerts. NOTE: a crash inside the OTel ASGI middleware records no requests row — see backend_asgi_exceptions for that class."

  criteria {
    query                   = <<-KQL
      requests
      | where timestamp > ago(10m)
      | where success == false or toint(resultCode) >= 500
      | summarize total = count() by bin(timestamp, 5m)
      | where total >= 3
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.ops_email[0].id]
  }

  tags = local.tags
}

# Unhandled exceptions (App Insights exceptions table). Catches unhandled server
# exceptions OTel records (e.g. a regression in a route handler surfaced by
# ServerErrorMiddleware). KQL source: workbook "Exception Summary" tile.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "backend_unhandled_exceptions" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-backend-unhandled-exceptions"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT5M"
  window_duration      = "PT10M"
  scopes               = [azurerm_application_insights.main[0].id]
  severity             = 2
  description          = "3+ unhandled server exceptions recorded in App Insights in the last 10 minutes (exceptions table). Surfaces regressions that raise past route handlers. Threshold is conservative; tune once a baseline is observed."

  criteria {
    query                   = <<-KQL
      exceptions
      | where timestamp > ago(10m)
      | summarize total = count() by bin(timestamp, 5m)
      | where total >= 3
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.ops_email[0].id]
  }

  tags = local.tags
}

# ASGI-layer exceptions (backend console logs). The in-telemetry catch for the
# _IncludedRouter class: a crash above the app (OTel/CORS middleware) never
# reaches a bible_app logger, so it produces no "| ERROR |"-formatted line (the
# backend_errors filter misses it) and no requests row (backend_5xx_rate misses
# it). It DOES produce a uvicorn.error "Exception in ASGI application" console
# line — which is what this rule keys on. Severity 1: any ASGI exception is a
# request the server could not handle.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "backend_asgi_exceptions" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-backend-asgi-exceptions"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT5M"
  window_duration      = "PT10M"
  scopes               = [azurerm_log_analytics_workspace.main.id]
  severity             = 1
  description          = "An ASGI-layer exception ('Exception in ASGI application' from uvicorn, or a bare Traceback) appeared in backend logs in the last 10 minutes. This is the signature of a crash ABOVE the app — OTel/CORS middleware — that the | ERROR | log filter and the requests-table alert both miss. The 2026-07-05 _IncludedRouter 500 on CORS preflight emitted exactly this line."

  criteria {
    query                   = <<-KQL
      ContainerAppConsoleLogs_CL
      | where TimeGenerated > ago(10m)
      | where ContainerAppName_s == "${azurerm_container_app.backend.name}"
      | where Log_s has "Exception in ASGI application"
          or Log_s contains "Traceback (most recent call last)"
      | summarize cnt = count(), Sample = any(Log_s)
      | where cnt > 0
      // Single AlertSummary column for the Telegram Logic App (rows[0][0]); cnt>0
      // guards the empty-input row. 600 chars of the traceback inline; the full
      // text is one click away via the "Details:" link the Logic App appends.
      | project AlertSummary = strcat('x', tostring(cnt), ' | ', substring(Sample, 0, 600))
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.ops_email[0].id]
  }

  tags = local.tags
}

# Frontend client-error spike (BITB-066). The web frontend reports JS/render/API
# errors to /api/v1/client-errors, which emits the client.errors_total metric.
# A spike means many real browsers are failing at once (e.g. a browser-only
# outage the backend request path can't see) — the client-side complement to the
# backend catch-all alerts. Threshold is deliberately a spike, not per-error, so
# individual users' transient network blips don't page; tune once a baseline
# exists.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "frontend_client_errors" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-frontend-client-errors"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT5M"
  window_duration      = "PT10M"
  scopes               = [azurerm_application_insights.main[0].id]
  severity             = 2
  description          = "More than 20 client-side error reports (client.errors_total) received in the last 10 minutes — a spike of browser-side JS/render/API failures, e.g. a browser-only outage. Emitted by the frontend error reporter (BITB-066)."

  criteria {
    query                   = <<-KQL
      customMetrics
      | where timestamp > ago(10m)
      | where name == "client.errors_total"
      | summarize total = sum(valueSum) by bin(timestamp, 5m)
      | where total > 20
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.ops_email[0].id]
  }

  tags = local.tags
}

# Content safety fallback alert (BITB-061).
# Fires when the content_safety.fallback_total custom metric records any
# provider-unavailable or provider-failure event (utils/content_safety.py).
# Every fallback branch already degrades safely to the local keyword-only
# filter (never to allow-all), but for a pastoral-care product screening
# self-harm/violence content, a degraded ML safety net is itself an
# operator-actionable signal, not just a resilience detail.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "content_safety_fallback_rate" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-content-safety-fallback-rate"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT5M"
  window_duration      = "PT10M"
  scopes               = [azurerm_application_insights.main[0].id]
  severity             = 2
  description          = "Content safety provider (Llama Guard / OpenAI Moderation / Azure) degraded to keyword-only fallback (content_safety.fallback_total metric) in the last 10 minutes — see utils/content_safety.py."

  criteria {
    query                   = <<-KQL
      customMetrics
      | where timestamp > ago(10m)
      | where name == "content_safety.fallback_total"
      | summarize total = sum(valueSum) by bin(timestamp, 5m)
      | where total > 0
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.ops_email[0].id]
  }

  tags = local.tags
}

# Lower severity than content_safety_fallback_rate above: this fires when the
# PRIMARY Llama Guard model (meta-llama/llama-guard-4-12b) is stuck failing on
# most/all requests while the secondary model keeps recovering them — the
# request is still ML-classified correctly, just at higher latency/cost, so
# it's not user-impacting on its own. Without this alert, that state is
# completely invisible: content_safety_fallback_rate only fires when BOTH
# models fail (the request degrades to keyword-only).
#
# IMPORTANT: the primary model fails on ~49% of calls under normal production
# load — a known OpenRouter routing quirk (finish_reason=stop, content: null
# on some routes; see the docstring in providers/llama_guard.py), always
# recovered by the secondary (0 total end-to-end failures in the BITB-061
# 100-sample benchmark; see docs/BACKLOG_STORIES/BITB-070-reevaluate-hybrid-
# content-safety-mode.md). That ~49% is accepted, steady-state noise, not an
# incident — so this rule alerts on a sustained high FAILURE RATE (computed
# from the same metric's success/failed outcomes, both emitted by
# llama_guard_primary_result_counter) well above that baseline, clustered
# across evaluations, rather than on any single failure.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "llama_guard_primary_failure_rate" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-llama-guard-primary-failure-rate"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT15M"
  window_duration      = "PT1H"
  scopes               = [azurerm_application_insights.main[0].id]
  severity             = 3
  description          = "Primary Llama Guard model (llama_guard.primary_result_total) failure rate stayed >=90% over a 15-min bin (min 5 calls), sustained across 2 of the last 3 evaluations — i.e. the primary is stuck failing on most/all requests, not the expected ~49% baseline (see BITB-061/070). The secondary model is still recovering these end-to-end, but the pipeline is running on a single remaining ML classifier for a sustained period. See providers/llama_guard.py."

  criteria {
    query                   = <<-KQL
      customMetrics
      | where timestamp > ago(1h)
      | where name == "llama_guard.primary_result_total"
      | extend outcome = tostring(customDimensions["outcome"])
      | summarize failed = sumif(valueSum, outcome == "failed"), total = sum(valueSum) by bin(timestamp, 15m)
      | where total >= 5
      | extend failure_rate = todouble(failed) / todouble(total)
      | where failure_rate >= 0.9
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 2
      number_of_evaluation_periods             = 3
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.ops_email[0].id]
  }

  tags = local.tags
}
