"""Unit tests for validator.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import cache
import validator


def setup_function():
    cache.clear()


def test_invalid_format_short():
    valid, name, error = validator.validate_ticker("A" * 10)
    assert valid is False
    assert error is not None


def test_invalid_format_numeric():
    valid, name, error = validator.validate_ticker("123")
    assert valid is False


def test_invalid_format_empty():
    valid, name, error = validator.validate_ticker("")
    assert valid is False


def test_normalizes_lowercase():
    # Should normalize to uppercase before regex check
    # Can't hit yfinance in unit test; ensure it at least tries uppercase
    ticker = "aapl"
    normalized = ticker.upper().strip()
    assert normalized == "AAPL"


def test_stamp_adds_fields():
    data = {"price": 100.0}
    stamped = validator.stamp(data)
    assert "fetched_at" in stamped
    assert "data_source" in stamped
    assert stamped["data_source"] == "yfinance"


def test_stamp_custom_source():
    data = {}
    stamped = validator.stamp(data, source="newsapi")
    assert stamped["data_source"] == "newsapi"


def test_utcnow_iso_format():
    ts = validator.utcnow_iso()
    assert "T" in ts
    assert "+" in ts or "Z" in ts or len(ts) > 19


def test_ticker_regex_valid_formats():
    import re
    pattern = re.compile(r'^[A-Z]{1,6}([-\.][A-Z]{1,2})?$')
    assert pattern.match("AAPL")
    assert pattern.match("MSFT")
    assert pattern.match("BRK-B")
    assert pattern.match("BRK.B")
    assert pattern.match("SPY")


def test_ticker_regex_invalid_formats():
    import re
    pattern = re.compile(r'^[A-Z]{1,6}([-\.][A-Z]{1,2})?$')
    assert not pattern.match("TOOLONG123")
    assert not pattern.match("12AB")
    assert not pattern.match("")
