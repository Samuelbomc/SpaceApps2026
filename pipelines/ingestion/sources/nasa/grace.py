"""Cliente de acceso a GRACE/GRACE-FO."""

from ._base import CMRSourceClient


class GRACEClient(CMRSourceClient):
    source = "grace"
