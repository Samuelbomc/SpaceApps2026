"""Envoltorio de resultados externos; separado de los contratos compartidos."""

from packages.contracts import DataQuery, SourceResult
from pipelines.ingestion.sources.nasa.catalog import POWER_DOCS, PRODUCTS


def source_result(source: str, query: DataQuery, payload: dict | None,
                  *, error: str | None = None) -> SourceResult:
    product = PRODUCTS.get(source)
    metadata = {
        "product": product.as_dict() if product else {"source": "power", "documentation": POWER_DOCS},
        "spatial_resolution": product.resolution if product else "meteorology 0.5 x 0.625 degree; solar 1 x 1 degree",
        "temporal_resolution": product.cadence if product else "daily",
        "temporal_filter_applied": not (product and product.static) if payload is not None else None,
        "spatial_alignment_applied": False, "temporal_alignment_applied": False,
        "spatial_selection": ("granule_intersection" if product else
                              "provider_point_sample" if query.point else "provider_regional_window"),
    }
    if payload is not None:
        metadata["effective_query"] = payload.get("query") if product else [
            item.get("query") for item in payload.get("raw_responses", [])]
        metadata["retrieved_at"] = payload.get("retrieved_at")
    if product:
        available = bool(payload and payload.get("granules"))
    else:
        available = any(
            series for item in (payload or {}).get("raw_responses", [])
            for feature in item["response"].get("features", [item["response"]])
            for series in feature.get("properties", {}).get("parameter", {}).values()
        )
    return {"query_id": query.query_id, "source": source,
            "status": "error" if error is not None else "ok" if available else "empty",
            "data_kind": "granule_catalog" if product else "provider_response",
            "requested": query.as_dict(), "metadata": metadata, "data": payload, "error": error}
