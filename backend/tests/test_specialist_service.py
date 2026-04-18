import unittest
from unittest.mock import MagicMock

from backend import specialist_service


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class InferSpecialistTypesTests(unittest.TestCase):
    def test_matches_single_keyword(self):
        self.assertEqual(
            specialist_service.infer_specialist_types("Metformin for diabetes"),
            ["endocrinologist", "pharmacy"],
        )

    def test_matches_multiple_keywords(self):
        result = specialist_service.infer_specialist_types("heart blood pressure combo")
        self.assertEqual(result, ["cardiologist", "pharmacy"])

    def test_defaults_when_no_match(self):
        self.assertEqual(
            specialist_service.infer_specialist_types("random stuff"),
            ["general practitioner", "pharmacy"],
        )

    def test_empty_input_defaults(self):
        self.assertEqual(
            specialist_service.infer_specialist_types(""),
            ["general practitioner", "pharmacy"],
        )


class HaversineTests(unittest.TestCase):
    def test_zero_distance(self):
        self.assertAlmostEqual(specialist_service.haversine_km(40.7, -74.0, 40.7, -74.0), 0.0, places=6)

    def test_nyc_to_la_distance(self):
        # NYC (40.7128, -74.0060) to LA (34.0522, -118.2437) ≈ 3935 km
        distance = specialist_service.haversine_km(40.7128, -74.0060, 34.0522, -118.2437)
        self.assertAlmostEqual(distance, 3935.0, delta=20.0)


class GooglePlacesSearchTests(unittest.TestCase):
    def test_geocode_location_returns_coordinates(self):
        fake_get = MagicMock(return_value=FakeResponse({
            "status": "OK",
            "results": [{
                "formatted_address": "Boston, MA, USA",
                "geometry": {"location": {"lat": 42.3601, "lng": -71.0589}},
            }],
        }))

        result = specialist_service.geocode_location("Boston", "USA", "KEY", http_get=fake_get)

        self.assertEqual(result["formatted_address"], "Boston, MA, USA")
        self.assertAlmostEqual(result["lat"], 42.3601)
        self.assertAlmostEqual(result["lng"], -71.0589)

    def _places_payload(self):
        return {
            "status": "OK",
            "results": [
                {
                    "place_id": "a",
                    "name": "Clinic A",
                    "vicinity": "1 Main St",
                    "rating": 4.5,
                    "geometry": {"location": {"lat": 40.7130, "lng": -74.0055}},
                },
                {
                    "place_id": "b",
                    "name": "Clinic B",
                    "formatted_address": "2 Broad St",
                    "rating": 4.0,
                    "geometry": {"location": {"lat": 40.7200, "lng": -74.0100}},
                },
                {
                    "place_id": "bad",
                    "name": "No Geo",
                    "geometry": {"location": {}},
                },
            ],
        }

    def test_search_parses_results_and_computes_distance(self):
        fake_get = MagicMock(return_value=FakeResponse(self._places_payload()))

        results = specialist_service.google_places_search(
            lat=40.7128,
            lng=-74.0060,
            radius=5000,
            specialist_type="cardiologist",
            api_key="KEY",
            http_get=fake_get,
        )

        fake_get.assert_called_once()
        call_kwargs = fake_get.call_args.kwargs
        self.assertEqual(call_kwargs["params"]["type"], "doctor")
        self.assertEqual(call_kwargs["params"]["keyword"], "cardiologist")
        self.assertEqual(call_kwargs["params"]["key"], "KEY")

        self.assertEqual(len(results), 2)  # "bad" filtered out
        self.assertEqual(results[0]["name"], "Clinic A")
        self.assertEqual(results[0]["address"], "1 Main St")
        self.assertGreater(results[0]["distance_km"], 0.0)
        self.assertLess(results[0]["distance_km"], 1.0)
        self.assertIn("map_url", results[0])
        self.assertEqual(results[0]["latitude"], 40.7130)
        self.assertEqual(results[0]["longitude"], -74.0055)

    def test_search_uses_pharmacy_type_for_pharmacy(self):
        fake_get = MagicMock(return_value=FakeResponse({"status": "ZERO_RESULTS", "results": []}))
        specialist_service.google_places_search(
            lat=0, lng=0, radius=1000, specialist_type="pharmacy", api_key="K", http_get=fake_get
        )
        params = fake_get.call_args.kwargs["params"]
        self.assertEqual(params["type"], "pharmacy")
        self.assertEqual(params["keyword"], "pharmacy")

    def test_search_raises_on_api_error_status(self):
        fake_get = MagicMock(return_value=FakeResponse({"status": "REQUEST_DENIED", "error_message": "bad key"}))
        with self.assertRaises(ValueError) as ctx:
            specialist_service.google_places_search(
                lat=0, lng=0, radius=1000, specialist_type="pharmacy", api_key="K", http_get=fake_get
            )
        self.assertIn("bad key", str(ctx.exception))

    def test_search_raises_on_http_error(self):
        fake_get = MagicMock(return_value=FakeResponse({}, status_code=500))
        with self.assertRaises(RuntimeError):
            specialist_service.google_places_search(
                lat=0, lng=0, radius=1000, specialist_type="pharmacy", api_key="K", http_get=fake_get
            )


class FindSpecialistsTests(unittest.TestCase):
    def test_dedupes_by_place_id_and_keeps_closest(self):
        def fake_search(lat, lng, radius, specialist_type, api_key):
            if specialist_type == "endocrinologist":
                return [
                    {"place_id": "x", "name": "Dr X", "address": "1", "specialist_type": "endocrinologist",
                     "rating": 4.0, "distance_km": 5.0, "map_url": ""},
                ]
            return [
                {"place_id": "x", "name": "Dr X", "address": "1", "specialist_type": "pharmacy",
                 "rating": 4.0, "distance_km": 2.0, "map_url": ""},
                {"place_id": "y", "name": "Pharm Y", "address": "2", "specialist_type": "pharmacy",
                 "rating": 3.0, "distance_km": 3.0, "map_url": ""},
            ]

        types, specialists, warnings = specialist_service.find_specialists(
            "insulin", 0, 0, 5000, "KEY", search_fn=fake_search
        )

        self.assertEqual(types, ["endocrinologist", "pharmacy"])
        self.assertEqual(warnings, [])
        self.assertEqual([s["place_id"] for s in specialists], ["x", "y"])
        self.assertEqual(specialists[0]["distance_km"], 2.0)  # closest copy kept

    def test_records_warning_when_one_search_fails(self):
        def fake_search(lat, lng, radius, specialist_type, api_key):
            if specialist_type == "pharmacy":
                raise ValueError("boom")
            return [{"place_id": "a", "name": "A", "address": "x", "specialist_type": specialist_type,
                     "rating": None, "distance_km": 1.0, "map_url": ""}]

        _types, specialists, warnings = specialist_service.find_specialists(
            "diabetes", 0, 0, 5000, "KEY", search_fn=fake_search
        )
        self.assertEqual(warnings, ["pharmacy: search failed"])
        self.assertEqual(len(specialists), 1)

    def test_limits_to_five_results(self):
        def fake_search(lat, lng, radius, specialist_type, api_key):
            return [
                {"place_id": f"{specialist_type}-{i}", "name": f"n{i}", "address": "a",
                 "specialist_type": specialist_type, "rating": 4.0, "distance_km": float(i), "map_url": ""}
                for i in range(10)
            ]

        _types, specialists, _warnings = specialist_service.find_specialists(
            "unknown med", 0, 0, 5000, "KEY", search_fn=fake_search
        )
        # Two specialist types × 10 results each; sorted across both by distance_km.
        self.assertEqual(len(specialists), 5)
        self.assertEqual([s["distance_km"] for s in specialists], [0.0, 0.0, 1.0, 1.0, 2.0])


if __name__ == "__main__":
    unittest.main()
