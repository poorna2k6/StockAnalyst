"""Financial news aggregation — yfinance primary, NewsAPI optional."""

import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import yfinance as yf

import cache as _cache
from models import NewsItem, NewsBundle, NewsSentiment
from validator import utcnow_iso

_POSITIVE_WORDS = {
    "beat", "beats", "upgrade", "upgraded", "growth", "strong", "record",
    "surge", "rally", "gains", "profit", "revenue", "bullish", "buy",
    "outperform", "raised", "boost", "soar", "winner", "positive",
}
_NEGATIVE_WORDS = {
    "miss", "misses", "downgrade", "downgraded", "loss", "weak", "layoff",
    "layoffs", "fraud", "investigation", "warning", "decline", "drop",
    "fall", "bearish", "sell", "underperform", "cut", "concern", "risk",
    "debt", "lawsuit", "recall", "breach",
}


def _score_sentiment(items: list[NewsItem]) -> NewsSentiment:
    pos = neg = neu = 0
    for item in items:
        words = set(item.title.lower().split())
        p = len(words & _POSITIVE_WORDS)
        n = len(words & _NEGATIVE_WORDS)
        if p > n:
            pos += 1
        elif n > p:
            neg += 1
        else:
            neu += 1
    total = pos + neg + neu
    if total == 0:
        overall = "neutral"
    elif pos / total >= 0.5:
        overall = "bullish"
    elif neg / total >= 0.5:
        overall = "bearish"
    else:
        overall = "neutral"
    return NewsSentiment(positive_count=pos, negative_count=neg, neutral_count=neu, overall=overall)


def _parse_yf_news(raw_articles: list[dict], max_items: int) -> list[NewsItem]:
    items: list[NewsItem] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    for article in raw_articles[:max_items * 2]:
        title = article.get("title", "").strip()
        url = article.get("link") or article.get("url", "")
        publisher = article.get("publisher", "Unknown")
        pub_time = article.get("providerPublishTime")
        if not title or not url:
            continue
        pub_dt: Optional[str] = None
        if pub_time:
            try:
                dt = datetime.fromtimestamp(int(pub_time), tz=timezone.utc)
                if dt < cutoff:
                    continue
                pub_dt = dt.isoformat()
            except Exception:
                pass
        tickers = article.get("relatedTickers") or []
        items.append(NewsItem(
            title=title,
            url=url,
            publisher=publisher,
            published_at=pub_dt,
            related_tickers=tickers,
        ))
        if len(items) >= max_items:
            break
    return items


def get_ticker_news(ticker: str, max_items: int = 10) -> NewsBundle:
    """
    Fetch recent news for a specific ticker via yfinance.
    Cached with NEWS_TTL.
    """
    ticker = ticker.upper().strip()
    cache_key = f"news:{ticker}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    now_iso = utcnow_iso()
    articles: list[NewsItem] = []
    try:
        raw = yf.Ticker(ticker).news or []
        articles = _parse_yf_news(raw, max_items)
    except Exception:
        pass

    sentiment = _score_sentiment(articles)
    result = NewsBundle(
        ticker=ticker,
        fetched_at=now_iso,
        articles=articles,
        sentiment=sentiment,
    )
    _cache.set(cache_key, result, _cache.NEWS_TTL)
    return result


def get_market_news(max_items: int = 15) -> NewsBundle:
    """
    Fetch broad market news via SPY and QQQ yfinance news, deduplicated.
    Cached with NEWS_TTL.
    """
    cache_key = "news:market"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    now_iso = utcnow_iso()
    seen_urls: set[str] = set()
    articles: list[NewsItem] = []

    for proxy_ticker in ("SPY", "QQQ", "IWM"):
        try:
            raw = yf.Ticker(proxy_ticker).news or []
            for item in _parse_yf_news(raw, max_items):
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    articles.append(item)
        except Exception:
            continue
        if len(articles) >= max_items:
            break

    articles = articles[:max_items]
    sentiment = _score_sentiment(articles)
    result = NewsBundle(
        ticker=None,
        fetched_at=now_iso,
        articles=articles,
        sentiment=sentiment,
    )
    _cache.set(cache_key, result, _cache.NEWS_TTL)
    return result


def get_newsapi_news(query: str, max_items: int = 10) -> list[NewsItem]:
    """
    Fetch from NewsAPI.org. Only called if NEWS_API_KEY is set in environment.
    Returns empty list gracefully if key is missing or request fails.
    """
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        return []

    import requests
    cache_key = f"newsapi:{query[:50]}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": max_items,
                "apiKey": api_key,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        items: list[NewsItem] = []
        for article in data.get("articles", []):
            title = article.get("title", "").strip()
            url = article.get("url", "")
            if not title or not url or title == "[Removed]":
                continue
            pub = article.get("publishedAt")
            items.append(NewsItem(
                title=title,
                url=url,
                publisher=article.get("source", {}).get("name", "Unknown"),
                published_at=pub,
            ))
        _cache.set(cache_key, items, _cache.NEWS_TTL)
        return items
    except Exception:
        return []


def format_news_for_prompt(bundle: NewsBundle, max_items: int = 8) -> str:
    """Format a NewsBundle as compact text for Claude prompt injection."""
    if not bundle.articles:
        return "No recent news available."
    lines = []
    for i, item in enumerate(bundle.articles[:max_items], 1):
        date_str = (item.published_at or "")[:10]
        lines.append(f"{i}. [{date_str}] {item.title} — {item.publisher}")
    sentiment = bundle.sentiment
    if sentiment:
        lines.append(f"\nSentiment (keyword-based): {sentiment.overall.upper()} "
                     f"({sentiment.positive_count} positive / {sentiment.negative_count} negative / "
                     f"{sentiment.neutral_count} neutral)")
    return "\n".join(lines)
