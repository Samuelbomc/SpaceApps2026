"""Cuentas privadas, catálogo de finca y procedencia de observaciones locales."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field, FiniteFloat, SecretStr, field_validator, model_validator

from .api import Contract


class RegisterRequest(Contract):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=100)
    password: SecretStr = Field(min_length=15, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return str(value).lower()

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("Escribe tu nombre.")
        return value.strip()


class LoginRequest(Contract):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return str(value).lower()


class FarmerUser(Contract):
    user_id: UUID
    email: str
    display_name: str
    created_at: datetime


class FarmerSession(Contract):
    user: FarmerUser
    csrf_token: str
    expires_at: datetime


class FarmBoundary(Contract):
    west: FiniteFloat = Field(ge=-180, le=180)
    south: FiniteFloat = Field(ge=-80, le=80)
    east: FiniteFloat = Field(ge=-180, le=180)
    north: FiniteFloat = Field(ge=-80, le=80)

    @model_validator(mode="after")
    def ordered(self):
        if self.west >= self.east or self.south >= self.north:
            raise ValueError("Los límites del área no son válidos.")
        return self


class FarmPolygon(Contract):
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[tuple[FiniteFloat, FiniteFloat]]]

    @model_validator(mode="after")
    def valid_ring(self):
        if len(self.coordinates) != 1 or not 4 <= len(self.coordinates[0]) <= 501:
            raise ValueError("El polígono debe tener un anillo exterior de 3 a 500 vértices.")
        ring = self.coordinates[0]
        if ring[0] != ring[-1] or len(set(ring[:-1])) != len(ring) - 1:
            raise ValueError("El anillo debe cerrarse y no repetir vértices.")
        if any(abs(lon) > 180 or abs(lat) > 80 for lon, lat in ring):
            raise ValueError("Coordenadas fuera del área admitida.")
        if max(p[0] for p in ring) - min(p[0] for p in ring) > 180:
            raise ValueError("No se admiten polígonos que crucen el antimeridiano.")

        def turn(a, b, c):
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        def on(a, b, p):
            return min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(
                a[1], b[1]
            )

        def intersects(a, b, c, d):
            x, y, z, w = turn(a, b, c), turn(a, b, d), turn(c, d, a), turn(c, d, b)
            return (x * y < 0 and z * w < 0) or any(
                v == 0 and on(p, q, r)
                for v, p, q, r in ((x, a, b, c), (y, a, b, d), (z, c, d, a), (w, c, d, b))
            )

        count = len(ring) - 1
        for i in range(count):
            for j in range(i + 1, count):
                if j == i + 1 or (i == 0 and j == count - 1):
                    continue
                if intersects(ring[i], ring[i + 1], ring[j], ring[j + 1]):
                    raise ValueError("Los lados del polígono no pueden cruzarse.")
        if (
            abs(
                sum(
                    (ring[i][0] - ring[0][0]) * (ring[i + 1][1] - ring[0][1])
                    - (ring[i + 1][0] - ring[0][0]) * (ring[i][1] - ring[0][1])
                    for i in range(count)
                )
            )
            < 1e-15
        ):
            raise ValueError("El polígono debe tener superficie positiva.")
        return self


class FarmWrite(Contract):
    name: str = Field(min_length=1, max_length=120)
    municipality: str = Field(default="", max_length=120)
    latitude: FiniteFloat = Field(ge=-80, le=80)
    longitude: FiniteFloat = Field(ge=-180, le=180)
    area_ha: FiniteFloat = Field(gt=0, le=1_000_000)
    boundary: FarmBoundary | None = None
    geometry: FarmPolygon | None = None
    altitude_m: FiniteFloat | None = Field(default=None, ge=-500, le=9000)
    soil_texture: Literal["unknown", "sandy", "clay", "loam", "silty"] = "unknown"
    soil_ph: FiniteFloat | None = Field(default=None, ge=0, le=14)
    irrigation: Literal["unknown", "rainfed", "drip", "sprinkler", "flood", "other"] = "unknown"
    current_crops: list[str] = Field(default_factory=list, max_length=20)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def center_inside_boundary(self):
        if self.geometry:
            ring = self.geometry.coordinates[0]
            derived = FarmBoundary(
                west=min(p[0] for p in ring),
                east=max(p[0] for p in ring),
                south=min(p[1] for p in ring),
                north=max(p[1] for p in ring),
            )
            if self.boundary and any(
                abs(getattr(self.boundary, key) - getattr(derived, key)) > 1e-7
                for key in ("west", "east", "south", "north")
            ):
                raise ValueError("El bbox debe corresponder al polígono guardado.")
            self.boundary = derived
        if self.boundary and not (
            self.boundary.west <= self.longitude <= self.boundary.east
            and self.boundary.south <= self.latitude <= self.boundary.north
        ):
            raise ValueError("El centro de la finca debe quedar dentro del área delimitada.")
        return self

    @field_validator("name")
    @classmethod
    def nonempty_name(cls, value):
        if not value.strip():
            raise ValueError("La finca necesita un nombre.")
        return value.strip()

    @field_validator("current_crops")
    @classmethod
    def crop_names(cls, values):
        if any(not value.strip() or len(value) > 80 for value in values):
            raise ValueError("Cada cultivo debe tener entre 1 y 80 caracteres.")
        return list(dict.fromkeys(value.strip() for value in values))


class Farm(FarmWrite):
    farm_id: UUID
    revision: int
    created_at: datetime
    updated_at: datetime


class FarmDataset(Contract):
    dataset_id: UUID
    farm_id: UUID
    original_filename: str
    sha256: str
    row_count: int
    first_date: date
    last_date: date
    variables: list[str]
    created_at: datetime
    quality: Literal["format_validated_unverified"] = "format_validated_unverified"
    date_basis: Literal["America/Bogota local calendar"] = "America/Bogota local calendar"


class DatasetUploadResult(Contract):
    dataset: FarmDataset
    duplicate: bool


class LocalObservation(Contract):
    dataset_id: UUID
    date: date
    variable: str
    value: FiniteFloat
    unit: str
    crop: str = ""
    source: Literal["LOCAL_FARM"] = "LOCAL_FARM"
    quality: Literal["format_validated_unverified"] = "format_validated_unverified"


class FarmModelContext(Contract):
    farm: Farm
    dataset_ids: list[UUID]
    dataset_versions: list[FarmDataset] = Field(default_factory=list)
    observation_count: int
    available_through: date | None
    conflict_count: int
    snapshot_id: str
    model_ready: Literal[False] = False
    nasa_status: Literal["not_ingested_for_farm"] = "not_ingested_for_farm"
    limitations: list[str]


class FarmFeatureBundle(Contract):
    context: FarmModelContext
    observations: list[LocalObservation]


class CatalogOption(Contract):
    value: str
    label: str


class LocalVariable(Contract):
    variable: str
    label: str
    unit: str
    aggregation: str
    minimum: FiniteFloat | None = None
    maximum: FiniteFloat | None = None


class FarmCatalog(Contract):
    soil_textures: list[CatalogOption]
    irrigation_types: list[CatalogOption]
    variables: list[LocalVariable]
    max_file_bytes: int
    max_rows: int
    required_columns: list[str]
    optional_columns: list[str]
