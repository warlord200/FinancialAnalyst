"""Stateless JWT access tokens for the API.

The signing secret comes from the AUTH_SECRET environment variable or a
persisted key file, so issued tokens survive server restarts. Each token
carries a unique id (jti) so logout can denylist it.
"""

import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt

ALGORITHM = "HS256"
DEFAULT_TTL_MINUTES = 60 * 24 * 7


class InvalidTokenError(Exception):
    pass


def load_or_create_secret(path: str) -> str:
    secret = os.getenv("AUTH_SECRET")
    if secret:
        return secret
    key_path = Path(path)
    if key_path.is_file():
        return key_path.read_text(encoding="utf-8").strip()
    secret = secrets.token_hex(32)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(secret, encoding="utf-8")
    return secret


def create_access_token(user: dict, secret: str, expires_minutes: int = DEFAULT_TTL_MINUTES) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["email"],
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, secret: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc))
