"""
Logging configuration for the Vox Quieta API.

Provides structured logging with consistent formatting across all modules.

OpenTelemetry integration:
    configure_azure_monitor(logger_name="bible_app") attaches an OpenTelemetry
    LoggingHandler to the "bible_app" logger.  All application loggers that live
    under this namespace (e.g. "bible_app.chat", "bible_app.routes") will
    automatically export their records to Application Insights.
"""

import logging
import sys
from typing import Any

from config import settings
from middleware.context import REQUEST_ID_CTX_VAR

# All application loggers should be children of this namespace so that the
# OpenTelemetry handler (attached by configure_azure_monitor) captures them.
APP_LOGGER_NAME = "bible_app"


class CorrelationIDFilter(logging.Filter):
    """
    Logging filter that injects the current request ID into every log record.

    The request ID is retrieved from the REQUEST_ID_CTX_VAR context variable,
    which is set by the CorrelationIDMiddleware for each request.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add request_id attribute to the log record.

        Args:
            record: The log record to modify

        Returns:
            True to allow the record to be logged
        """
        record.request_id = REQUEST_ID_CTX_VAR.get("")  # type: ignore[attr-defined]
        return True


def setup_logging() -> None:
    """
    Configure application-wide logging.

    Sets up:
    - Console handler with formatted output on the root logger
    - Application logger (bible_app) at the configured level
    - Consistent format across all loggers
    """
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Create formatter with request_id field
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | [%(request_id)s] | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates, but preserve any
    # OpenTelemetry handlers that were already attached.
    for handler in root_logger.handlers[:]:
        if "opentelemetry" in type(handler).__module__:
            continue
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(CorrelationIDFilter())
    root_logger.addHandler(console_handler)

    # Ensure the application logger inherits from root and is at the right level.
    # configure_azure_monitor(logger_name="bible_app") will later attach an
    # OpenTelemetry handler here, exporting logs to Application Insights.
    app_logger = logging.getLogger(APP_LOGGER_NAME)
    app_logger.setLevel(log_level)

    # Set levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    # Azure Monitor SDK HTTP logging is extremely chatty at INFO level
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
    logging.getLogger("azure.monitor.opentelemetry.exporter").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module under the app namespace.

    Returns a logger named ``bible_app.<name>`` so that records are
    captured by both the console handler and the OpenTelemetry handler
    (when Application Insights is enabled).

    Args:
        name: Module name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(f"{APP_LOGGER_NAME}.{name}")


class LogContext:
    """Context manager for structured logging with extra fields."""

    def __init__(self, logger: logging.Logger, **context: Any):
        self.logger = logger
        self.context = context

    def info(self, message: str, **extra: Any) -> None:
        self._log(logging.INFO, message, **extra)

    def error(self, message: str, **extra: Any) -> None:
        self._log(logging.ERROR, message, **extra)

    def warning(self, message: str, **extra: Any) -> None:
        self._log(logging.WARNING, message, **extra)

    def debug(self, message: str, **extra: Any) -> None:
        self._log(logging.DEBUG, message, **extra)

    def _log(self, level: int, message: str, **extra: Any) -> None:
        all_context = {**self.context, **extra}
        context_str = " | ".join(f"{k}={v}" for k, v in all_context.items())
        full_message = f"{message} | {context_str}" if context_str else message
        self.logger.log(level, full_message)
