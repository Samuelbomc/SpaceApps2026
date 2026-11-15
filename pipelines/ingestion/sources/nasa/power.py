"""Series POWER por región: una consulta por variable, en celdas nativas."""

from math import ceil, floor

from .catalog import POWER_DOCS, POWER_PARAMETERS
from pipelines.ingestion.http import IngestionError, JsonHTTPClient, utc_now
from packages.contracts.models import ANTIOQUIA_ORIENTE, BoundingBox, DateRange, GeoPoint


class PowerClient:
    ENDPOINT = "https://power.larc.nasa.gov/api/temporal/daily/regional"

    def __init__(self, http: JsonHTTPClient | None = None):
        self.http = http if http is not None else JsonHTTPClient()

    def fetch_point_daily(self, period: DateRange, point: GeoPoint,
                          parameters=POWER_PARAMETERS) -> dict:
        """Consulta puntual nativa; no crea un bbox ni un radio arbitrario."""
        parameters = tuple(dict.fromkeys(parameters))
        if not 1 <= len(parameters) <= 20 or any(
            not p or not p.replace("_", "").isalnum() for p in parameters
        ):
            raise ValueError("POWER puntual requiere entre 1 y 20 códigos de variable válidos.")
        endpoint = "https://power.larc.nasa.gov/api/temporal/daily/point"
        query = {"parameters": ",".join(parameters), "community": "AG", "format": "JSON",
                 "latitude": point.latitude, "longitude": point.longitude,
                 "start": period.start.strftime("%Y%m%d"),
                 "end": period.end.strftime("%Y%m%d"), "time-standard": "UTC"}
        payload = self.http.get(endpoint, query)
        if "properties" not in payload or "header" not in payload:
            raise IngestionError("POWER devolvió una respuesta puntual sin properties/header.")
        return {"schema_version": 1, "source": "power", "retrieved_at": utc_now(),
                "point": point.as_dict(), "period": period.as_dict(),
                "documentation": POWER_DOCS,
                "raw_responses": [{"query": query, "response": payload}],
                "notes": "Muestreo puntual del proveedor sobre su resolución nativa. "
                         "No implica una medición independiente o resolución de parcela."}

    def fetch_daily(self, period: DateRange, bbox: BoundingBox = ANTIOQUIA_ORIENTE,
                    parameters=POWER_PARAMETERS) -> dict:
        """Consume POWER y conserva el payload del proveedor sin transformaciones."""
        parameters = tuple(dict.fromkeys(parameters))
        if not parameters or any(not p or not p.replace("_", "").isalnum() for p in parameters):
            raise ValueError("Especifica al menos un código de variable POWER válido.")
        # POWER exige >=2 grados en ambos ejes. Expandir a grados enteros evita
        # errores de coma flotante y filtrar después respeta el AOI solicitado.
        west, south, east, north = floor(bbox.west), floor(bbox.south), ceil(bbox.east), ceil(bbox.north)
        west, south = max(-180, min(west, 178)), max(-90, min(south, 88))
        east, north = max(east, west + 2), max(north, south + 2)
        query_bbox = BoundingBox(west, south, east, north)
        responses = []
        for parameter in parameters:
            # El endpoint regional admite UNA variable por petición.
            query = {"parameters": parameter, "community": "AG", "format": "JSON",
                     "latitude-min": query_bbox.south, "latitude-max": query_bbox.north,
                     "longitude-min": query_bbox.west, "longitude-max": query_bbox.east,
                     "start": period.start.strftime("%Y%m%d"),
                     "end": period.end.strftime("%Y%m%d"), "time-standard": "UTC"}
            payload = self.http.get(self.ENDPOINT, query)
            if "features" not in payload or "header" not in payload:
                raise IngestionError("POWER devolvió una respuesta sin features/header.")
            responses.append({"query": query, "response": payload})
        return {"schema_version": 1, "source": "power", "retrieved_at": utc_now(),
                "bbox": bbox.as_dict(), "query_bbox": query_bbox.as_dict(),
                "period": period.as_dict(), "documentation": POWER_DOCS,
                "raw_responses": responses,
                "notes": "Respuestas originales de POWER. La ventana efectiva puede ser "
                         "mayor al bbox solicitado por el mínimo de 2 grados por eje. "
                         "No se filtran puntos, normalizan valores ni construyen features."}
