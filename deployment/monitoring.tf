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
