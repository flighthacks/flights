"""Authentication — JWT tokens (hand-rolled HMAC), password hashing, dependency injection."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Header

SECRET_KEY = os.environ.get("JWT_SECRET", "autofare-dev-secret-change-in-production")
ACCESS_TOKEN_EXPIRE_HOURS = 72


@dataclass
class AuthUser:
    id: str
    email: str
    name: str = ""
    tier: str = "free"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_access_token(user_id: str, email: str) -> str:
    """Create a simple HMAC-SHA256 JWT token."""
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    exp = int((datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)).timestamp())
    payload = _b64url_encode(json.dumps({"sub": user_id, "email": email, "exp": exp}).encode())
    signing_input = f"{header}.{payload}"
    signature = _b64url_encode(
        hmac.new(SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256).digest()
    )
    return f"{header}.{payload}.{signature}"


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token format")

        header, payload, signature = parts
        signing_input = f"{header}.{payload}"
        expected_sig = _b64url_encode(
            hmac.new(SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256).digest()
        )

        if not hmac.compare_digest(signature, expected_sig):
            raise HTTPException(401, "Invalid token signature")

        claims = json.loads(_b64url_decode(payload))

        if claims.get("exp") and claims["exp"] < time.time():
            raise HTTPException(401, "Token expired")

        return claims
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid token")


async def get_current_user(
    authorization: Optional[str] = Header(None),
) -> AuthUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing authorization header")

    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)

    from .database import get_db_instance
    db = get_db_instance()
    user = await db.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(401, "User not found")

    return AuthUser(
        id=user["id"],
        email=user["email"],
        name=user.get("name", ""),
        tier=user.get("tier", "free"),
    )
