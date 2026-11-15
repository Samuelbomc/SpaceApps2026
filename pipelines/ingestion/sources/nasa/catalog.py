"""Productos explícitos y versionados, comprobados contra CMR el 2026-11-14."""

from dataclasses import asdict, dataclass

from packages.contracts.query import DEFAULT_POWER_PARAMETERS as POWER_PARAMETERS

__all__ = ["POWER_DOCS", "POWER_PARAMETERS", "PRODUCTS", "Product"]


@dataclass(frozen=True)
class Product:
    source: str
    short_name: str
    version: str
    provider: str
    resolution: str
    cadence: str
    variables: tuple[str, ...]
    documentation: str
    notes: str
    static: bool = False

    def as_dict(self):
        return asdict(self)


PRODUCTS = {
    "gpm": Product(
        "gpm",
        "GPM_3IMERGDF",
        "07",
        "GES_DISC",
        "0.1 degree",
        "daily",
        ("precipitation",),
        "https://gpm.nasa.gov/data/imerg",
        "IMERG Final: histórico con latencia de meses; no es pronóstico ni producto operativo inmediato.",
    ),
    "smap": Product(
        "smap",
        "SPL4SMGP",
        "008",
        "NSIDC_CPRD",
        "9 km",
        "3-hourly",
        ("sm_surface", "sm_rootzone"),
        "https://nsidc.org/data/spl4smgp/versions/8",
        "L4 combina asimilación y modelo: humedad superficial y radicular estimadas; no fertilidad química.",
    ),
    "srtm": Product(
        "srtm",
        "SRTMGL1",
        "003",
        "LPCLOUD",
        "1 arc-second (~30 m)",
        "static (February 2000)",
        ("elevation",),
        "https://www.earthdata.nasa.gov/data/catalog/lpcloud-srtmgl1-003",
        "DEM estático: se ignora el intervalo temporal de la consulta. Pendiente se debe derivar del DEM.",
        True,
    ),
    "grace": Product(
        "grace",
        "TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4",
        "RL06.3Mv04",
        "POCLOUD",
        "3-degree mascons, sampled on 0.5-degree grid",
        "monthly (multi-time file)",
        ("lwe_thickness", "uncertainty"),
        "https://podaac.jpl.nasa.gov/dataset/TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4",
        "Anomalías regionales de almacenamiento total (cm de agua equivalente), no humedad de parcela. "
        "El archivo contiene múltiples fechas; filtrar el catálogo no recorta su contenido.",
    ),
    "ecostress": Product(
        "ecostress",
        "ECO_L3T_JET",
        "003",
        "LPCLOUD",
        "70 m",
        "irregular overpasses",
        ("ETdaily", "PTJPLSMinst", "ETuncertainty", "cloud", "water"),
        "https://doi.org/10.5067/ECOSTRESS/ECO_L3T_JET.003",
        "Evapotranspiración: consultar unidades, escalas y máscaras de cada capa; no asumir mm/día.",
    ),
    "ecostress-lst": Product(
        "ecostress",
        "ECO_L2T_LSTE",
        "003",
        "LPCLOUD",
        "70 m",
        "irregular overpasses",
        ("LST", "QC", "cloud", "water"),
        "https://doi.org/10.5067/ECOSTRESS/ECO_L2T_LSTE.003",
        "Temperatura superficial y emisividad; no equivale a temperatura del aire.",
    ),
    "landsat": Product(
        "landsat",
        "HLSL30",
        "2.0",
        "LPCLOUD",
        "30 m",
        "Landsat overpasses",
        ("B04 (red)", "B05 (NIR)", "Fmask"),
        "https://hls.gsfc.nasa.gov/documents/",
        "HLSL30 es el producto NASA derivado de Landsat 8/9, no Landsat Collection 2 original. "
        "NDVI se deriva de reflectancias con escalas, nodata y máscara de nubes aplicadas.",
    ),
}


POWER_DOCS = "https://power.larc.nasa.gov/docs/services/api/temporal/daily/"
