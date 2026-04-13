"""
OpenTelemetry tracer configuration for Vox Quieta API.

Provides a pre-configured tracer for database instrumentation.
The tracer automatically integrates with Azure Monitor when
APPLICATIONINSIGHTS_CONNECTION_STRING is set.
"""

from opentelemetry import trace

# Tracer for database/scripture operations.
# When configure_azure_monitor() has been called (in main.py), spans created
# by this tracer will be exported to Azure Application Insights.
# When no exporter is configured, the OTel API is a graceful no-op.
tracer = trace.get_tracer("bible_app.scripture")
