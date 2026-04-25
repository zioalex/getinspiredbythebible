"""
Tests for the synthetic-monitor probe bypass helper.

The helper gates Turnstile + rate-limit bypass behind a shared secret that
must match what's deployed in the backend. These tests cover the critical
fail-closed paths (header without server config, mismatched value, empty
strings) since a bug here lets unauthenticated clients bypass bot
protection.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from starlette.requests import Request

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.monitor_probe import PROBE_HEADER, is_monitor_probe


def _request_with_header(value: str | None) -> Request:
    req = MagicMock(spec=Request)
    req.headers = {PROBE_HEADER: value} if value is not None else {}
    return req


class TestIsMonitorProbe:
    @pytest.mark.parametrize("server_secret", [None, ""])
    def test_unconfigured_server_never_bypasses(self, server_secret):
        """Empty/None server secret = bypass disabled, even if header matches."""
        with patch("utils.monitor_probe.settings") as s:
            s.monitor_probe_secret = server_secret
            assert is_monitor_probe(_request_with_header("anything")) is False

    def test_missing_header_does_not_bypass(self):
        with patch("utils.monitor_probe.settings") as s:
            s.monitor_probe_secret = "configured-secret"
            assert is_monitor_probe(_request_with_header(None)) is False

    def test_empty_header_does_not_bypass(self):
        with patch("utils.monitor_probe.settings") as s:
            s.monitor_probe_secret = "configured-secret"
            assert is_monitor_probe(_request_with_header("")) is False

    def test_mismatched_header_does_not_bypass(self):
        with patch("utils.monitor_probe.settings") as s:
            s.monitor_probe_secret = "configured-secret"
            assert is_monitor_probe(_request_with_header("wrong-secret")) is False

    def test_matching_header_bypasses(self):
        with patch("utils.monitor_probe.settings") as s:
            s.monitor_probe_secret = "configured-secret"
            assert is_monitor_probe(_request_with_header("configured-secret")) is True

    def test_compare_is_constant_time(self):
        """Sanity: the helper uses hmac.compare_digest, so case/length
        differences should not short-circuit early. We can't test timing
        directly, but we can confirm the matching path returns True for
        equal-length strings and False otherwise."""
        with patch("utils.monitor_probe.settings") as s:
            s.monitor_probe_secret = "abc-123"
            assert is_monitor_probe(_request_with_header("abc-124")) is False
            assert is_monitor_probe(_request_with_header("abc-1230")) is False
