"""Tests for the structural fingerprinting + diff engine.

These exercise the HTML / JSON / RSS fingerprint extractors and the
fingerprint comparator, all offline against in-memory documents.
"""

from __future__ import annotations

from monitoring.structure_validator import (
    _compare_fingerprints,
    _extract_api_fingerprint,
    _extract_html_fingerprint,
    _extract_rss_fingerprint,
)


# --- _extract_html_fingerprint -------------------------------------------


def test_html_fingerprint_counts_tables_and_headers():
    html = """
    <html><body>
      <h2>Weekly Statistical Supplement</h2>
      <table class="data grid"><tr><th>Rate</th></tr></table>
      <table class="aux"><tr><td>x</td></tr></table>
    </body></html>
    """
    fp = _extract_html_fingerprint(html, "http://example.test")
    assert fp["table_count"] == 2
    assert "data.grid" in fp["key_selectors"]
    assert "Weekly Statistical Supplement" in fp["section_headers"]
    # <th> text is captured as a header too.
    assert "Rate" in fp["section_headers"]
    assert fp["url"] == "http://example.test"


def test_html_fingerprint_normalizes_download_link_dates():
    html = """
    <a href="/files/report-2026-03-08.csv">today</a>
    <a href="/files/report-2025-01-01.csv">old</a>
    <a href="/about">not a download</a>
    """
    fp = _extract_html_fingerprint(html, "u")
    # The two dated CSV links collapse to a single regex pattern.
    assert len(fp["download_url_patterns"]) == 1
    pat = fp["download_url_patterns"][0]
    assert "\\d{4}[-/]\\d{2}[-/]\\d{2}" in pat
    assert ".csv" in pat


def test_html_fingerprint_size_range_brackets_length():
    html = "<html></html>"
    fp = _extract_html_fingerprint(html, "u")
    lo, hi = fp["response_size_range"]
    assert lo == max(0, len(html) - 5000)
    assert hi == len(html) + 5000


# --- _extract_api_fingerprint --------------------------------------------


def test_api_fingerprint_top_level_keys_and_schema():
    data = {"seriess": [{"id": "GDP", "value": 1.0}], "count": 1}
    fp = _extract_api_fingerprint(data, "u")
    assert set(fp["top_level_keys"]) == {"seriess", "count"}
    assert fp["json_schema"]["count"] == "int"
    # Nested list element schema is recursed into.
    assert fp["json_schema"]["seriess"][0]["id"] == "str"


def test_api_fingerprint_list_payload_has_no_top_level_keys():
    fp = _extract_api_fingerprint([1, 2, 3], "u")
    assert fp["top_level_keys"] == []
    assert fp["json_schema"] == ["int"]


def test_api_fingerprint_empty_list_marker():
    fp = _extract_api_fingerprint({"items": []}, "u")
    assert fp["json_schema"]["items"] == ["empty"]


# --- _extract_rss_fingerprint --------------------------------------------


RSS_DOC = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><title>A</title><link>http://a</link><pubDate>Mon, 09 Mar 2026 10:00:00 GMT</pubDate></item>
  <item><title>B</title><link>http://b</link><pubDate>Mon, 09 Mar 2026 09:00:00 GMT</pubDate></item>
</channel></rss>"""

ATOM_DOC = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><title>A</title><link href="http://a"/><updated>2026-03-09T10:00:00Z</updated></entry>
</feed>"""


def test_rss_fingerprint_detects_rss2_and_fields():
    fp = _extract_rss_fingerprint(RSS_DOC, "u")
    assert fp["format"] == "rss2"
    assert "title" in fp["item_fields"]
    assert "link" in fp["item_fields"]
    assert "pubDate" in fp["item_fields"]
    lo, hi = fp["item_count_range"]
    assert lo <= 2 <= hi


def test_rss_fingerprint_detects_atom():
    fp = _extract_rss_fingerprint(ATOM_DOC, "u")
    assert fp["format"] == "atom"
    assert "title" in fp["item_fields"]


# --- _compare_fingerprints -----------------------------------------------


def test_compare_identical_html_is_match():
    base = _extract_html_fingerprint(
        "<table class='a'></table><table class='a'></table><h2>Head</h2>", "u"
    )
    match, diffs = _compare_fingerprints(dict(base), base)
    assert match is True
    assert diffs == []


def test_compare_flags_large_table_count_drop():
    baseline = {"table_count": 10}
    current = {"table_count": 2}  # drop of 8 > max(2, 5)
    match, diffs = _compare_fingerprints(current, baseline)
    assert match is False
    assert any("Table count changed" in d for d in diffs)


def test_compare_tolerates_small_table_count_jitter():
    baseline = {"table_count": 10}
    current = {"table_count": 8}  # drop of 2 is within max(2, 5)
    match, diffs = _compare_fingerprints(current, baseline)
    assert match is True


def test_compare_flags_missing_api_keys_but_new_keys_are_info():
    baseline = {"top_level_keys": ["seriess", "count"]}
    current = {"top_level_keys": ["count", "realtime_start"]}
    match, diffs = _compare_fingerprints(current, baseline)
    assert match is False
    joined = " ".join(diffs)
    assert "Missing API keys" in joined and "seriess" in joined
    assert "New API keys" in joined and "realtime_start" in joined


def test_compare_flags_missing_rss_fields():
    baseline = {"item_fields": ["title", "link", "pubDate"]}
    current = {"item_fields": ["title", "link"]}
    match, diffs = _compare_fingerprints(current, baseline)
    assert match is False
    assert any("pubDate" in d for d in diffs)


def test_compare_flags_zero_item_rss_feed():
    baseline = {"item_count_range": [90, 110]}
    current = {"item_count_range": [0, 0]}
    match, diffs = _compare_fingerprints(current, baseline)
    assert match is False
    assert any("0 items" in d for d in diffs)


def test_compare_missing_headers_only_flagged_above_threshold():
    baseline = {"section_headers": ["a", "b", "c", "d", "e"]}
    # Missing 1 of 5 (20%) is under the 30% threshold -> still a match.
    ok_match, _ = _compare_fingerprints({"section_headers": ["a", "b", "c", "d"]}, baseline)
    assert ok_match is True
    # Missing 3 of 5 (60%) exceeds threshold -> flagged.
    bad_match, diffs = _compare_fingerprints({"section_headers": ["a", "b"]}, baseline)
    assert bad_match is False
    assert any("Missing headers" in d for d in diffs)
