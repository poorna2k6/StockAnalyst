"""Ticker validation and data provenance stamping."""

import re
from datetime import datetime, timezone
from typing import Any

import yfinance as yf

import cache as _cache

# Accepts standard US tickers (1-5 chars) + exchange qualifiers like BRK-B, BRK.B
_TICKER_RE = re.compile(r'^[A-Z]{1,6}([-\.][A-Z]{1,2})?$')


def validate_ticker(ticker: str) -> tuple[bool, str | None, str | None]:
    """
    Returns (is_valid, company_name_or_None, error_message_or_None).
    Calls yfinance and checks for a non-zero market price.
    Caches results to avoid repeated round-trips.
    """
    ticker = ticker.upper().strip()
    cache_key = f"validate:{ticker}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    if not _TICKER_RE.match(ticker):
        result: tuple[bool, str | None, str | None] = (
            False, None, f"Invalid ticker format: '{ticker}'"
        )
        _cache.set(cache_key, result, _cache.VALIDATION_TTL)
        return result

    try:
        info = yf.Ticker(ticker).info
        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("regularMarketOpen")
            or info.get("navPrice")
        )
        if not price or float(price) <= 0:
            result = (False, None, f"No market price found for '{ticker}'. May be delisted or invalid.")
            _cache.set(cache_key, result, 60)
            return result
        name = info.get("longName") or info.get("shortName") or ticker
        result = (True, str(name), None)
        _cache.set(cache_key, result, _cache.VALIDATION_TTL)
        return result
    except Exception as exc:
        result = (False, None, f"Error validating '{ticker}': {exc}")
        _cache.set(cache_key, result, 60)
        return result


def validate_tickers(tickers: list[str]) -> dict[str, tuple[bool, str | None, str | None]]:
    """Validate multiple tickers. Returns dict keyed by normalized ticker."""
    return {t.upper().strip(): validate_ticker(t) for t in tickers}


def stamp(data: dict[str, Any], source: str = "yfinance") -> dict[str, Any]:
    """Inject provenance metadata into any data dict before returning to callers."""
    data["fetched_at"] = datetime.now(timezone.utc).isoformat()
    data["data_source"] = source
    return data


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
