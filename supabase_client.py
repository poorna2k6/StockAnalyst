"""Supabase admin client — server-side database operations (bypasses RLS via service key)."""

import os
from typing import Optional

_client = None


def get_client():
    """Return Supabase admin client (lazy init). None if not configured."""
    global _client
    if _client is not None:
        return _client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if url and key:
        from supabase import create_client
        _client = create_client(url, key)
    return _client


def is_configured() -> bool:
    return get_client() is not None


# ── User Settings ─────────────────────────────────────────────────────────────

def get_user_settings(user_id: str) -> dict:
    client = get_client()
    if not client:
        return {"preferred_model": "claude", "use_byok": False, "credit_balance": 0.0}
    result = client.table("user_settings").select("*").eq("user_id", user_id).execute()
    if result.data:
        return result.data[0]
    defaults = {"user_id": user_id, "preferred_model": "claude", "use_byok": False, "credit_balance": 0.0}
    client.table("user_settings").insert(defaults).execute()
    return defaults


def upsert_user_settings(user_id: str, updates: dict) -> dict:
    client = get_client()
    if not client:
        return updates
    updates["user_id"] = user_id
    result = client.table("user_settings").upsert(updates, on_conflict="user_id").execute()
    return result.data[0] if result.data else updates


# ── Portfolio ─────────────────────────────────────────────────────────────────

def get_or_create_portfolio(user_id: str) -> dict:
    client = get_client()
    if not client:
        return {}
    result = client.table("portfolios").select("*").eq("user_id", user_id).execute()
    if result.data:
        return result.data[0]
    new_row = {"user_id": user_id, "cash": 0.0}
    result = client.table("portfolios").insert(new_row).execute()
    return result.data[0] if result.data else new_row


def get_positions(portfolio_id: str) -> list:
    client = get_client()
    if not client:
        return []
    result = client.table("positions").select("*").eq("portfolio_id", portfolio_id).execute()
    return result.data or []


def upsert_position(portfolio_id: str, ticker: str, shares: float, avg_cost: float) -> None:
    client = get_client()
    if not client:
        return
    existing = (
        client.table("positions")
        .select("id, shares, avg_cost")
        .eq("portfolio_id", portfolio_id)
        .eq("ticker", ticker)
        .execute()
    )
    if existing.data:
        pos = existing.data[0]
        total_shares = pos["shares"] + shares
        new_avg = (pos["shares"] * pos["avg_cost"] + shares * avg_cost) / total_shares
        client.table("positions").update({"shares": total_shares, "avg_cost": new_avg}).eq("id", pos["id"]).execute()
    else:
        client.table("positions").insert(
            {"portfolio_id": portfolio_id, "ticker": ticker, "shares": shares, "avg_cost": avg_cost}
        ).execute()


def delete_position(portfolio_id: str, ticker: str) -> None:
    client = get_client()
    if not client:
        return
    client.table("positions").delete().eq("portfolio_id", portfolio_id).eq("ticker", ticker).execute()


def update_cash(user_id: str, amount: float) -> None:
    client = get_client()
    if not client:
        return
    client.table("portfolios").update({"cash": amount, "updated_at": "now()"}).eq("user_id", user_id).execute()


def reset_user_portfolio(user_id: str) -> None:
    client = get_client()
    if not client:
        return
    port = get_or_create_portfolio(user_id)
    client.table("positions").delete().eq("portfolio_id", port["id"]).execute()
    client.table("portfolios").update({"cash": 0.0}).eq("user_id", user_id).execute()


# ── Watchlist ─────────────────────────────────────────────────────────────────

def get_watchlist(user_id: str) -> list[str]:
    client = get_client()
    if not client:
        return []
    result = client.table("watchlists").select("ticker, added_at").eq("user_id", user_id).execute()
    return result.data or []


def add_to_watchlist(user_id: str, ticker: str) -> None:
    client = get_client()
    if not client:
        return
    client.table("watchlists").upsert({"user_id": user_id, "ticker": ticker}).execute()


def remove_from_watchlist(user_id: str, ticker: str) -> None:
    client = get_client()
    if not client:
        return
    client.table("watchlists").delete().eq("user_id", user_id).eq("ticker", ticker).execute()


# ── Chat History ──────────────────────────────────────────────────────────────

def save_chat_message(user_id: str, session_id: str, role: str, content: str, model: str | None = None) -> None:
    client = get_client()
    if not client:
        return
    client.table("chat_history").insert(
        {"user_id": user_id, "session_id": session_id, "role": role, "content": content, "model": model}
    ).execute()


def get_chat_history(user_id: str, session_id: str = "default", limit: int = 50) -> list:
    client = get_client()
    if not client:
        return []
    result = (
        client.table("chat_history")
        .select("role, content, model, created_at")
        .eq("user_id", user_id)
        .eq("session_id", session_id)
        .order("created_at")
        .limit(limit)
        .execute()
    )
    return result.data or []
