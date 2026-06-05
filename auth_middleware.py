"""JWT authentication middleware for Supabase-issued tokens."""

import os
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)


def _decode(token: str) -> dict:
    secret = os.getenv("SUPABASE_JWT_SECRET")
    if not secret:
        raise ValueError("SUPABASE_JWT_SECRET not set")
    return jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        audience="authenticated",
        options={"verify_exp": True},
    )


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[str]:
    """
    Returns Supabase user_id (the JWT 'sub' claim) if the token is valid.
    Returns None when SUPABASE_JWT_SECRET is not set (single-user dev mode).
    Raises HTTP 401 if a token is present but invalid.
    """
    if not os.getenv("SUPABASE_JWT_SECRET"):
        return None  # dev / no-auth mode

    if creds is None:
        raise HTTPException(status_code=401, detail="Authorization header required")

    try:
        payload = _decode(creds.credentials)
        uid = payload.get("sub")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token: missing sub")
        return uid
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired — please sign in again")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")


def require_user(user_id: Optional[str] = Depends(get_current_user)) -> str:
    """Same as get_current_user but falls back to 'anonymous' in dev mode."""
    return user_id or "anonymous"
