"""FastAPI: contrato v1 y consulta de resultados almacenados."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.app.config import Settings
from apps.api.app.db.postgres import Database, DatabaseUnavailable
from apps.api.app.middleware import PrivateRequestLimits
from apps.api.app.repositories.mongo import DocumentStoreUnavailable
from apps.api.app.repositories.operational import OperationalRepository
from apps.api.app.repositories.runtime import runtime_stores
from apps.api.app.routers.crop_catalog import router as crop_catalog_router
from apps.api.app.routers.farmers import farmer_router
from apps.api.app.routers.manual_updates import manual_update_router
from apps.api.app.routers.map_places import map_places_router
from apps.api.app.services.analysis import AnalysisService
from apps.api.app.services.map_places import MapPlaceService
from apps.api.app.services.session_access import session_access
from ml.inference.expanded import ExpandedModelBundle
from packages.contracts.api import (
    AnalysisRequest,
    AnalysisResult,
    Observation,
    ObservationPage,
    Region,
    StatusResponse,
)
from packages.contracts.pretrained import ModelCatalog
from packages.contracts.training import AutomationStatus


def create_app(
    repository=None,
    analysis_service=None,
    settings=None,
    results_repository=None,
    model_registry=None,
    place_service=None,
    pretrained_models=None,
):
    settings = settings or Settings.from_env()
    repository = (
        repository
        if repository is not None
        else OperationalRepository(Database(settings.database_url))
    )
    analysis_service = analysis_service or AnalysisService(repository)
    pretrained_models = (
        pretrained_models
        if pretrained_models is not None
        else ExpandedModelBundle(settings.pretrained_model_directory)
    )
    if results_repository is None or model_registry is None:
        default_results, default_registry = runtime_stores(settings, repository)
        results_repository = (
            results_repository if results_repository is not None else default_results
        )
        model_registry = model_registry if model_registry is not None else default_registry
    app = FastAPI(
        title="AgroGeo API",
        version="1.0.0",
        description="Ingesta NASA y contratos de análisis agrícola",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
        allow_credentials=True,
    )
    app.add_middleware(PrivateRequestLimits)
    database = getattr(repository, "database", None) or Database(settings.database_url)
    access = session_access(database, settings)
    app.include_router(farmer_router(database, settings, access=access))
    app.include_router(manual_update_router(database, access))
    app.include_router(
        map_places_router(
            place_service if place_service is not None else MapPlaceService(settings.geocoder_url)
        )
    )
    app.include_router(crop_catalog_router)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        if request.url.path.startswith(("/api/v1/auth/", "/api/v1/farms")):
            return JSONResponse(
                status_code=422,
                content={
                    "detail": [
                        {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
                        for error in exc.errors()
                    ]
                },
            )
        return await request_validation_exception_handler(request, exc)

    @app.exception_handler(DatabaseUnavailable)
    async def database_unavailable(request, exc):
        return JSONResponse(
            status_code=503, content={"detail": str(exc), "code": "database_unavailable"}
        )

    @app.exception_handler(DocumentStoreUnavailable)
    async def document_store_unavailable(request, exc):
        return JSONResponse(
            status_code=503, content={"detail": str(exc), "code": "results_store_unavailable"}
        )

    def require_region(region_id):
        if repository.region(region_id) is None:
            raise HTTPException(404, "Región no encontrada")

    def model_catalog():
        try:
            return pretrained_models.catalog()
        except (OSError, ValueError, KeyError):
            raise HTTPException(
                503, "No se pudieron verificar los artefactos XGBoost integrados."
            ) from None

    @app.get("/api/v1/models", response_model=ModelCatalog)
    def models():
        # Solo metadatos JSON y hashes; HTTP no carga Boosters ni ejecuta inferencias.
        return model_catalog()

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "api_version": "1.0.0"}

    @app.get("/api/v1/regions", response_model=list[Region])
    def regions():
        return repository.regions()

    @app.get("/api/v1/status", response_model=StatusResponse)
    def status():
        available = {model.model_kind for model in model_catalog().models}
        return {
            "climate_model": "configured"
            if analysis_service.climate or "climate" in available
            else "not_configured",
            "soil_model": "configured"
            if analysis_service.soil or "soil" in available
            else "not_configured",
            "recommendations": "configured"
            if analysis_service.recommendations
            else "not_configured",
            "schedule": repository.schedule(),
            "recent_runs": repository.recent_runs(),
        }

    @app.get("/api/v1/regions/{region_id}/observations", response_model=ObservationPage)
    def observations(
        region_id: str,
        start: date | None = None,
        end: date | None = None,
        limit: int = Query(1000, ge=1, le=10000),
        offset: int = Query(0, ge=0),
    ):
        require_region(region_id)
        if start is None and end is None:
            page = repository.observation_page(region_id, limit, offset)
            return {
                **page,
                "region_id": region_id,
                "limit": limit,
                "offset": offset,
                "items": [
                    Observation(**{k: row[k] for k in Observation.model_fields})
                    for row in page["items"]
                ],
            }
        if start is None or end is None:
            raise HTTPException(422, "start y end deben enviarse juntos o se pueden omitir ambos")
        if start > end:
            raise HTTPException(422, "start debe ser anterior o igual a end")
        if offset:
            raise HTTPException(
                422, "La paginación con offset se utiliza al consultar el histórico completo"
            )
        rows = repository.observations(region_id, start, end, limit)
        return {
            "region_id": region_id,
            "limit": limit,
            "items": [Observation(**{k: row[k] for k in Observation.model_fields}) for row in rows],
        }

    @app.get("/api/v1/regions/{region_id}/analyses", response_model=list[AnalysisResult])
    def analyses(region_id: str, limit: int = Query(10, ge=1, le=100)):
        require_region(region_id)
        return results_repository.analyses(region_id, limit)

    @app.get("/api/v1/automation", response_model=AutomationStatus)
    def automation():
        return {
            "results_backend": settings.results_backend,
            "schedules": repository.schedules(),
            "published_models": model_registry.published_models(),
            "recent_training": model_registry.recent_training(),
            "limitations": [
                "Los modelos requieren features, etiquetas verificadas y umbrales de promoción configurados.",
                "Los CSV privados no se incorporan al entrenamiento regional sin validación y autorización.",
            ],
        }

    def read_analysis(request: AnalysisRequest):
        stored = results_repository.analysis_for(request)
        if stored is not None:
            return AnalysisResult.model_validate(stored)
        if analysis_service.climate is None or analysis_service.soil is None:
            catalog = model_catalog()
            if request.horizon_days in catalog.supported_horizons:
                return AnalysisResult(
                    status="pending_run",
                    request=request,
                    messages=[
                        "Modelos XGBoost integrados. El job debe generar el resultado con las variables procesadas de esta región y fecha."
                    ],
                )
            return AnalysisResult(
                status="pending_model",
                request=request,
                messages=[
                    "Este plazo no tiene modelos conectados. Horizontes disponibles: "
                    + ", ".join(map(str, catalog.supported_horizons))
                    + " días."
                    if catalog.models
                    else "Los modelos climático y de suelo aún no están configurados."
                ],
            )
        return AnalysisResult(
            status="pending_run",
            request=request,
            messages=["El resultado todavía no ha sido generado por el job de análisis."],
        )

    @app.get("/api/v1/regions/{region_id}/latest-analysis", response_model=AnalysisResult | None)
    def latest_analysis(
        region_id: str, horizon_days: int = Query(7, ge=1, le=90), as_of: date | None = None
    ):
        require_region(region_id)
        today = datetime.now(ZoneInfo("America/Bogota")).date()
        requested_on = as_of or today
        if requested_on > today:
            raise HTTPException(422, "as_of no puede ser posterior al día de la consulta")
        # El corte de features del modelo puede ser anterior al último dato de otra fuente.
        # Se busca primero el periodo exacto; nunca se devuelve un pronóstico viejo como actual.
        stored = results_repository.analysis_for_period(region_id, horizon_days, requested_on)
        if isinstance(stored, dict):
            result = AnalysisResult.model_validate(stored)
            if (
                result.request.region_id != region_id
                or result.request.horizon_days != horizon_days
                or result.request.forecast_start_date != requested_on
            ):
                raise HTTPException(
                    503, "El resultado almacenado no corresponde al periodo solicitado."
                )
            return result
        reference = repository.latest_observation_date(region_id, requested_on)
        if reference is None:
            return None
        return read_analysis(
            AnalysisRequest(
                region_id=region_id,
                reference_date=reference,
                horizon_days=horizon_days,
                forecast_start_date=requested_on,
            )
        )

    @app.post("/api/v1/analyses", response_model=AnalysisResult)
    def analyze(request: AnalysisRequest):
        require_region(request.region_id)
        if request.reference_date >= datetime.now(UTC).date():
            raise HTTPException(422, "reference_date debe ser un día histórico completado")
        return read_analysis(request)

    return app


app = create_app()
