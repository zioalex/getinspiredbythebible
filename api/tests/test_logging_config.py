"""
Tests for logging configuration and Application Insights integration.

Verifies:
- get_logger() returns loggers under the bible_app namespace
- setup_logging() preserves OpenTelemetry handlers
- All application modules use get_logger (not logging.getLogger directly)
- APP_LOGGER_NAME matches what main.py passes to configure_azure_monitor
- Telemetry flush is called on shutdown when App Insights is enabled
"""

import ast
import logging
import sys
from pathlib import Path

import pytest

# Ensure the api directory is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.logging_config import APP_LOGGER_NAME, get_logger, setup_logging

# ---------------------------------------------------------------------------
# get_logger namespace tests
# ---------------------------------------------------------------------------


class TestGetLogger:
    """Verify get_logger returns loggers under the bible_app namespace."""

    def test_returns_logger_under_app_namespace(self):
        logger = get_logger("some_module")
        assert logger.name == f"{APP_LOGGER_NAME}.some_module"

    def test_nested_module_name(self):
        logger = get_logger("routes.chat")
        assert logger.name == f"{APP_LOGGER_NAME}.routes.chat"

    def test_dunder_name(self):
        """Typical usage: get_logger(__name__) from a module."""
        logger = get_logger("chat.service")
        assert logger.name == f"{APP_LOGGER_NAME}.chat.service"

    def test_logger_is_child_of_app_logger(self):
        """Child loggers propagate records to their parent, so an OTel
        handler on bible_app will capture records from bible_app.routes.*."""
        parent = logging.getLogger(APP_LOGGER_NAME)
        child = get_logger("routes.chat")
        assert child.parent is parent or child.parent.name == APP_LOGGER_NAME

    def test_app_logger_name_is_bible_app(self):
        """Guard against accidental renames that would break the
        configure_azure_monitor(logger_name=...) call in main.py."""
        assert APP_LOGGER_NAME == "bible_app"


# ---------------------------------------------------------------------------
# setup_logging tests
# ---------------------------------------------------------------------------


class TestSetupLogging:
    """Verify setup_logging configures handlers correctly."""

    def test_adds_console_handler_to_root(self):
        setup_logging()
        root = logging.getLogger()
        stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) >= 1

    def test_sets_app_logger_level(self):
        setup_logging()
        app_logger = logging.getLogger(APP_LOGGER_NAME)
        assert app_logger.level != logging.NOTSET

    def test_preserves_opentelemetry_handlers(self):
        """If an OpenTelemetry handler is already on the root logger,
        setup_logging() must not remove it."""
        root = logging.getLogger()

        # Create a fake OTel handler whose module contains 'opentelemetry'
        fake_otel_handler = logging.Handler()
        fake_otel_handler.__class__ = type(
            "LoggingHandler",
            (logging.Handler,),
            {"__module__": "opentelemetry.sdk._logs"},
        )
        root.addHandler(fake_otel_handler)

        setup_logging()

        # The fake OTel handler should still be present
        assert fake_otel_handler in root.handlers

        # Clean up
        root.removeHandler(fake_otel_handler)

    def test_removes_non_otel_duplicate_handlers(self):
        """setup_logging() should remove previous non-OTel handlers to
        avoid duplicates on repeated calls."""
        root = logging.getLogger()
        extra = logging.StreamHandler()
        root.addHandler(extra)

        handler_count_before = len(root.handlers)
        setup_logging()
        # After setup, we should have fewer or equal handlers (the extra
        # one removed, one console re-added)
        assert len(root.handlers) <= handler_count_before

    def test_noisy_libraries_suppressed(self):
        """Chatty libraries should be set to WARNING or higher."""
        setup_logging()
        for name in ["httpx", "httpcore", "asyncio", "uvicorn.access"]:
            assert logging.getLogger(name).level >= logging.WARNING


# ---------------------------------------------------------------------------
# Module compliance: all app modules must use get_logger, not logging.getLogger
# ---------------------------------------------------------------------------


# Application modules that should use get_logger (relative to api/)
_APP_MODULES = [
    "main.py",
    "chat/service.py",
    "routes/chat.py",
    "routes/church.py",
    "routes/feedback.py",
    "routes/health.py",
    "providers/openrouter.py",
    "utils/email_service.py",
    "utils/local_only.py",
    "utils/security.py",
]


class TestModuleCompliance:
    """Ensure all app modules use get_logger instead of logging.getLogger."""

    @pytest.mark.parametrize("module_path", _APP_MODULES)
    def test_module_does_not_call_logging_getlogger(self, module_path: str):
        """Parse the module AST and verify there are no calls to
        logging.getLogger(__name__).  Modules should use
        get_logger(__name__) from utils.logging_config instead."""
        full_path = Path(__file__).resolve().parent.parent / module_path
        if not full_path.exists():
            pytest.skip(f"{module_path} not found")

        source = full_path.read_text()
        tree = ast.parse(source, filename=module_path)

        violations = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            # Match logging.getLogger(...)
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "logging"
                and func.attr == "getLogger"
            ):
                violations.append(node.lineno)

        assert not violations, (
            f"{module_path} still calls logging.getLogger() on line(s) "
            f"{violations}. Use get_logger() from utils.logging_config instead."
        )

    @pytest.mark.parametrize("module_path", _APP_MODULES)
    def test_module_imports_get_logger(self, module_path: str):
        """Verify each module imports get_logger."""
        full_path = Path(__file__).resolve().parent.parent / module_path
        if not full_path.exists():
            pytest.skip(f"{module_path} not found")

        source = full_path.read_text()
        assert (
            "get_logger" in source
        ), f"{module_path} does not import get_logger from utils.logging_config"


# ---------------------------------------------------------------------------
# configure_azure_monitor integration
# ---------------------------------------------------------------------------


class TestConfigureAzureMonitorIntegration:
    """Verify main.py passes the correct logger_name to configure_azure_monitor."""

    def test_main_passes_correct_logger_name(self):
        """Parse main.py and verify configure_azure_monitor is called with
        logger_name matching APP_LOGGER_NAME."""
        main_path = Path(__file__).resolve().parent.parent / "main.py"
        source = main_path.read_text()
        tree = ast.parse(source, filename="main.py")

        found = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            # Match configure_azure_monitor(...)
            if isinstance(func, ast.Name) and func.id == "configure_azure_monitor":
                for kw in node.keywords:
                    if kw.arg == "logger_name":
                        assert isinstance(kw.value, ast.Constant)
                        assert kw.value.value == APP_LOGGER_NAME, (
                            f"main.py passes logger_name={kw.value.value!r} but "
                            f"APP_LOGGER_NAME={APP_LOGGER_NAME!r}"
                        )
                        found = True
        assert found, "main.py does not call configure_azure_monitor with logger_name"


# ---------------------------------------------------------------------------
# Telemetry flush on shutdown
# ---------------------------------------------------------------------------


class TestTelemetryFlush:
    """Verify the shutdown path flushes OpenTelemetry data."""

    def test_main_contains_force_flush_call(self):
        """The lifespan shutdown block must call force_flush so that
        pending telemetry is exported before the container scales to zero.

        We verify this via AST inspection rather than runtime patching
        because the azure/opentelemetry packages may not be installed
        in the test environment.
        """
        main_path = Path(__file__).resolve().parent.parent / "main.py"
        source = main_path.read_text()
        tree = ast.parse(source, filename="main.py")

        found_force_flush = False
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "force_flush"
            ):
                # Verify it passes a timeout
                for kw in node.keywords:
                    if kw.arg == "timeout_millis":
                        found_force_flush = True
                        break

        assert found_force_flush, (
            "main.py must call force_flush(timeout_millis=...) in the "
            "shutdown path to flush OpenTelemetry data before scale-to-zero"
        )

    def test_force_flush_is_guarded_by_connection_string(self):
        """The force_flush call should only run when App Insights is enabled."""
        main_path = Path(__file__).resolve().parent.parent / "main.py"
        source = main_path.read_text()

        # The flush block should be inside 'if _appinsights_conn:'
        assert "if _appinsights_conn:" in source
        # And force_flush should appear after it
        conn_idx = source.index("if _appinsights_conn:", source.index("Shutting down"))
        flush_idx = source.index("force_flush", conn_idx)
        assert flush_idx > conn_idx


# ---------------------------------------------------------------------------
# Log record propagation (end-to-end namespace check)
# ---------------------------------------------------------------------------


class TestLogPropagation:
    """Verify that records from child loggers reach the app logger."""

    def test_child_record_reaches_app_logger(self):
        """A log record from bible_app.routes.chat should be visible to
        a handler on the bible_app logger."""
        setup_logging()

        captured: list[logging.LogRecord] = []
        handler = logging.Handler()
        handler.emit = lambda record: captured.append(record)  # type: ignore[assignment]

        app_logger = logging.getLogger(APP_LOGGER_NAME)
        app_logger.addHandler(handler)

        try:
            child = get_logger("routes.chat")
            child.info("test message")

            assert len(captured) == 1
            assert captured[0].name == f"{APP_LOGGER_NAME}.routes.chat"
            assert captured[0].getMessage() == "test message"
        finally:
            app_logger.removeHandler(handler)
