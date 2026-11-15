"""Dependencias HTTP de sesión y CSRF compartidas por escrituras privadas y jobs."""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import APIKeyCookie

from apps.api.app.repositories.farmers import FarmerRepository
from apps.api.app.services.auth import COOKIE_NAME, session_token, token_hash, valid_csrf


@dataclass(frozen=True)
class SessionAccess:
    current: Callable
    write: Callable
    trusted_origin: Callable


def session_access(database, settings):
    repository = FarmerRepository(database)
    cookie_auth = APIKeyCookie(name=COOKIE_NAME, auto_error=False)

    def trusted_origin(request: Request):
        origin = request.headers.get("origin")
        if (origin and origin not in settings.cors_origins) or request.headers.get(
            "sec-fetch-site"
        ) == "cross-site":
            raise HTTPException(403, "Origen de la solicitud no permitido.")

    def current(request: Request, session_cookie: str | None = Depends(cookie_auth)):
        token = session_cookie if session_cookie is not None else session_token(request.cookies)
        row = repository.session(token_hash(token)) if len(token) == 43 else None
        if row is None:
            raise HTTPException(401, "Inicia sesión para realizar esta acción.")
        return row

    def write(
        request: Request,
        session=Depends(current),
        provided: str = Header(default="", alias="X-CSRF-Token"),
    ):
        trusted_origin(request)
        if not valid_csrf(session_token(request.cookies), provided):
            raise HTTPException(
                403, "La sesión necesita actualizarse. Recarga la página e inténtalo de nuevo."
            )
        return session

    return SessionAccess(current, write, trusted_origin)
