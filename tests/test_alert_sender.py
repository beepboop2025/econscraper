"""Tests for Telegram message splitting and config env-var expansion.

Network-free: only the pure helpers _split_message and _load_config are
exercised, the latter against a temp config file.
"""

from __future__ import annotations

import monitoring.alert_sender as alert_sender
from monitoring.alert_sender import TELEGRAM_MAX_LENGTH, _load_config, _split_message


# --- _split_message ------------------------------------------------------


def test_short_message_is_single_part():
    assert _split_message("hello") == ["hello"]


def test_message_at_exact_limit_is_single_part():
    text = "x" * TELEGRAM_MAX_LENGTH
    parts = _split_message(text)
    assert len(parts) == 1
    assert parts[0] == text


def test_long_message_splits_into_multiple_parts_each_within_limit():
    text = "y" * (TELEGRAM_MAX_LENGTH * 2 + 50)
    parts = _split_message(text)
    assert len(parts) >= 3
    assert all(len(p) <= TELEGRAM_MAX_LENGTH for p in parts)
    # No characters are lost (no newlines to strip in this input).
    assert sum(len(p) for p in parts) == len(text)


def test_split_prefers_newline_boundary():
    # A newline sits comfortably past the half-limit, so the split should
    # happen there rather than mid-line.
    head = "a" * (TELEGRAM_MAX_LENGTH - 10)
    tail = "b" * 100
    text = head + "\n" + tail
    parts = _split_message(text)
    assert parts[0] == head  # split at the newline, newline consumed
    assert parts[1] == tail


def test_split_falls_back_to_hard_cut_when_no_good_newline():
    # Newline is too early (before half the limit) to be a useful split,
    # so the function hard-cuts at max_len.
    text = "z\n" + "q" * (TELEGRAM_MAX_LENGTH * 2)
    parts = _split_message(text)
    assert len(parts[0]) == TELEGRAM_MAX_LENGTH


# --- _load_config --------------------------------------------------------


def test_load_config_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(alert_sender, "CONFIG_PATH", tmp_path / "nope.yaml")
    assert _load_config() == {}


def test_load_config_expands_env_vars(monkeypatch, tmp_path):
    cfg = tmp_path / "alerts.yaml"
    cfg.write_text(
        "telegram:\n"
        "  enabled: true\n"
        "  bot_token: ${MY_BOT_TOKEN}\n"
        "  chat_id: ${MISSING_VAR}\n"
    )
    monkeypatch.setattr(alert_sender, "CONFIG_PATH", cfg)
    monkeypatch.setenv("MY_BOT_TOKEN", "secret123")
    monkeypatch.delenv("MISSING_VAR", raising=False)

    loaded = _load_config()
    assert loaded["telegram"]["enabled"] is True
    # Present env var is substituted...
    assert loaded["telegram"]["bot_token"] == "secret123"
    # ...and an unset var is left verbatim so callers can detect it.
    assert loaded["telegram"]["chat_id"] == "${MISSING_VAR}"
