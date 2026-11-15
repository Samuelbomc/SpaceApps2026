"""Cliente de acceso a GPM IMERG."""

from ._base import CMRSourceClient


class GPMClient(CMRSourceClient):
    source = "gpm"
