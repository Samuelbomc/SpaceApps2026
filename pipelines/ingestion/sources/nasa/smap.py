"""Cliente de acceso a SMAP."""

from ._base import CMRSourceClient


class SMAPClient(CMRSourceClient):
    source = "smap"
