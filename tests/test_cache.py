"""Unit tests for cache.py"""
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import cache


def setup_function():
    cache.clear()


def test_set_and_get():
    cache.set("k1", "hello", ttl=60)
    assert cache.get("k1") == "hello"


def test_miss_returns_none():
    assert cache.get("nonexistent_key_xyz") is None


def test_expiry():
    cache.set("k_expire", "value", ttl=1)
    assert cache.get("k_expire") == "value"
    time.sleep(1.1)
    assert cache.get("k_expire") is None


def test_overwrite():
    cache.set("k_ow", "first", ttl=60)
    cache.set("k_ow", "second", ttl=60)
    assert cache.get("k_ow") == "second"


def test_invalidate():
    cache.set("k_inv", "data", ttl=60)
    cache.invalidate("k_inv")
    assert cache.get("k_inv") is None


def test_invalidate_prefix():
    cache.set("quote:AAPL", 1, ttl=60)
    cache.set("quote:MSFT", 2, ttl=60)
    cache.set("news:AAPL", 3, ttl=60)
    cache.invalidate_prefix("quote:")
    assert cache.get("quote:AAPL") is None
    assert cache.get("quote:MSFT") is None
    assert cache.get("news:AAPL") == 3


def test_clear():
    cache.set("a", 1, ttl=60)
    cache.set("b", 2, ttl=60)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None


def test_stats():
    cache.set("s1", "x", ttl=60)
    cache.get("s1")    # hit
    cache.get("s_miss")  # miss
    stats = cache.stats()
    assert stats["valid_entries"] >= 1
    assert stats["hits"] >= 1
    assert stats["misses"] >= 1


def test_stores_complex_objects():
    obj = {"ticker": "AAPL", "price": 150.0, "list": [1, 2, 3]}
    cache.set("complex", obj, ttl=60)
    result = cache.get("complex")
    assert result == obj
