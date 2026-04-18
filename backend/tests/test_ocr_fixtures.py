"""Characterization tests for OCR against the real prescription / label fixtures.

Baselines were captured once against EasyOCR on macOS/Python 3.12 (April 2026).
Thresholds are intentionally loose (≈70% of baseline text_count, ≈60% of len)
so minor engine/version drift won't fail CI, but clear regressions will.

Skips cleanly when no real OCR engine is available.
"""

import importlib.util
import os
import unittest

from backend import ocr_service


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _path(*parts):
    return os.path.join(REPO_ROOT, *parts)


# name -> {path, min_count, min_len, phrases}
FIXTURE_EXPECTATIONS = {
    "strong_bottle_IMG_7027": {
        "path": _path("tests", "IMG_7027.webp"),
        "min_count": 60,
        "min_len": 1000,
        "phrases": ["supplement"],
    },
    "fair_label_IMG_7025": {
        "path": _path("tests", "images", "IMG_7025.webp"),
        "min_count": 60,
        "min_len": 500,
        "phrases": [],
    },
    "noisy_energy_IMG_7029": {
        "path": _path("tests", "images", "IMG_7029.jpg"),
        "min_count": 30,
        "min_len": 300,
        "phrases": [],
    },
    "fair_tablet_IMG_7030": {
        "path": _path("tests", "images", "IMG_7030.jpg"),
        "min_count": 45,
        "min_len": 400,
        "phrases": ["serving"],
    },
    "morphine_stock_image": {
        "path": _path("tests", "images", "istockphoto-1444837770-612x612.jpg"),
        "min_count": 8,
        "min_len": 100,
        "phrases": ["morphine"],
    },
    "ginger_capsules_sample3": {
        "path": _path("tests", "images", "sample3_real.jpg"),
        "min_count": 35,
        "min_len": 350,
        "phrases": ["capsules"],
    },
    "architecture_doc_image": {
        "path": _path("docs", "image.png"),
        "min_count": 20,
        "min_len": 400,
        "phrases": ["capture prescription"],
    },
}


def _has_real_ocr_engine():
    if not (importlib.util.find_spec("cv2") and importlib.util.find_spec("numpy")):
        return False
    if importlib.util.find_spec("easyocr") or importlib.util.find_spec("paddleocr"):
        return True
    try:
        ocr_service.get_tesseract_binary()
    except RuntimeError:
        return False
    return True


@unittest.skipUnless(_has_real_ocr_engine(), "No runnable OCR engine is installed.")
class OCRFixtureCharacterizationTests(unittest.TestCase):
    """One test per fixture, generated dynamically below."""


def _make_fixture_test(name, spec):
    def test(self):
        self.assertTrue(os.path.exists(spec["path"]), f"Missing fixture: {spec['path']}")
        result = ocr_service.extract_text_from_image(spec["path"])
        self.assertEqual(result.get("status"), "success", msg=f"OCR failed: {result}")
        self.assertGreaterEqual(
            result["text_count"], spec["min_count"],
            msg=f"{name}: text_count {result['text_count']} < {spec['min_count']}",
        )
        self.assertGreaterEqual(
            len(result["full_text"]), spec["min_len"],
            msg=f"{name}: full_text len {len(result['full_text'])} < {spec['min_len']}",
        )
        normalized = " ".join(result["full_text"].lower().split())
        for phrase in spec["phrases"]:
            self.assertIn(phrase, normalized, msg=f"{name}: missing phrase '{phrase}'")

    test.__name__ = f"test_{name}"
    return test


for _name, _spec in FIXTURE_EXPECTATIONS.items():
    setattr(
        OCRFixtureCharacterizationTests,
        f"test_{_name}",
        _make_fixture_test(_name, _spec),
    )


if __name__ == "__main__":
    unittest.main()
