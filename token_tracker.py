"""Token usage tracking and credit management."""

import os
from typing import Optional

# USD per 1 million tokens (input_price, output_price)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6":          (3.00,  15.00),
    "claude-haiku-4-5-20251001":  (0.25,   1.25),
    "claude-opus-4-8":            (15.00,  75.00),
    "gemini-1.5-flash":           (0.075,  0.30),
    "gemini-1.5-pro":             (3.50,  10.50),
    "gemini-2.0-flash":           (0.10,   0.40),
}


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    in_price, out_price = MODEL_PRICING.get(model, (3.00, 15.00))
    return (input_tokens * in_price + output_tokens * out_price) / 1_000_000


def track_usage(
    user_id: Optional[str],
    feature: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    was_byok: bool = False,
) -> float:
    """Log usage to Supabase, deduct app credits if not BYOK. Returns cost in USD."""
    cost = compute_cost(model, input_tokens, output_tokens)
    if not user_id or user_id == "anonymous":
        return cost
    try:
        from supabase_client import get_client
        client = get_client()
        if client:
            client.table("token_usage").insert({
                "user_id": user_id,
                "feature": feature,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost,
                "was_byok": was_byok,
            }).execute()
            if not was_byok:
                _deduct_credits(client, user_id, cost)
    except Exception as exc:
        print(f"[token_tracker] warning: {exc}")
    return cost


def _deduct_credits(client, user_id: str, cost: float) -> None:
    try:
        result = client.table("user_settings").select("credit_balance").eq("user_id", user_id).execute()
        if result.data:
            current = float(result.data[0].get("credit_balance") or 0)
            client.table("user_settings").update(
                {"credit_balance": max(0, current - cost)}
            ).eq("user_id", user_id).execute()
    except Exception as exc:
        print(f"[token_tracker] credit deduction failed: {exc}")


def get_usage_summary(user_id: str) -> dict:
    """Aggregate token usage stats for a user."""
    try:
        from supabase_client import get_client
        client = get_client()
        if not client:
            return {"error": "Supabase not configured"}
        result = client.table("token_usage").select("*").eq("user_id", user_id).execute()
        rows = result.data or []

        total_cost = sum(float(r.get("cost_usd") or 0) for r in rows)
        total_tokens = sum(
            int(r.get("input_tokens") or 0) + int(r.get("output_tokens") or 0) for r in rows
        )
        by_feature: dict = {}
        for r in rows:
            feat = r.get("feature", "unknown")
            if feat not in by_feature:
                by_feature[feat] = {"calls": 0, "tokens": 0, "cost_usd": 0.0}
            by_feature[feat]["calls"] += 1
            by_feature[feat]["tokens"] += int(r.get("input_tokens") or 0) + int(r.get("output_tokens") or 0)
            by_feature[feat]["cost_usd"] += float(r.get("cost_usd") or 0)

        return {
            "total_calls": len(rows),
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "by_feature": by_feature,
        }
    except Exception as exc:
        return {"error": str(exc)}
