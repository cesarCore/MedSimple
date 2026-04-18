import io
import os
import unittest
from unittest.mock import patch

from backend import app as app_module


class RouteTestsBase(unittest.TestCase):
    def setUp(self):
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()


class HealthRouteTests(RouteTestsBase):
    def test_health_ok(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "healthy")


class UploadRouteTests(RouteTestsBase):
    def test_rejects_missing_file(self):
        response = self.client.post("/api/upload", data={})
        self.assertEqual(response.status_code, 400)
        self.assertIn("No file", response.get_json()["message"])

    def test_rejects_bad_extension(self):
        data = {"file": (io.BytesIO(b"abc"), "notes.txt")}
        response = self.client.post("/api/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)
        self.assertIn("not allowed", response.get_json()["message"])

    def test_success_path_is_wired_to_service(self):
        canned = {
            "status": "success",
            "full_text": "Aspirin 500mg",
            "structured_results": [],
            "text_count": 1,
            "average_confidence": 0.9,
            "engine": "test",
        }
        with patch.object(app_module, "extract_text_from_image", return_value=canned):
            data = {"file": (io.BytesIO(b"\x89PNG\r\n\x1a\n"), "sample.png")}
            response = self.client.post(
                "/api/upload", data=data, content_type="multipart/form-data"
            )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["ocr_data"], canned)
        self.assertTrue(body["file_id"].endswith(".png"))
        # clean up the saved file so repeat runs stay tidy
        saved = os.path.join(app_module.app.config["UPLOAD_FOLDER"], body["file_id"])
        if os.path.exists(saved):
            os.remove(saved)


class FindSpecialistsRouteTests(RouteTestsBase):
    def _post(self, payload):
        return self.client.post("/api/find-specialists", json=payload)

    def test_missing_api_key_returns_500(self):
        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": ""}, clear=False):
            response = self._post({
                "medication_name": "insulin",
                "user_location": {"lat": 40.7, "lng": -74.0},
            })
        self.assertEqual(response.status_code, 500)
        self.assertIn("GOOGLE_MAPS_API_KEY", response.get_json()["message"])

    def test_requires_medication_name(self):
        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test"}):
            response = self._post({"user_location": {"lat": 0, "lng": 0}})
        self.assertEqual(response.status_code, 400)
        self.assertIn("medication_name", response.get_json()["message"])

    def test_rejects_out_of_range_coords(self):
        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test"}):
            response = self._post({
                "medication_name": "insulin",
                "user_location": {"lat": 999, "lng": -74.0},
            })
        self.assertEqual(response.status_code, 400)
        self.assertIn("out of range", response.get_json()["message"])

    def test_rejects_radius_outside_bounds(self):
        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test"}):
            response = self._post({
                "medication_name": "insulin",
                "user_location": {"lat": 40.7, "lng": -74.0},
                "radius": 50,
            })
        self.assertEqual(response.status_code, 400)

    def test_accepts_city_and_country_and_geocodes(self):
        def fake_service(medication_name, lat, lng, radius, api_key):
            self.assertEqual(medication_name, "insulin")
            self.assertAlmostEqual(lat, 42.36)
            self.assertAlmostEqual(lng, -71.05)
            self.assertEqual(radius, 5000)
            return (["endocrinologist"], [], [])

        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test"}), \
             patch.object(app_module, "geocode_location", return_value={
                 "formatted_address": "Boston, MA, USA",
                 "lat": 42.36,
                 "lng": -71.05,
             }), \
             patch.object(app_module, "find_specialists_service", side_effect=fake_service):
            response = self._post({
                "medication_name": "insulin",
                "user_location": {"city": "Boston", "country": "USA"},
                "radius": 5000,
            })

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["user_location"]["formatted_address"], "Boston, MA, USA")
        self.assertEqual(body["count"], 0)

    def test_happy_path_returns_ranked_specialists(self):
        def fake_service(medication_name, lat, lng, radius, api_key):
            return (
                ["endocrinologist", "pharmacy"],
                [
                    {"place_id": "a", "name": "A", "address": "1",
                     "specialist_type": "endocrinologist", "rating": 4.5,
                     "distance_km": 1.2, "latitude": 40.8, "longitude": -74.1, "map_url": ""},
                ],
                [],
            )

        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test"}), \
             patch.object(app_module, "find_specialists_service", side_effect=fake_service):
            response = self._post({
                "medication_name": "insulin",
                "user_location": {"lat": 40.7, "lng": -74.0},
                "radius": 5000,
            })

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["specialist_types"], ["endocrinologist", "pharmacy"])
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["specialists"][0]["name"], "A")


class AnalyzeRouteTests(RouteTestsBase):
    def test_requires_ocr_full_text(self):
        r = self.client.post("/api/analyze", json={})
        self.assertEqual(r.status_code, 400)

    def test_happy_path(self):
        canned = {"status": "success", "product": {}, "ingredients": [],
                  "clinical_findings": [], "warnings": [],
                  "specialist_recommendation_basis": {}, "metadata": {}}
        with patch.object(app_module, "analyze_service", return_value=canned):
            r = self.client.post("/api/analyze", json={
                "ocr": {"full_text": "Aspirin 500mg"},
            })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "success")


if __name__ == "__main__":
    unittest.main()
