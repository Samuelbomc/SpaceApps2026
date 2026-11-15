"""Fixtures locales: no son mediciones agrícolas reales."""

import unittest
from datetime import date

from pydantic import ValidationError

from apps.api.app.services.auth import HASHER, verify_password
from apps.api.app.services.farm_datasets import parse_csv
from packages.contracts.farms import FarmWrite


class FarmCSVTests(unittest.TestCase):
    def test_units_dates_and_values_are_kept_without_imputation(self):
        rows = parse_csv(
            b"date,variable,value,unit,crop\n2024-01-01,soil_moisture,0.31,m3/m3,\n2024-01-01,crop_yield,4.2,t/ha,maiz\n",
            today=date(2024, 1, 2),
        )
        self.assertEqual(rows[0]["value"], 0.31)
        self.assertEqual(rows[0]["date"], date(2024, 1, 1))
        self.assertEqual(rows[1]["crop"], "maiz")

    def test_utf8_bom_and_semicolon_export(self):
        content = "\ufeffdate;variable;value;unit\n2024-01-01;soil_ph;6.2;pH\n".encode("utf-8")
        self.assertEqual(parse_csv(content)[0]["value"], 6.2)

    def test_invalid_files_are_rejected_whole(self):
        invalid = [
            b"",
            b"date,variable,value,unit\n",
            b"\xff\x00",
            b"date,variable,value,unit\n2999-01-01,soil_ph,6,pH\n",
            b"date,variable,value,unit\n2024-01-01,soil_ph,nan,pH\n",
            b"date,variable,value,unit\n2024-01-01,relative_humidity,101,%\n",
            b"date,variable,value,unit\n2024-01-01,soil_moisture,31,%\n",
            b"date,variable,value,unit\n2024-01-01,rain,2,mm\n",
            b"date,variable,value,unit\n2024-01-01,crop_yield,4,t/ha\n",
            b"date,variable,value,unit,crop\n2024-01-01,crop_yield,4,t/ha,=formula\n",
            "date,variable,value,unit,crop\n2024-01-01,crop_yield,4,t/ha,\ufeff=formula\n".encode(
                "utf-8"
            ),
            b"date,variable,value,unit\n2024-01-01,soil_ph,6,pH\n2024-01-01,soil_ph,7,pH\n",
            b"date,variable,value,unit\n2024-01-01,soil_ph,6,pH,extra\n",
        ]
        for content in invalid:
            with self.subTest(content=content), self.assertRaises(ValueError):
                parse_csv(content)

    def test_declared_farm_center_must_match_saved_area(self):
        with self.assertRaises(ValidationError):
            FarmWrite(
                name="Fixture",
                latitude=6,
                longitude=-75,
                area_ha=1,
                boundary={"west": -74, "east": -73, "south": 5, "north": 7},
            )

    def test_password_hashes_are_salted_and_verified(self):
        password = "Una frase de prueba muy larga"
        first, second = HASHER.hash(password), HASHER.hash(password)
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("$argon2id$"))
        self.assertTrue(verify_password(password, first))
        self.assertFalse(verify_password("otra contraseña", first))
