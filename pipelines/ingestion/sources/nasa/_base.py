"""Cliente base para productos que comparten el catálogo CMR de NASA."""

from packages.contracts import DataQuery

from ._cmr import CMRClient
from .catalog import PRODUCTS


class CMRSourceClient:
    source: str

    def __init__(self, cmr: CMRClient | None = None):
        self.cmr = cmr if cmr is not None else CMRClient()

    def collection(self) -> dict:
        return self.cmr.collection(PRODUCTS[self.source])

    def search(self, query: DataQuery) -> dict:
        return self.cmr.search(
            self.source,
            query.period,
            query.bbox,
            point=query.point,
            limit=query.limit,
            page_size=query.page_size,
        )
