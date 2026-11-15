"""Configuración por entorno; no registra secretos ni lee .env implícitamente."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str = "postgresql://fieldshift:fieldshift_dev@localhost:5432/fieldshift"
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")
    auth_cookie_secure: bool = False
    farm_upload_directory: Path = Path("data/farms")
    results_backend: str = "postgresql"
    mongodb_uri: str = "mongodb://127.0.0.1:27017"
    mongodb_database: str = "fieldshift"
    dataset_directory: Path = Path("data/datasets")
    model_directory: Path = Path("data/models")
    geocoder_url: str = "https://photon.komoot.io/reverse"
    pretrained_model_directory: Path = Path('ml/artifacts')
    feature_directory: Path = Path('data/features/expanded-v1')
    rotation_water_rules_path: Path | None = None

    @classmethod
    def from_env(cls):
        return cls(database_url=os.getenv("DATABASE_URL", cls.database_url),
                   cors_origins=tuple(value.strip() for value in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if value.strip()),
                   auth_cookie_secure=os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true",
                   farm_upload_directory=Path(os.getenv("FARM_UPLOAD_DIRECTORY", "data/farms")),
                   results_backend=os.getenv("RESULTS_BACKEND", "postgresql"),
                   mongodb_uri=os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017"),
                   mongodb_database=os.getenv("MONGODB_DATABASE", "fieldshift"),
                   dataset_directory=Path(os.getenv("DATASET_DIRECTORY", "data/datasets")),
                   model_directory=Path(os.getenv("MODEL_DIRECTORY", "data/models")),
                   geocoder_url=os.getenv("GEOCODER_URL", "https://photon.komoot.io/reverse"),
                   pretrained_model_directory=Path(os.getenv('PRETRAINED_MODEL_DIRECTORY', 'ml/artifacts')),
                   feature_directory=Path(os.getenv('FEATURE_DIRECTORY', 'data/features/expanded-v1')),
                   rotation_water_rules_path=Path(os.environ['ROTATION_WATER_RULES_PATH']) if os.getenv('ROTATION_WATER_RULES_PATH') else None)
