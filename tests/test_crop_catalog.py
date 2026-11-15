"""Catálogo real aportado por el usuario y contextos sintéticos de prueba, sin inferencias reales."""

import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock

from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.app.main import create_app
from ml.recommendations.catalog import load_crop_catalog
from ml.recommendations.screening import screen_catalog
from packages.contracts.agronomy import CropScreeningContext
from pipelines.processing.validation.crop_catalog import normalize_crop_catalog

SOURCE = Path("samples/agronomy/ecocrop-user.tsv")


def context(**changes):
    values = {
        "region_id": "test-only",
        "as_of": "2026-11-14",
        "temperature": {
            "mean_c": 23,
            "start": "2026-11-14",
            "end": "2026-11-20",
            "kind": "forecast",
            "source": "synthetic-test",
        },
        "annual_rainfall": {
            "total_mm": 1000,
            "start": "2025-01-01",
            "end": "2025-12-31",
            "valid_days": 365,
            "source": "synthetic-test",
        },
        "soil_ph": 6,
        "altitude_m": 1500,
    }
    return CropScreeningContext.model_validate({**values, **changes})


class CropCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = normalize_crop_catalog(SOURCE.read_bytes())
        self.maize = next(crop for crop in self.catalog.crops if crop.ecocrop_code == 238663)

    def test_import_preserves_twelve_profiles_and_eleven_species_and_all_source_columns(self):
        self.assertEqual(len(self.catalog.crops), 12)
        self.assertEqual(len({crop.ecocrop_code for crop in self.catalog.crops}), 11)
        self.assertEqual(len({crop.crop_id for crop in self.catalog.crops}), 12)
        self.assertTrue(all(len(crop.source_attributes) == 38 for crop in self.catalog.crops))
        self.assertEqual(self.catalog.review_status, "format_validated_agronomic_review_pending")

    def test_decimal_commas_missing_values_and_real_zero_are_distinct(self):
        self.assertEqual(self.maize.soil_ph.absolute.minimum, 4.5)
        self.assertIsNone(self.maize.lethal_temperature_rest_c)
        yam = next(crop for crop in self.catalog.crops if crop.ecocrop_code == 942)
        self.assertIsNone(yam.altitude_max_m)
        self.assertIn("altitude_max_missing", yam.quality_flags)
        cassava = next(crop for crop in self.catalog.crops if crop.ecocrop_code == 1420)
        self.assertEqual(cassava.lethal_temperature_early_growth_c, 0)

    def test_bean_variants_are_not_deduplicated_or_given_invented_species_requirements(self):
        beans = [crop for crop in self.catalog.crops if crop.ecocrop_code == 1668]
        self.assertEqual(len(beans), 2)
        self.assertNotEqual(beans[0].crop_id, beans[1].crop_id)
        self.assertEqual(beans[0].temperature, beans[1].temperature)
        self.assertTrue(
            all(
                "shared_species_requirements_not_variety_specific" in crop.quality_flags
                for crop in beans
            )
        )

    def test_invalid_ranges_and_wrong_source_codes_are_rejected_with_row_context(self):
        source = SOURCE.read_text()
        for changed in (
            source.replace("\t18\t33\t10\t47\t", "\t50\t33\t10\t47\t", 1),
            source.replace("dataSheet?id=238663", "dataSheet?id=123", 1),
        ):
            with self.assertRaisesRegex(ValueError, "Fila 2"):
                normalize_crop_catalog(changed.encode())

    def test_packaged_catalog_matches_original_table_and_api_contract(self):
        self.assertEqual(load_crop_catalog(), self.catalog)
        response = TestClient(create_app(repository=Mock())).get("/api/v1/crops/catalog")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version"], self.catalog.version)
        self.assertEqual(len(response.json()["crops"]), 12)

    def test_annual_rainfall_cannot_be_replaced_by_short_forecasts_or_future_observations(self):
        for rain in (
            {
                "total_mm": 40,
                "start": "2026-11-14",
                "end": "2026-11-20",
                "valid_days": 7,
                "source": "test-only",
            },
            {
                "total_mm": 1000,
                "start": "2026-01-01",
                "end": "2026-12-31",
                "valid_days": 365,
                "source": "test-only",
            },
        ):
            with self.assertRaises(ValidationError):
                context(annual_rainfall=rain)

    def test_missing_data_and_incomplete_rainfall_remain_unknown(self):
        empty = CropScreeningContext(region_id="test-only", as_of=date(2026, 11, 14))
        report = screen_catalog(self.catalog, empty)
        self.assertTrue(all(crop.status == "insufficient_data" for crop in report.crops))
        self.assertTrue(all(check.status == "unknown" for check in report.crops[0].checks))
        rain = context().annual_rainfall.model_copy(update={"valid_days": 360})
        report = screen_catalog(self.catalog, context(annual_rainfall=rain))
        check = next(
            check for check in report.crops[0].checks if check.variable == "annual_rainfall"
        )
        self.assertEqual(check.status, "unknown")
        self.assertIsNone(check.value)

    def test_valid_numeric_ranges_are_explained_without_promising_sowing_or_rotations(self):
        report = screen_catalog(self.catalog, context())
        maize = next(crop for crop in report.crops if crop.ecocrop_code == 238663)
        self.assertEqual(maize.status, "within_checked_ranges")
        self.assertEqual(maize.checks[0].status, "optimal")
        self.assertFalse(maize.recommendation_ready)
        self.assertFalse(report.rotations_evaluated)
        self.assertTrue(any("65–365" in note for note in maize.limitations))
        self.assertNotIn("latitude", [check.variable for check in maize.checks])
        self.assertEqual(
            screen_catalog(self.catalog, context()).input_snapshot_id, report.input_snapshot_id
        )

    def test_outside_absolute_and_boundary_values_are_not_mislabeled_optimal(self):
        first = screen_catalog(
            self.catalog, context(temperature={**context().temperature.model_dump(), "mean_c": 9})
        )
        maize = next(crop for crop in first.crops if crop.ecocrop_code == 238663)
        self.assertEqual(maize.status, "outside_checked_ranges")
        self.assertEqual(maize.checks[0].status, "outside_absolute")
        boundary = screen_catalog(
            self.catalog, context(temperature={**context().temperature.model_dump(), "mean_c": 10})
        )
        maize = next(crop for crop in boundary.crops if crop.ecocrop_code == 238663)
        self.assertEqual(maize.checks[0].status, "within_absolute")
        self.assertFalse(maize.recommendation_ready)
