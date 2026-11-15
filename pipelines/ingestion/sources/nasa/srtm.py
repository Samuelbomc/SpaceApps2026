"""Cliente de acceso a elevación SRTM."""

from ._base import CMRSourceClient


class SRTMClient(CMRSourceClient):
    source = "srtm"
