"""Verifica que el acceso externo preserve datos sin adelantar decisiones de ML."""

import unittest
from unittest.mock import Mock

from apps.api.app.repositories import ECOSTRESSRepository, PowerRepository
from packages.contracts import DataQuery
from packages.contracts.models import ANTIOQUIA_ORIENTE, DateRange
from pipelines.ingestion.sources.nasa.power import PowerClient


class RepositoryBoundaryTests(unittest.TestCase):
    def test_power_preserves_provider_values_coordinates_and_metadata(self):
        period = DateRange.parse("2024-01-01", "2024-01-01")
        provider = {
            "header": {"fill_value": -999},
            "features": [
                {
                    "geometry": {"coordinates": [-76, 5]},
                    "properties": {"parameter": {"T2M": {"20240101": -999}}},
                }
            ],
            "parameters": {"T2M": {"units": "C"}},
        }
        http = Mock()
        http.get.return_value = provider
        result = PowerRepository(PowerClient(http)).fetch(
            DataQuery(bbox=ANTIOQUIA_ORIENTE, period=period, power_parameters=("T2M",))
        )
        payload = result["data"]
        self.assertEqual(payload["raw_responses"][0]["response"], provider)
        self.assertNotIn("records", payload)
        self.assertEqual(payload["bbox"], ANTIOQUIA_ORIENTE.as_dict())
        self.assertNotEqual(payload["query_bbox"], payload["bbox"])

    def test_ecostress_invalid_product_fails_before_network(self):
        with self.assertRaisesRegex(ValueError, "Producto ECOSTRESS"):
            ECOSTRESSRepository(product="unknown")


if __name__ == "__main__":
    unittest.main()
