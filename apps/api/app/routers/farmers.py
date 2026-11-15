"""Rutas privadas de cuentas, fincas y archivos locales, separadas de NASA pública."""

import hashlib
import hmac
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import APIKeyCookie
from starlette.concurrency import run_in_threadpool

from apps.api.app.repositories.farmers import FarmerRepository
from apps.api.app.services.auth import (
    COOKIE_NAME,
    HASHER,
    SESSION_SECONDS,
    csrf_token,
    hash_password,
    new_session,
    token_hash,
    verify_password,
)
from apps.api.app.services.farm_datasets import (
    MAX_FILE_BYTES,
    MAX_ROWS,
    VARIABLES,
    FarmDatasetService,
)
from packages.contracts.farms import (
    DatasetUploadResult,
    Farm,
    FarmCatalog,
    FarmDataset,
    FarmerSession,
    FarmerUser,
    FarmModelContext,
    FarmWrite,
    LoginRequest,
    RegisterRequest,
)
from pipelines.ingestion.download import file_digest


def farmer_router(database, settings):
    router = APIRouter(prefix="/api/v1", tags=["Cuentas y fincas"])
    cookie_auth = APIKeyCookie(name=COOKIE_NAME, auto_error=False)
    repository = FarmerRepository(database)
    datasets = FarmDatasetService(repository, settings.farm_upload_directory)

    def trusted_origin(request: Request):
        origin = request.headers.get("origin")
        if (origin and origin not in settings.cors_origins) or request.headers.get(
            "sec-fetch-site"
        ) == "cross-site":
            raise HTTPException(403, "Origen de la solicitud no permitido.")

    def rate_limit(request, purpose, email=None):
        host = request.client.host if request.client else "local"
        keys = [(f"{purpose}:ip:{host}", 3600, 100 if purpose == "login" else 20)]
        if email:
            keys.append((f"{purpose}:email:{email}", 900, 10))
        for key, window, maximum in keys:
            if not repository.consume_attempt(
                hashlib.sha256(key.encode()).hexdigest(), window, maximum
            ):
                raise HTTPException(
                    429,
                    "Demasiados intentos. Espera antes de volver a intentarlo.",
                    headers={"Retry-After": str(window)},
                )

    def current(request: Request, session_cookie: str | None = Depends(cookie_auth)):
        token = session_cookie or ""
        row = repository.session(token_hash(token)) if len(token) == 43 else None
        if row is None:
            raise HTTPException(401, "Inicia sesión para acceder a tus fincas.")
        return row

    def write_session(
        request: Request,
        session=Depends(current),
        provided: str = Header(default="", alias="X-CSRF-Token"),
    ):
        trusted_origin(request)
        if (
            not provided.isascii()
            or len(provided) != 64
            or not hmac.compare_digest(provided, csrf_token(request.cookies[COOKIE_NAME]))
        ):
            raise HTTPException(
                403, "La sesión necesita actualizarse. Recarga la página e inténtalo de nuevo."
            )
        return session

    def own_farm(session, farm_id):
        farm = repository.farm(session["user_id"], farm_id)
        if farm is None:
            raise HTTPException(404, "Finca no encontrada.")
        return farm

    def dataset_public(row):
        return FarmDataset(
            **{
                key: row[key]
                for key in (
                    "dataset_id",
                    "farm_id",
                    "original_filename",
                    "sha256",
                    "row_count",
                    "first_date",
                    "last_date",
                    "variables",
                    "created_at",
                )
            }
        )

    def establish(response, user):
        token, expires = new_session(repository, user["user_id"])
        response.set_cookie(
            COOKIE_NAME,
            token,
            max_age=SESSION_SECONDS,
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite="lax",
            path="/",
        )
        response.headers["Cache-Control"] = "no-store"
        return FarmerSession(
            user=FarmerUser(**{key: user[key] for key in FarmerUser.model_fields}),
            csrf_token=csrf_token(token),
            expires_at=expires,
        )

    @router.post("/auth/register", response_model=FarmerSession, status_code=201)
    def register(body: RegisterRequest, request: Request, response: Response):
        trusted_origin(request)
        rate_limit(request, "register")
        user = repository.create_user(
            str(body.email), body.display_name, hash_password(body.password.get_secret_value())
        )
        if user is None:
            raise HTTPException(409, "Ya existe una cuenta con ese correo. Inicia sesión.")
        return establish(response, user)

    @router.post("/auth/login", response_model=FarmerSession)
    def login(body: LoginRequest, request: Request, response: Response):
        trusted_origin(request)
        rate_limit(request, "login", str(body.email))
        user = repository.user_by_email(str(body.email))
        valid = verify_password(
            body.password.get_secret_value(), user["password_hash"] if user else None
        )
        if not valid or user is None:
            raise HTTPException(401, "Correo o contraseña incorrectos.")
        if HASHER.check_needs_rehash(user["password_hash"]):
            repository.rehash(user["user_id"], hash_password(body.password.get_secret_value()))
        return establish(response, user)

    @router.get("/auth/me", response_model=FarmerSession)
    def me(request: Request, response: Response, session=Depends(current)):
        response.headers["Cache-Control"] = "no-store"
        return FarmerSession(
            user=FarmerUser(**{key: session[key] for key in FarmerUser.model_fields}),
            csrf_token=csrf_token(request.cookies[COOKIE_NAME]),
            expires_at=session["expires_at"],
        )

    @router.post("/auth/logout", status_code=204)
    def logout(request: Request, response: Response, session=Depends(write_session)):
        repository.revoke_session(token_hash(request.cookies[COOKIE_NAME]))
        response.delete_cookie(
            COOKIE_NAME, httponly=True, secure=settings.auth_cookie_secure, samesite="lax", path="/"
        )

    @router.get("/farms/catalog", response_model=FarmCatalog)
    def catalog(session=Depends(current)):
        return {
            "soil_textures": [
                {"value": k, "label": v}
                for k, v in [
                    ("unknown", "No lo sé"),
                    ("sandy", "Arenoso"),
                    ("clay", "Arcilloso"),
                    ("loam", "Franco"),
                    ("silty", "Limoso"),
                ]
            ],
            "irrigation_types": [
                {"value": k, "label": v}
                for k, v in [
                    ("unknown", "Sin especificar"),
                    ("rainfed", "Solo lluvia"),
                    ("drip", "Goteo"),
                    ("sprinkler", "Aspersión"),
                    ("flood", "Inundación"),
                    ("other", "Otro"),
                ]
            ],
            "variables": VARIABLES,
            "max_file_bytes": MAX_FILE_BYTES,
            "max_rows": MAX_ROWS,
            "required_columns": ["date", "variable", "value", "unit"],
            "optional_columns": ["crop"],
        }

    @router.get("/farms", response_model=list[Farm])
    def farms(session=Depends(current)):
        return repository.farms(session["user_id"])

    @router.post("/farms", response_model=Farm, status_code=201)
    def create(body: FarmWrite, session=Depends(write_session)):
        farm = repository.create_farm(session["user_id"], body.model_dump(mode="json"))
        if farm is None:
            raise HTTPException(409, "Tu cuenta admite hasta 20 fincas.")
        return farm

    @router.get("/farms/{farm_id}", response_model=Farm)
    def farm(farm_id: UUID, session=Depends(current)):
        return own_farm(session, farm_id)

    @router.put("/farms/{farm_id}", response_model=Farm)
    def update(
        farm_id: UUID, body: FarmWrite, revision: int = Query(ge=1), session=Depends(write_session)
    ):
        own_farm(session, farm_id)
        farm = repository.update_farm(
            session["user_id"], farm_id, body.model_dump(mode="json"), revision
        )
        if farm is None:
            raise HTTPException(409, "La ficha cambió en otra ventana. Recárgala antes de guardar.")
        return farm

    @router.get("/farms/{farm_id}/datasets", response_model=list[FarmDataset])
    def list_datasets(farm_id: UUID, session=Depends(current)):
        own_farm(session, farm_id)
        return [dataset_public(row) for row in repository.datasets(session["user_id"], farm_id)]

    @router.post("/farms/{farm_id}/datasets", response_model=DatasetUploadResult)
    async def upload(
        farm_id: UUID, file: UploadFile, response: Response, session=Depends(write_session)
    ):
        try:
            await run_in_threadpool(own_farm, session, farm_id)
            content = await file.read(MAX_FILE_BYTES + 1)
            if len(content) > MAX_FILE_BYTES:
                raise HTTPException(413, "El CSV no puede superar 5 MiB.")
            # El parseo y SQL son operaciones bloqueantes: ejecutarlas fuera del event loop.
            record, duplicate = await run_in_threadpool(
                datasets.upload, session["user_id"], farm_id, file.filename, content
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        except OSError:
            raise HTTPException(
                507,
                "No se pudo guardar el archivo local. Revisa el espacio y permisos del servidor.",
            ) from None
        finally:
            await file.close()
        response.status_code = 200 if duplicate else 201
        return DatasetUploadResult(dataset=dataset_public(record), duplicate=duplicate)

    @router.get(
        "/farms/{farm_id}/datasets/{dataset_id}/download",
        response_class=FileResponse,
        responses={
            200: {
                "description": "CSV original autorizado",
                "content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}},
            }
        },
    )
    def download(farm_id: UUID, dataset_id: UUID, session=Depends(current)):
        row = repository.dataset(session["user_id"], farm_id, dataset_id)
        if row is None:
            raise HTTPException(404, "Dataset no encontrado.")
        path = datasets.path(row["storage_key"])
        if not path.is_file():
            raise HTTPException(404, "El archivo local no está disponible.")
        if file_digest(path) != row["sha256"]:
            raise HTTPException(
                409,
                "El archivo local cambió desde su carga. Carga una nueva copia para conservar su procedencia.",
            )
        return FileResponse(
            path,
            media_type="text/csv",
            filename=row["original_filename"],
            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
        )

    @router.delete("/farms/{farm_id}/datasets/{dataset_id}", status_code=204)
    def remove_dataset(farm_id: UUID, dataset_id: UUID, session=Depends(write_session)):
        removed = repository.delete_dataset(session["user_id"], farm_id, dataset_id)
        if removed is None:
            raise HTTPException(404, "Dataset no encontrado.")
        try:
            datasets.path(removed["storage_key"]).unlink(missing_ok=True)
        except OSError:
            # Ya no se sirve ni se usa en features; un administrador puede limpiar el archivo huérfano.
            pass

    @router.get("/farms/{farm_id}/model-context", response_model=FarmModelContext)
    def model_context(farm_id: UUID, session=Depends(current)):
        own_farm(session, farm_id)
        cutoff = datetime.now(ZoneInfo("America/Bogota")).date()
        return datasets.bundle(session["user_id"], farm_id, cutoff).context

    return router
