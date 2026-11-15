"""Pruebas de integración de comandos y consultas por fuente."""

import io
import json
import unittest
from unittest.mock import patch

from scripts.ingest import main
from pipelines.ingestion.http import IngestionError


class CLITests(unittest.TestCase):
    def test_missing_dates(self):
        with patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(main(["power"]), 1)
            self.assertEqual(main(["search", "--source", "gpm", "--start", "2024-01-01"]), 1)

    def test_partial_success_is_reported(self):
        def search(source, *args, **kwargs):
            if source == "smap":
                raise IngestionError("No disponible")
            return {"granules": []}
        with patch("scripts.ingest.CMRClient") as client, patch("sys.stdout", new_callable=io.StringIO) as output:
            client.return_value.search.side_effect = search
            code = main(["search", "--source", "all", "--start", "2024-01-01", "--end", "2024-01-02"])
            payload = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertIn("gpm", payload["products"])
        self.assertEqual(payload["errors"], {"smap": "No disponible"})



class PowerCLITests(unittest.TestCase):
    def test_cli_power_uses_raw_client_contract(self):
        payload = {"raw_responses": [{"response": {"value": -999}}]}
        with patch("scripts.ingest.PowerClient") as client, patch("sys.stdout", new_callable=io.StringIO) as stdout:
            client.return_value.fetch_daily.return_value = payload
            code = main(["power", "--start", "2024-01-01", "--end", "2024-01-02"])
            self.assertEqual(json.loads(stdout.getvalue()), payload)
            client.return_value.daily.assert_not_called()
        self.assertEqual(code, 0)
