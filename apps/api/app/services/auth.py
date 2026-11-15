"""Contraseñas Argon2id, sesiones opacas y CSRF ligado a la sesión."""
import hashlib
import hmac
import secrets
import threading
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError

HASHER = PasswordHasher()
HASH_SLOTS = threading.BoundedSemaphore(4)


def hash_password(value):
    with HASH_SLOTS:
        return HASHER.hash(value)


DUMMY_HASH = hash_password(secrets.token_urlsafe(32))
COOKIE_NAME = 'fieldshift_session'
SESSION_SECONDS = 7 * 86400


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_token(value):
    return hmac.new(value.encode(), b'fieldshift-csrf-v1', hashlib.sha256).hexdigest()


def verify_password(value, encoded):
    try:
        with HASH_SLOTS:
            return HASHER.verify(encoded or DUMMY_HASH, value)
    except (VerificationError, InvalidHashError):
        return False


def new_session(repository, user_id):
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(seconds=SESSION_SECONDS)
    repository.create_session(user_id, token_hash(token), expires)
    return token, expires
