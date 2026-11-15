"""Cliente NASA HLSL30 derivado de Landsat 8/9."""

from ._base import CMRSourceClient


class HLSClient(CMRSourceClient):
    source = "landsat"
