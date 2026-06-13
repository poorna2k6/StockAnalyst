"""CSV portfolio import — auto-detects Fidelity, Schwab, Robinhood, Webull, E*TRADE, generic."""

import csv
import io
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedPosition:
    ticker: str
    shares: float
    avg_cost: float
    name: Optional[str] = None
    source_row: int = 0


@dataclass
class CSVParseResult:
    positions: list[ParsedPosition] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    format_detected: str = "generic"
    total_rows_read: int = 0
    rows_skipped: int = 0


# ── Column name mappings per broker ──────────────────────────────────────────

_FORMAT_SIGNATURES: dict[str, set[str]] = {
    "fidelity": {"symbol", "description", "quantity", "average cost basis"},
    "schwab":   {"symbol", "description", "quantity", "average cost basis / share"},
    "robinhood": {"symbol", "average cost", "shares"},
    "webull":   {"ticker", "avg cost", "qty"},
    "etrade":   {"symbol", "quantity", "adjusted cost basis / share"},
}

_COLUMN_MAPS: dict[str, dict[str, str]] = {
    "fidelity": {
        "ticker":    "symbol",
        "shares":    "quantity",
        "avg_cost":  "average cost basis",
        "name":      "description",
    },
    "schwab": {
        "ticker":    "symbol",
        "shares":    "quantity",
        "avg_cost":  "average cost basis / share",
        "name":      "description",
    },
    "robinhood": {
        "ticker":    "symbol",
        "shares":    "shares",
        "avg_cost":  "average cost",
        "name":      "name",
    },
    "webull": {
        "ticker":    "ticker",
        "shares":    "qty",
        "avg_cost":  "avg cost",
        "name":      "name",
    },
    "etrade": {
        "ticker":    "symbol",
        "shares":    "quantity",
        "avg_cost":  "adjusted cost basis / share",
        "name":      "description",
    },
    "generic": {
        "ticker":    "ticker",
        "shares":    "shares",
        "avg_cost":  "avg_cost",
        "name":      "name",
    },
}

_TICKER_RE = re.compile(r'^[A-Z]{1,5}$')


def _clean_number(value: str) -> Optional[float]:
    """Strip $, commas, spaces and parse to float."""
    cleaned = re.sub(r'[$,\s]', '', value.strip())
    if not cleaned or cleaned in ("-", "--", "N/A", "n/a", ""):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def detect_format(headers: list[str]) -> str:
    """Return broker name or 'generic' based on CSV headers."""
    lower_headers = {h.strip().lower() for h in headers}
    for fmt, sigs in _FORMAT_SIGNATURES.items():
        if sigs.issubset(lower_headers):
            return fmt
    # Fallback: look for common generic patterns
    if "ticker" in lower_headers or "symbol" in lower_headers:
        return "generic"
    return "generic"


def _find_column(row_dict: dict, target_key: str, col_map: dict[str, str]) -> Optional[str]:
    """Find a value in a row using the column map, case-insensitive."""
    col_name = col_map.get(target_key, target_key)
    # Try exact match first
    if col_name in row_dict:
        return row_dict[col_name]
    # Try case-insensitive
    col_lower = col_name.lower()
    for k, v in row_dict.items():
        if k.strip().lower() == col_lower:
            return v
    return None


def parse_csv(content: str | bytes) -> CSVParseResult:
    """
    Parse a portfolio CSV file and return structured positions.
    Handles encoding, auto-detects format, validates tickers.
    """
    result = CSVParseResult()

    if isinstance(content, bytes):
        content = content.decode("utf-8-sig", errors="replace")

    # Strip leading non-CSV lines (Fidelity adds account header rows)
    lines = content.splitlines()
    start_idx = 0
    for i, line in enumerate(lines):
        if "," in line and any(
            kw in line.lower()
            for kw in ["symbol", "ticker", "shares", "quantity"]
        ):
            start_idx = i
            break

    csv_content = "\n".join(lines[start_idx:])
    reader = csv.DictReader(io.StringIO(csv_content))

    try:
        headers = reader.fieldnames or []
    except Exception:
        result.warnings.append("Could not read CSV headers — check file format")
        return result

    fmt = detect_format(list(headers))
    result.format_detected = fmt
    col_map = _COLUMN_MAPS[fmt]

    for row_num, row in enumerate(reader, start=1):
        result.total_rows_read += 1

        raw_ticker = _find_column(row, "ticker", col_map)
        raw_shares = _find_column(row, "shares", col_map)
        raw_cost   = _find_column(row, "avg_cost", col_map)
        raw_name   = _find_column(row, "name", col_map)

        if not raw_ticker:
            result.rows_skipped += 1
            continue

        ticker = raw_ticker.strip().upper()

        # Skip cash, money-market, totals rows
        if ticker in ("", "--", "TOTAL", "PENDING", "CASH", "SPAXX", "FCASH", "MMDA1"):
            result.rows_skipped += 1
            continue

        if not _TICKER_RE.match(ticker):
            result.rows_skipped += 1
            result.warnings.append(f"Row {row_num}: skipped '{ticker}' — not a valid ticker")
            continue

        shares = _clean_number(raw_shares or "")
        avg_cost = _clean_number(raw_cost or "")

        if shares is None or shares <= 0:
            result.rows_skipped += 1
            result.warnings.append(f"Row {row_num}: {ticker} — invalid shares '{raw_shares}'")
            continue

        if avg_cost is None or avg_cost <= 0:
            result.rows_skipped += 1
            result.warnings.append(f"Row {row_num}: {ticker} — invalid avg cost '{raw_cost}'")
            continue

        result.positions.append(ParsedPosition(
            ticker=ticker,
            shares=shares,
            avg_cost=avg_cost,
            name=raw_name.strip() if raw_name else None,
            source_row=row_num,
        ))

    return result
