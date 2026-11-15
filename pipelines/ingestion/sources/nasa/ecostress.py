"""Cliente de acceso a productos ET y LST de ECOSTRESS."""

from ._base import CMRSourceClient
from ._cmr import CMRClient


class ECOSTRESSClient(CMRSourceClient):
    def __init__(self, cmr: CMRClient | None = None, *, product: str = "et"):
        if product not in ("et", "lst"):
            raise ValueError("Producto ECOSTRESS inválido; usa 'et' o 'lst'.")
        super().__init__(cmr)
        self.source = "ecostress" if product == "et" else "ecostress-lst"
