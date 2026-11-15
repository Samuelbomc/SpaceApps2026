"""Descubrimiento CMR compartido por las seis fuentes de productos satelitales."""

from packages.contracts.models import ANTIOQUIA_ORIENTE, BoundingBox, DateRange, GeoPoint
from pipelines.ingestion.http import IngestionError, JsonHTTPClient, utc_now

from .catalog import PRODUCTS, Product


def data_links(entry: dict) -> list[str]:
    """Solo GET DATA HTTPS; excluye previews, servicios y enlaces heredados."""
    return list(
        dict.fromkeys(
            link["href"]
            for link in entry.get("links", [])
            if link.get("href", "").startswith("https://")
            and link.get("rel", "").endswith("/data#")
            and not link.get("inherited", False)
        )
    )


class CMRClient:
    BASE = "https://cmr.earthdata.nasa.gov/search"

    def __init__(self, http: JsonHTTPClient | None = None):
        self.http = http if http is not None else JsonHTTPClient()

    def collection(self, product: Product) -> dict:
        payload = self.http.get(
            f"{self.BASE}/collections.json",
            {
                "short_name": product.short_name,
                "version": product.version,
                "provider": product.provider,
                "page_size": 10,
            },
        )
        entries = self._entries(payload)
        if len(entries) != 1:
            raise IngestionError(
                f"Se esperaba una colección para {product.short_name} "
                f"v{product.version}/{product.provider}; se encontraron {len(entries)}."
            )
        return entries[0]

    @staticmethod
    def _entries(payload):
        try:
            entries = payload["feed"]["entry"]
            if not isinstance(entries, list):
                raise TypeError
            return entries
        except (KeyError, TypeError):
            raise IngestionError("Respuesta CMR sin feed.entry válido.") from None

    def search(
        self,
        source: str,
        period: DateRange | None = None,
        bbox: BoundingBox | None = None,
        *,
        point: GeoPoint | None = None,
        limit: int = 20,
        page_size: int = 100,
    ) -> dict:
        if source not in PRODUCTS:
            raise ValueError(f"Fuente CMR desconocida: {source}")
        if not 1 <= limit <= 10000 or not 1 <= page_size <= 2000:
            raise ValueError("limit debe estar entre 1 y 10000; page_size entre 1 y 2000.")
        product = PRODUCTS[source]
        if bbox is not None and point is not None:
            raise ValueError("Selecciona punto o bbox, no ambos.")
        if point is None and bbox is None:
            bbox = ANTIOQUIA_ORIENTE
        if not product.static and period is None:
            raise ValueError("Se requieren fechas para productos temporales.")
        collection = self.collection(product)
        query = {
            "collection_concept_id": collection["id"],
            "sort_key[]": ["start_date", "producer_granule_id"],
        }
        query.update({"point": point.cmr} if point is not None else {"bounding_box": bbox.cmr})
        if not product.static:
            query["temporal"] = period.cmr
        results, seen, page, previous_ids = [], set(), 1, None
        size = min(page_size, limit)
        while len(results) < limit:
            entries = self._entries(
                self.http.get(
                    f"{self.BASE}/granules.json",
                    {
                        **query,
                        "page_size": size,
                        "page_num": page,
                    },
                )
            )
            for entry in entries:
                if entry["id"] not in seen:
                    seen.add(entry["id"])
                    results.append(
                        {
                            "id": entry["id"],
                            "title": entry.get("title"),
                            "start": entry.get("time_start"),
                            "end": entry.get("time_end"),
                            "size_mb_reported": entry.get("granule_size"),
                            "data_urls": data_links(entry),
                            "raw_metadata": entry,
                        }
                    )
                if len(results) == limit:
                    break
            if len(entries) < size:
                break
            if entries and {e["id"] for e in entries} == previous_ids:
                raise IngestionError("CMR repitió una página; búsqueda interrumpida.")
            previous_ids = {e["id"] for e in entries}
            page += 1
        return {
            "schema_version": 1,
            "kind": "granule_catalog",
            "retrieved_at": utc_now(),
            "product": product.as_dict(),
            "collection": collection,
            "bbox": bbox.as_dict() if bbox else None,
            "point": point.as_dict() if point else None,
            "period_requested": period.as_dict() if period else None,
            "temporal_filter_applied": not product.static,
            "query": query,
            "limit": limit,
            "limit_reached": len(results) == limit,
            "granules": results,
            "notes": "La búsqueda devuelve archivos que intersectan el punto o rectángulo. "
            "No recorta píxeles/fechas ni extrae variables científicas. "
            "limit_reached implica que pueden existir más resultados.",
        }
