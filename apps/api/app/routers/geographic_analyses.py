"""Acceso público: HTTP encola geometrías y lee resultados, sin ejecutar ML."""

import hashlib
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from apps.api.app.repositories.farmers import FarmerRepository
from apps.api.app.repositories.geographic_analyses import GeographicAnalysisRepository
from packages.contracts.geographic_analysis import GeographicAnalysis, GeographicAnalysisRequest


def geographic_analysis_router(database, access, results):
    router = APIRouter(prefix="/api/v1/geographic-analyses", tags=["Análisis geográfico"])
    repository = GeographicAnalysisRepository(database)

    @router.post(
        "",
        response_model=GeographicAnalysis,
        status_code=202,
        dependencies=[Depends(access.trusted_origin)],
    )
    def enqueue(body: GeographicAnalysisRequest, request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        peer = request.client.host if request.client else "unknown"
        bucket = "geographic:" + hashlib.sha256(peer.encode()).hexdigest()
        if not FarmerRepository(database).consume_attempt(bucket, 3600, 60):
            raise HTTPException(
                429,
                "Límite de solicitudes alcanzado; intenta más tarde.",
                headers={"Retry-After": "3600"},
            )
        try:
            identifier = repository.enqueue(body, datetime.now(ZoneInfo("America/Bogota")).date())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        except OverflowError as exc:
            raise HTTPException(429, str(exc), headers={"Retry-After": "60"}) from None
        return repository.get(identifier, results)

    @router.get("/{request_id}", response_model=GeographicAnalysis)
    def status(request_id: UUID, response: Response):
        response.headers["Cache-Control"] = "no-store"
        item = repository.get(request_id, results)
        if item is None:
            raise HTTPException(404, "Solicitud no encontrada.")
        return item

    return router
