"""Límites de cuerpo antes de parsear JSON o almacenar multipart temporal."""

from fastapi import HTTPException
from starlette.responses import JSONResponse

from apps.api.app.services.farm_datasets import MAX_FILE_BYTES


class PrivateRequestLimits:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        private = scope.get("path", "").startswith(("/api/v1/auth/", "/api/v1/farms"))
        if scope["type"] != "http" or not private:
            return await self.app(scope, receive, send)
        upload = scope["method"] == "POST" and scope["path"].endswith("/datasets")
        maximum = MAX_FILE_BYTES + 65536 if upload else 65536
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail": "Content-Length inválido."}, status_code=400)(
                scope, receive, send
            )
        if length < 0 or length > maximum:
            return await JSONResponse(
                {"detail": "La solicitud supera el tamaño permitido."}, status_code=413
            )(scope, receive, send)
        consumed = 0

        async def bounded_receive():
            nonlocal consumed
            message = await receive()
            consumed += len(message.get("body", b""))
            if consumed > maximum:
                raise HTTPException(413, "La solicitud supera el tamaño permitido.")
            return message

        async def private_send(message):
            if message["type"] == "http.response.start":
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"cache-control"
                ]
                message = {
                    **message,
                    "headers": [
                        *headers,
                        (b"cache-control", b"no-store"),
                        (b"x-content-type-options", b"nosniff"),
                    ],
                }
            await send(message)

        await self.app(scope, bounded_receive, private_send)
