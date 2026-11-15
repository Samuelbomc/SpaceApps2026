"""Repositorio de acceso a los productos ET y LST de ECOSTRESS."""

from pipelines.ingestion.sources.nasa.ecostress import ECOSTRESSClient

from ._satellite import SatelliteRepository


class ECOSTRESSRepository(SatelliteRepository):
    def __init__(self, client: ECOSTRESSClient | None = None, *, product: str = "et"):
        if product not in ("et", "lst"):
            raise ValueError("Producto ECOSTRESS inválido; usa 'et' o 'lst'.")
        self.client = client if client is not None else ECOSTRESSClient(product=product)
        self.source = self.client.source
