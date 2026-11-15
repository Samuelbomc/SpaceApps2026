"""Contraseñas Argon2id, sesiones opacas y CSRF ligado a la sesión."""

import hashlib
import hmac
import secrets
import threading
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

HASHER = PasswordHasher()
HASH_SLOTS = threading.BoundedSemaphore(4)


def hash_password(value):
    with HASH_SLOTS:
        return HASHER.hash(value)


DUMMY_HASH = hash_password(secrets.token_urlsafe(32))
COOKIE_NAME = "agrogeo_session"
# Compatibilidad de sesiones emitidas antes de adoptar la identidad AgroGeo.
LEGACY_COOKIE_NAME = "fieldshift_session"
LEGACY_CSRF_CONTEXT = b"fieldshift-csrf-v1"
SESSION_SECONDS = 7 * 86400


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_token(value):
    return hmac.new(value.encode(), b"agrogeo-csrf-v1", hashlib.sha256).hexdigest()


def session_token(cookies: Mapping[str, str]) -> str:
    # La cookie actual tiene precedencia, incluso si está vacía o es inválida.
    return cookies.get(COOKIE_NAME, cookies.get(LEGACY_COOKIE_NAME, ""))


def valid_csrf(value: str, provided: str) -> bool:
    if not provided.isascii() or len(provided) != 64:
        return False
    legacy = hmac.new(value.encode(), LEGACY_CSRF_CONTEXT, hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided, csrf_token(value)) or hmac.compare_digest(provided, legacy)


def verify_password(value, encoded):
    try:
        with HASH_SLOTS:
            return HASHER.verify(encoded or DUMMY_HASH, value)
    except (VerificationError, InvalidHashError):
        return False


def new_session(repository, user_id):
    token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(seconds=SESSION_SECONDS)
    repository.create_session(user_id, token_hash(token), expires)
    return token, expires
