import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cabpool_5_methods as cabpool


class PlaceCatalogTests(unittest.TestCase):
    def setUp(self):
        self.app = cabpool.CabPool()

    def test_supplied_catalog_contains_one_thousand_numbered_places(self):
        self.assertEqual(len(self.app.places), 1000)
        self.assertEqual(self.app.places[0]["number"], 1)
        self.assertEqual(self.app.places[-1]["number"], 1000)

    def test_finds_catalog_place_by_number_and_city_name(self):
        self.assertEqual(self.app.choose_catalog_place("1")["name"],
                         "Indira Gandhi International Airport (IGI) - Terminal 1, New Delhi")
        self.assertEqual(self.app.choose_catalog_place("Noida")["name"],
                         "Noida, Uttar Pradesh")

    def test_returns_no_match_for_place_outside_catalog(self):
        self.assertIsNone(self.app.choose_catalog_place("Atlantis"))

    def test_unknown_place_uses_manually_entered_distance(self):
        with patch.object(self.app, "ask_manual_distance", return_value=(25.5, "manually entered")):
            destination, distance, source = self.app.resolve_destination("Atlantis")
        self.assertEqual(destination, "Atlantis")
        self.assertEqual(distance, 25.5)
        self.assertEqual(source, "manually entered")


class RouteDistanceTests(unittest.TestCase):
    def test_catalog_place_uses_route_distance_in_metres_converted_to_km(self):
        app = cabpool.CabPool()
        place = app.choose_catalog_place("Noida")
        geocode = [{"lat": "28.5355", "lon": "77.3910", "display_name": "Noida, India"}]
        route = {"code": "Ok", "routes": [{"distance": 18342.0}]}
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "distance_cache.json"
            with patch.object(cabpool, "DISTANCE_CACHE_FILE", str(cache_path)), \
                    patch.object(cabpool, "get_json", side_effect=[geocode, route]):
                distance, source = app.route_distance(place)
            saved_cache = json.loads(cache_path.read_text(encoding="utf-8"))

        self.assertEqual(distance, 18.3)
        self.assertEqual(source, "OpenStreetMap route")
        self.assertEqual(saved_cache[place["name"]]["distance_km"], 18.3)


class FareCalculationTests(unittest.TestCase):
    def test_fare_uses_distance_and_rate_then_splits_between_passengers(self):
        app = cabpool.CabPool(fare_per_km=10)
        app.requests = [
            {"name": "A", "destination": "Noida", "distance_km": 20.0,
             "distance_source": "manual", "time": 600, "flex": 30},
            {"name": "B", "destination": "Noida", "distance_km": 20.0,
             "distance_source": "manual", "time": 610, "flex": 30},
        ]

        app.match_requests()
        total_saved = app.calculate_fares()
        cab = app.cabs[0]

        self.assertEqual(cab["cab_fare"], 200.0)
        self.assertEqual(cab["per_person"], 100.0)
        self.assertEqual(cab["saved_per_person"], 100.0)
        self.assertEqual(total_saved, 200.0)

    def test_single_request_remains_unmatched(self):
        app = cabpool.CabPool()
        app.requests = [
            {"name": "A", "destination": "Noida", "distance_km": 20.0,
             "distance_source": "manual", "time": 600, "flex": 30},
        ]
        app.match_requests()
        self.assertEqual(app.cabs, [])
        self.assertEqual([item["name"] for item in app.unmatched], ["A"])


if __name__ == "__main__":
    unittest.main()
