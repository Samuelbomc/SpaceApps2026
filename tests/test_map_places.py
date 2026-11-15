"""Nombres del centro del mapa, sin depender de llamadas externas durante la suite."""

import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from apps.api.app.main import create_app
from apps.api.app.services.map_places import MapPlaceService, PlaceLookupBusy, PlaceLookupUnavailable
from pipelines.ingestion.http import IngestionError


class MapPlacesTests(unittest.TestCase):
    def setUp(self):
        self.http = Mock()
        self.http.get.return_value = {"features": [{"properties": {
            "name": "Una calle", "district": "El Poblado", "city": "Medellín", "state": "Antioquia", "country": "Colombia"}}]}
        self.now = 100.
        self.service = MapPlaceService("https://example.invalid/reverse", self.http, clock=lambda: self.now)
        self.client = TestClient(create_app(repository=Mock(), place_service=self.service))

    def test_reverse_uses_map_coordinates_rounds_and_reuses_cached_names(self):
        first = self.client.get('/api/v1/places/reverse?latitude=6.2442&longitude=-75.5812')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()['label'], 'El Poblado, Medellín, Antioquia, Colombia')
        second = self.client.get('/api/v1/places/reverse?latitude=6.24421&longitude=-75.58121')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(self.http.get.call_count, 1)
        params = self.http.get.call_args.args[1]
        self.assertEqual(params['lat'], 6.244)
        self.assertEqual(params['lon'], -75.581)

    def test_rate_limit_is_bounded_and_does_not_send_additional_upstream_requests(self):
        self.service.resolve(6.2442, -75.5812)
        with self.assertRaises(PlaceLookupBusy):
            self.service.resolve(6.3, -75.6)
        response = self.client.get('/api/v1/places/reverse?latitude=6.3&longitude=-75.6')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers['Retry-After'], '2')
        self.assertEqual(self.http.get.call_count, 1)
        self.now += 2
        self.assertEqual(self.client.get('/api/v1/places/reverse?latitude=6.3&longitude=-75.6').status_code, 200)

    def test_empty_coverage_does_not_invent_a_location(self):
        self.http.get.return_value = {'features': []}
        response = self.client.get('/api/v1/places/reverse?latitude=0&longitude=0')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['label'])

    def test_provider_failure_does_not_leak_details_or_relabel_an_old_place(self):
        self.http.get.side_effect = IngestionError('private-upstream-details')
        response = self.client.get('/api/v1/places/reverse?latitude=6.2&longitude=-75.5')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private-upstream-details', response.text)

    def test_invalid_coordinates_fail_before_calling_provider(self):
        for params in ('latitude=91&longitude=0', 'latitude=0&longitude=-181', 'latitude=nan&longitude=0'):
            self.assertEqual(self.client.get('/api/v1/places/reverse?' + params).status_code, 422)
        self.http.get.assert_not_called()

    def test_malformed_provider_response_is_not_cached_as_a_valid_place(self):
        self.http.get.return_value = {'features': 'invalid'}
        with self.assertRaises(PlaceLookupUnavailable):
            self.service.resolve(6.2, -75.5)
        self.now += 2
        self.http.get.return_value = {'features': [{'properties': {'name': 'Rionegro', 'osm_key': 'place', 'city': 'Rionegro', 'country': 'Colombia'}}]}
        self.assertEqual(self.service.resolve(6.2, -75.5).label, 'Rionegro, Colombia')
