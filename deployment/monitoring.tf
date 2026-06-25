# -----------------------------------------------------------------------------
# Production monitoring & alerting (native Azure baseline)
# -----------------------------------------------------------------------------
#
# This is the *backup* delivery channel for production alerts. The primary
# channel is Telegram via .github/workflows/prod-monitor.yml, which catches
# functional failures (e.g. in-band SSE error chunks the way the OpenRouter
# 401 incident manifested). This Azure-native baseline covers the case where
# GitHub Actions itself is degraded.
#
# All resources are gated on var.alert_email being non-empty; leave it empty
# in non-prod to skip the email action group and downstream alerts entirely.
#
# Resources defined here:
#   - azurerm_monitor_action_group.ops_email
#       Email-only action group, target: var.alert_email.
#   - azurerm_monitor_metric_alert.backend_availability
#       Wires the existing azurerm_application_insights_standard_web_test
#       (defined in main.tf) to the action group. Without this, the web test
#       runs but never alerts.
#   - azurerm_monitor_metric_alert.backend_restarts
#       Fires when the backend container app reports >0 restarts in 15 min.
#   - azurerm_monitor_scheduled_query_rules_alert_v2.backend_errors
#       Same KQL the prod-monitor.yml log-scan job runs; alerts via email if
#       any backend error log line is seen in the last 10 minutes.
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
#       Observation alert: fires when an unquoted-paraphrase canonical-text append
#       lands before a closing bracket (chat.verse_grounding.paraphrase_appends with
#       bracketed=true), i.e. it nested inside a parenthetical reference. Cosmetic
#       only; exists to measure whether the edge actually occurs before any fix.

locals {
  alerts_enabled = var.alert_email != "" && var.enable_application_insights
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

  tags = local.tags
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

# Backend error-log alert (mirror of prod-monitor.yml's log-scan job).
# Runs every 5 minutes; fires if any error-shaped log line was emitted in the
# last 10 minutes.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "backend_errors" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-backend-error-logs"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT5M"
  window_duration      = "PT10M"
  scopes               = [azurerm_log_analytics_workspace.main.id]
  severity             = 2
  description          = "Backend logs contain error-shaped messages (OpenRouter, LLM, traceback) in the last 10 minutes."

  criteria {
    query                   = <<-KQL
      ContainerAppConsoleLogs_CL
      | where TimeGenerated > ago(10m)
      | where ContainerAppName_s == "${azurerm_container_app.backend.name}"
      | where Log_s matches regex "(?i)(openrouter error|llm streaming error|anthropic error|internal server error|traceback)"
      | summarize cnt = count() by bin(TimeGenerated, 5m)
      | where cnt > 0
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
      | summarize cnt = count() by bin(TimeGenerated, 5m)
      | where cnt > 0
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

# Unquoted-paraphrase nested-parens observation alert (BITB-053).
# Pass 2 of verse grounding appends canonical verse text right after a reference.
# When the reference is parenthesised — e.g. "(Isaia 41:10)" — the append lands
# before the closing bracket and nests: (Isaia 41:10 ("Non temere…")). This is
# cosmetic (offsets are safe), so rather than re-engineer the insertion point
# blindly we measure it: chat.verse_grounding.paraphrase_appends carries a
# `bracketed` dimension, and this rule fires on the first bracketed append in an
# hour. Severity 3. Once a baseline is known, retune the threshold or remove it.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "verse_grounding_paraphrase_brackets" {
  count                = local.alerts_enabled ? 1 : 0
  name                 = "${local.name_prefix}-verse-grounding-paraphrase-brackets"
  resource_group_name  = azurerm_resource_group.main.name
  location             = azurerm_resource_group.main.location
  evaluation_frequency = "PT15M"
  window_duration      = "PT1H"
  scopes               = [azurerm_application_insights.main[0].id]
  severity             = 3
  description          = "A BITB-053 unquoted-paraphrase append landed before a closing bracket (nested-parens artifact) in the last hour. Cosmetic; this is an observation alert to confirm whether the edge occurs in production."

  criteria {
    query                   = <<-KQL
      customMetrics
      | where timestamp > ago(1h)
      | where name == "chat.verse_grounding.paraphrase_appends"
      | extend bracketed = tostring(customDimensions["bracketed"])
      | where bracketed == "true"
      | summarize total = sum(valueSum) by bin(timestamp, 15m)
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
