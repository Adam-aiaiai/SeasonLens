from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .storage import PersistentRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def password_hash(password: str, *, iterations: int = 600_000, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
        base64.urlsafe_b64encode(derived).decode("ascii").rstrip("="),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_value, expected_value = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_value + "=" * (-len(salt_value) % 4))
        expected = base64.urlsafe_b64decode(expected_value + "=" * (-len(expected_value) % 4))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def valid_password_hash(encoded: str) -> bool:
    """Validate the supported password-hash envelope without checking a password."""

    try:
        algorithm, iterations_value, salt_value, expected_value = encoded.split("$", 3)
        iterations = int(iterations_value)
        salt = base64.urlsafe_b64decode(salt_value + "=" * (-len(salt_value) % 4))
        expected = base64.urlsafe_b64decode(expected_value + "=" * (-len(expected_value) % 4))
        return (algorithm == "pbkdf2_sha256" and iterations > 0
                and len(salt) >= 16 and len(expected) == hashlib.sha256().digest_size)
    except (ValueError, TypeError):
        return False


def opaque_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class ResearcherAuth:
    def __init__(self, repository: PersistentRepository, *,
                 username: str | None = None, password_digest: str | None = None,
                 development_password: str | None = None,
                 clock: Callable[[], datetime] = _utc_now) -> None:
        self.repository = repository
        self.username = (os.environ.get("SEASONLENS_RESEARCHER_USERNAME", "")
                         if username is None else username)
        configured_hash = (os.environ.get("SEASONLENS_RESEARCHER_PASSWORD_HASH", "")
                           if password_digest is None else password_digest)
        development_password = (os.environ.get("SEASONLENS_RESEARCHER_PASSWORD")
                                if development_password is None else development_password)
        self.using_development_password = bool(development_password and not configured_hash)
        if os.environ.get("RAILWAY_ENVIRONMENT") and self.using_development_password:
            development_password = None
            self.using_development_password = False
        self.password_digest = configured_hash or (password_hash(development_password) if development_password else "")
        self.clock = clock

    @property
    def configured(self) -> bool:
        return bool(self.username and valid_password_hash(self.password_digest))

    @property
    def configuration_errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.username:
            errors.append("SEASONLENS_RESEARCHER_USERNAME is missing")
        if not self.password_digest:
            errors.append("SEASONLENS_RESEARCHER_PASSWORD_HASH is missing")
        elif not valid_password_hash(self.password_digest):
            errors.append("SEASONLENS_RESEARCHER_PASSWORD_HASH is invalid")
        return tuple(errors)

    def login(self, username: str, password: str) -> tuple[str, dict[str, Any]]:
        # Run a real PBKDF2 check even for an unknown user to reduce timing leakage.
        fallback = "pbkdf2_sha256$600000$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        digest = (self.password_digest
                  if self.configured and hmac.compare_digest(username, self.username)
                  else fallback)
        valid = verify_password(password, digest)
        if not self.configured or not valid or not hmac.compare_digest(username, self.username):
            raise PermissionError("Invalid researcher credentials.")
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        created = self.clock()
        expires = created + timedelta(hours=12)
        session = {"username": username, "csrf_token": csrf,
                   "created_at": created.isoformat(), "expires_at": expires.isoformat()}
        self.repository.create_researcher_session(
            opaque_hash(token), username, csrf, session["created_at"], session["expires_at"])
        return token, session

    def authenticate(self, token: str) -> dict[str, Any]:
        if not token:
            raise PermissionError("Researcher authentication is required.")
        session = self.repository.researcher_session(opaque_hash(token), self.clock().isoformat())
        if not session:
            raise PermissionError("Researcher session is invalid or expired.")
        return session

    def require_csrf(self, token: str, csrf: str) -> dict[str, Any]:
        session = self.authenticate(token)
        if not csrf or not hmac.compare_digest(csrf, session["csrf_token"]):
            raise PermissionError("A valid CSRF token is required.")
        return session

    def logout(self, token: str) -> None:
        if token:
            self.repository.delete_researcher_session(opaque_hash(token))
