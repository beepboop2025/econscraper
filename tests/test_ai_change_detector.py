"""Tests for the AI change-detector report builder.

The only network call (to the local CLIProxy) is replaced with a fake
AsyncClient, so every test runs fully offline and deterministically.
"""

from __future__ import annotations

from datetime import datetime

import httpx
import pytest

import monitoring.ai_change_detector as acd
from monitoring.ai_change_detector import (
    _format_results_for_llm,
    _format_validation_diffs,
    analyze_changes,
)
from monitoring.source_health_checker import (
    IST,
    HealthCheckResult,
    HealthStatus,
)


def _result(name, status, notes="OK", ms=100.0, last_date=None, match=True):
    return HealthCheckResult(name, status, ms, last_date, match, notes)


# --- _format_results_for_llm ---------------------------------------------


def test_format_results_for_llm_includes_all_fields():
    when = datetime(2026, 3, 8, tzinfo=IST)
    line = _format_results_for_llm(
        [_result("NSE", HealthStatus.WARNING, notes="slow", ms=250.0, last_date=when)]
    )
    assert "NSE" in line
    assert "status=warning" in line
    assert "response_time=250ms" in line
    assert "structure_match=True" in line
    assert "2026-03-08" in line
    assert "notes=slow" in line


def test_format_results_for_llm_unknown_date():
    line = _format_results_for_llm([_result("X", HealthStatus.HEALTHY, last_date=None)])
    assert "last_data_date=unknown" in line


# --- _format_validation_diffs --------------------------------------------


def test_format_validation_diffs_only_lists_changed_sources():
    out = _format_validation_diffs(
        [
            ("nse", True, []),  # unchanged -> omitted
            ("rbi", False, ["Missing API keys: ['x']"]),
        ]
    )
    assert "rbi" in out
    assert "nse" not in out
    assert "Missing API keys" in out


def test_format_validation_diffs_no_changes_message():
    assert _format_validation_diffs([("nse", True, [])]) == "No structural changes detected."


# --- analyze_changes: all-clear short-circuit ----------------------------


@pytest.mark.asyncio
async def test_analyze_changes_all_clear_skips_network(monkeypatch):
    # If the network were touched this would raise; prove it isn't.
    def _boom(*a, **k):
        raise AssertionError("network must not be called on the all-clear path")

    monkeypatch.setattr(acd.httpx, "AsyncClient", _boom)

    results = [
        _result("A", HealthStatus.HEALTHY),
        _result("B", HealthStatus.HEALTHY),
    ]
    report = await analyze_changes(results, [("A", True, []), ("B", True, [])])
    assert "ALL CLEAR" in report
    assert "2/2 sources healthy" in report


# --- analyze_changes: connect-error fallback (offline) -------------------


class _FakeConnectErrorClient:
    """Async context manager whose .post raises ConnectError."""

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, *a, **k):
        raise httpx.ConnectError("refused")


@pytest.mark.asyncio
async def test_analyze_changes_connect_error_produces_raw_fallback(monkeypatch):
    monkeypatch.setattr(acd.httpx, "AsyncClient", _FakeConnectErrorClient)

    results = [_result("NSE", HealthStatus.BROKEN, notes="HTTP 503")]
    validation = [("nse", False, ["Missing API keys: ['seriess']"])]
    report = await analyze_changes(results, validation)

    # Header is always prepended.
    assert report.startswith("# EconScraper Health Report")
    # Fallback explains the proxy was unreachable and dumps raw problems.
    assert "CLIProxyAPI not reachable" in report
    assert "HTTP 503" in report
    assert "Missing API keys" in report


# --- analyze_changes: successful LLM response, header rewrite ------------


class _FakeOKClient:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, *a, **k):
        # The model returns its own markdown header that must be stripped
        # and replaced with the canonical one.
        body = "# Some Model Header\n\n🔴 BROKEN: NSE — down — fix selector"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": body}}]},
            request=httpx.Request("POST", "http://local"),
        )


@pytest.mark.asyncio
async def test_analyze_changes_strips_model_header_and_keeps_body(monkeypatch):
    monkeypatch.setattr(acd.httpx, "AsyncClient", _FakeOKClient)

    results = [_result("NSE", HealthStatus.BROKEN, notes="down")]
    report = await analyze_changes(results, [("nse", True, [])])

    # Canonical header present, model's own header removed.
    assert report.startswith("# EconScraper Health Report")
    assert "Some Model Header" not in report
    # Body content preserved.
    assert "🔴 BROKEN: NSE" in report
