"""CEO-only password session authentication; short-lived signed HttpOnly cookie."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

SESSION_COOKIE = "agentic_ceo_session"
SESSION_SECONDS = 8 * 60 * 60
HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def password_hash(password: str) -> str:
    if len(password) < 12 or len(password) > 1024:
        raise ValueError("CEO password must be 12-1024 characters")
    return HASHER.hash(password)


def verify_password(encoded: str, password: str) -> bool:
    try:
        return HASHER.verify(encoded, password)
    except (VerifyMismatchError, VerificationError):
        return False


def signer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt="agentic-s1-ceo-auth")


def make_session(secret: str, user_id: str) -> tuple[str, str]:
    nonce = secrets.token_urlsafe(24)
    issued = int(datetime.now(timezone.utc).timestamp())
    cookie = signer(secret).dumps({"sub": user_id, "nonce": nonce, "iat": issued})
    return cookie, csrf_token(secret, nonce)


def read_session(secret: str, cookie: str) -> dict | None:
    try:
        data = signer(secret).loads(cookie, max_age=SESSION_SECONDS)
        if not isinstance(data, dict) or not isinstance(data.get("sub"), str) or not isinstance(data.get("nonce"), str):
            return None
        return data
    except (BadSignature, SignatureExpired):
        return None


def csrf_token(secret: str, nonce: str) -> str:
    return hmac.new(secret.encode("utf-8"), ("csrf:" + nonce).encode("utf-8"), hashlib.sha256).hexdigest()


def csrf_valid(secret: str, nonce: str, candidate: str | None) -> bool:
    return candidate is not None and hmac.compare_digest(csrf_token(secret, nonce), candidate)
