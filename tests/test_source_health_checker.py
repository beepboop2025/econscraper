"""Tests for pure-logic helpers in source_health_checker.

All tests here are network-free: they exercise date parsing, staleness logic,
and the terminal table formatter directly.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from monitoring.source_health_checker import (
    IST,
    HealthCheckResult,
    HealthStatus,
    _is_weekday_stale,
    _parse_date_fuzzy,
    format_results_table,
)


# --- _parse_date_fuzzy ---------------------------------------------------


def test_parse_date_dd_mm_yyyy_slash():
    d = _parse_date_fuzzy("Updated on 05/03/2026 at noon")
    assert d is not None
    assert (d.year, d.month, d.day) == (2026, 3, 5)
    # Result must be tz-aware in IST
    assert d.tzinfo == IST


def test_parse_date_dd_mm_yyyy_dash_normalized():
    # Dashes are normalized to slashes before %d/%m/%Y parsing.
    d = _parse_date_fuzzy("12-07-2025")
    assert d is not None
    assert (d.year, d.month, d.day) == (2025, 7, 12)


def test_parse_date_iso_yyyy_mm_dd():
    d = _parse_date_fuzzy("snapshot 2024-11-30 final")
    assert d is not None
    assert (d.year, d.month, d.day) == (2024, 11, 30)


def test_parse_date_dayfirst_dateutil_fallback():
    # No explicit numeric pattern matches "3 January 2026"; dateutil fallback
    # with dayfirst=True handles it.
    d = _parse_date_fuzzy("Published: 3 January 2026")
    assert d is not None
    assert (d.year, d.month, d.day) == (2026, 1, 3)


def test_parse_date_returns_none_on_garbage():
    assert _parse_date_fuzzy("no date at all here !!!") is None
    assert _parse_date_fuzzy("") is None


def test_parse_date_invalid_numeric_falls_through_to_none():
    # 45/45/2026 matches the dd/mm regex but strptime raises ValueError,
    # and dateutil can't parse it either -> None.
    assert _parse_date_fuzzy("45/45/2026") is None


# --- _is_weekday_stale ---------------------------------------------------


def test_stale_when_no_date():
    assert _is_weekday_stale(None) is True


def test_fresh_when_recent():
    recent = datetime.now(IST) - timedelta(hours=2)
    assert _is_weekday_stale(recent, max_days=3) is False


def test_stale_when_old():
    old = datetime.now(IST) - timedelta(days=10)
    assert _is_weekday_stale(old, max_days=3) is True


def test_weekend_grace_extends_threshold(monkeypatch):
    # Freeze "now" to a known Monday (2026-03-09 is a Monday) so the
    # Monday +2 day grace window is deterministic.
    import monitoring.source_health_checker as mod

    monday = datetime(2026, 3, 9, 12, 0, tzinfo=IST)

    class _FrozenDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return monday

    monkeypatch.setattr(mod, "datetime", _FrozenDT)

    # 4 days old on a Monday: base max_days=3 -> +2 weekend grace = 5,
    # so 4 days is NOT stale.
    four_days = monday - timedelta(days=4)
    assert mod._is_weekday_stale(four_days, max_days=3) is False

    # 6 days old exceeds the 5-day Monday window -> stale.
    six_days = monday - timedelta(days=6)
    assert mod._is_weekday_stale(six_days, max_days=3) is True


# --- format_results_table ------------------------------------------------


def _result(name, status, notes="OK", ms=123.0):
    return HealthCheckResult(name, status, ms, None, True, notes)


def test_format_table_counts_only_healthy():
    results = [
        _result("A", HealthStatus.HEALTHY),
        _result("B", HealthStatus.HEALTHY),
        _result("C", HealthStatus.BROKEN, notes="down"),
        _result("D", HealthStatus.WARNING, notes="slow"),
    ]
    table = format_results_table(results)
    assert "2/4 sources healthy" in table


def test_format_table_includes_source_names_and_truncates_notes():
    long_notes = "x" * 80
    table = format_results_table([_result("RBI DBIE", HealthStatus.WARNING, notes=long_notes)])
    assert "RBI DBIE" in table
    # Notes are truncated to 40 chars in the table body.
    assert "x" * 40 in table
    assert "x" * 41 not in table


def test_format_table_renders_response_time_rounded():
    table = format_results_table([_result("S", HealthStatus.HEALTHY, ms=456.7)])
    # f"{ms:.0f}ms" -> rounds to nearest integer.
    assert "457ms" in table


def test_format_table_empty_is_zero_of_zero():
    table = format_results_table([])
    assert "0/0 sources healthy" in table
