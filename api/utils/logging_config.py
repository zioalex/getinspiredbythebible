"""
Logging configuration for the Bible Inspiration Chat API.

Provides structured logging with consistent formatting across all modules.
"""

import logging
import sys
from typing import Any

from config import settings


def setup_logging() -> None:
    """
    Configure application-wide logging.

    Sets up:
    - Console handler with formatted output
    - Appropriate log level from settings
    - Consistent format across all loggers
    """
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Set levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


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
