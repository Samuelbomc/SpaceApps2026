"""Geocodificación inversa del mapa público; no crea regiones ni ingestas."""

from fastapi import APIRouter, HTTPException, Query

from apps.api.app.services.map_places import PlaceLookupBusy, PlaceLookupUnavailable
from packages.contracts.api import MapPlace


def map_places_router(service):
    router = APIRouter(prefix="/api/v1/places", tags=["Map places"])

    @router.get("/reverse", response_model=MapPlace)
    def reverse(latitude: float = Query(ge=-90, le=90, allow_inf_nan=False),
                longitude: float = Query(ge=-180, le=180, allow_inf_nan=False)):
        try:
            return service.resolve(latitude, longitude)
        except PlaceLookupBusy:
            raise HTTPException(429, "Espera un momento para consultar otro lugar.", headers={"Retry-After": "2"}) from None
        except PlaceLookupUnavailable:
            raise HTTPException(503, "No se pudo identificar el lugar en el mapa.", headers={"Retry-After": "2"}) from None

    return router
