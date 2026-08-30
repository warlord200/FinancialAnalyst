"""Email + password accounts.

Soft-verify start: a new account works immediately as unverified, with
stricter quotas. Verification is a stub today (no email service on day
one); a future email flow replaces it.
"""

import re
from contextlib import closing
from datetime import datetime, timezone

import bcrypt

from financial_analyst.auth.db import connect
from financial_analyst.auth.sessions import RevokedTokenStore
from financial_analyst.auth.tokens import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
)

MIN_PASSWORD_LENGTH = 8
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserAlreadyExistsError(Exception):
    pass


class InvalidEmailError(Exception):
    pass


class WeakPasswordError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


class UserStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        with closing(connect(db_path)):
            pass

    def create(self, email: str, password_hash: str) -> dict:
        created_at = datetime.now(timezone.utc).isoformat()
        with closing(connect(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO users (email, password_hash, verified, created_at)"
                " VALUES (?, ?, 0, ?)",
                (email, password_hash, created_at),
            )
            conn.commit()
        return {
            "email": email,
            "password_hash": password_hash,
            "verified": False,
            "created_at": created_at,
        }

    def get_by_email(self, email: str) -> dict | None:
        with closing(connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT email, password_hash, verified, created_at FROM users WHERE email = ?",
                (email,),
            ).fetchone()
        if row is None:
            return None
        return {
            "email": row["email"],
            "password_hash": row["password_hash"],
            "verified": bool(row["verified"]),
            "created_at": row["created_at"],
        }

    def set_verified(self, email: str, verified: bool = True) -> dict | None:
        with closing(connect(self.db_path)) as conn:
            conn.execute(
                "UPDATE users SET verified = ? WHERE email = ?", (int(verified), email)
            )
            conn.commit()
        return self.get_by_email(email)


class AuthService:
    def __init__(
        self,
        user_store: UserStore,
        secret: str,
        revoked_store: RevokedTokenStore | None = None,
    ) -> None:
        self.users = user_store
        self.secret = secret
        self.revoked = revoked_store

    def signup(self, email: str, password: str) -> dict:
        email = email.strip().lower()
        if not EMAIL_RE.match(email):
            raise InvalidEmailError("Enter a valid email address.")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise WeakPasswordError(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
            )
        if self.users.get_by_email(email) is not None:
            raise UserAlreadyExistsError("An account with that email already exists.")
        user = self.users.create(email, hash_password(password))
        return self._auth_payload(user)

    def login(self, email: str, password: str) -> dict:
        user = self.users.get_by_email(email.strip().lower())
        if user is None or not verify_password(password, user["password_hash"]):
            raise InvalidCredentialsError("Incorrect email or password.")
        return self._auth_payload(user)

    def verify(self, email: str) -> dict | None:
        """Mark an account verified. Stub for the future email flow;
        callable only by a trusted path today, never by the user directly."""
        return self.users.set_verified(email.strip().lower(), True)

    def authenticate_token(self, token: str) -> dict | None:
        try:
            payload = decode_access_token(token, self.secret)
        except InvalidTokenError:
            return None
        if self.revoked is not None and self.revoked.is_revoked(payload.get("jti", "")):
            return None
        user = self.users.get_by_email(payload.get("sub", ""))
        if user is None:
            return None
        return self.public_user(user)

    def revoke_token(self, token: str) -> None:
        """Invalidate a still-valid token (logout). Raises InvalidTokenError
        if the token cannot be decoded."""
        if self.revoked is None:
            raise InvalidTokenError("Token revocation is not configured.")
        payload = decode_access_token(token, self.secret)
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc).isoformat()
        self.revoked.revoke(payload["jti"], expires_at)

    def public_user(self, user: dict) -> dict:
        return {
            "email": user["email"],
            "verified": bool(user["verified"]),
            "created_at": user["created_at"],
        }

    def _auth_payload(self, user: dict) -> dict:
        return {
            "token": create_access_token(user, self.secret),
            "user": self.public_user(user),
        }
