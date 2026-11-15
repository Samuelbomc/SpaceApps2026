"""HTTP encola y consulta; nunca ejecuta descargas ni entrenamiento en la petición."""

from fastapi import APIRouter, Depends, HTTPException, Response

from apps.api.app.repositories.manual_updates import ManualUpdateRepository, UpdateCooldown
from packages.contracts.manual_update import ManualUpdate


def manual_update_router(database, access):
    router = APIRouter(prefix="/api/v1/automation", tags=["Actualización manual"])
    repository = ManualUpdateRepository(database)

    @router.post("/refresh", status_code=202, response_model=ManualUpdate)
    def enqueue(response: Response, session=Depends(access.write)):
        response.headers["Cache-Control"] = "no-store"
        try:
            return repository.enqueue(session["user_id"])
        except UpdateCooldown as exc:
            raise HTTPException(
                429,
                "Ya se solicitó una actualización recientemente. Espera unos minutos.",
                headers={"Retry-After": str(exc.seconds)},
            ) from None

    @router.get("/refresh", response_model=ManualUpdate | None)
    def latest(response: Response, session=Depends(access.current)):
        response.headers["Cache-Control"] = "no-store"
        return repository.latest()

    return router
