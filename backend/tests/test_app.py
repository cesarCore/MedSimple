import importlib.util
import os
import unittest
from unittest.mock import patch

from backend import ocr_service


class FakeOCREngine:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def ocr(self, path, cls=True):
        self.calls.append({"path": path, "cls": cls})
        return self.result


class OCRServiceTests(unittest.TestCase):
    def test_parse_tesseract_tsv_filters_empty_rows_and_normalizes_confidence(self):
        tsv_text = (
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t10\t20\t30\t40\t96.5\tCapture\n"
            "5\t1\t1\t1\t1\t2\t45\t20\t60\t40\t88.0\tprescription\n"
            "5\t1\t1\t1\t1\t3\t100\t20\t10\t40\t-1\t\n"
        )

        result = ocr_service.parse_tesseract_tsv(tsv_text)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["text"], "Capture")
        self.assertAlmostEqual(result[0]["confidence"], 0.965, places=3)
        self.assertEqual(result[1]["bbox"], [[45, 20], [105, 20], [105, 60], [45, 60]])

    def test_build_preprocessed_image_path_preserves_multi_dot_names(self):
        path = "/tmp/prescription.sample.v1.png"
        expected = "/tmp/prescription.sample.v1_preprocessed.png"
        self.assertEqual(ocr_service.build_preprocessed_image_path(path), expected)

    def test_extract_text_from_image_returns_structured_success_payload(self):
        fake_engine = FakeOCREngine([
            [
                [
                    [[0, 0], [1, 0], [1, 1], [0, 1]],
                    ("OCR extraction", 0.91),
                ],
                [
                    [[2, 2], [3, 2], [3, 3], [2, 3]],
                    ("Structured JSON", 0.89),
                ],
            ]
        ])

        with patch.object(ocr_service, "get_numpy") as mock_get_numpy:
            class FakeNumpy:
                @staticmethod
                def mean(values):
                    return sum(values) / len(values)

            mock_get_numpy.return_value = FakeNumpy()
            result = ocr_service.extract_text_from_image(
                "/tmp/sample.png",
                ocr_engine=fake_engine,
                preprocess_fn=lambda _: "preprocessed-image",
                save_preprocessed_fn=lambda path, image: "/tmp/preprocessed.png",
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["full_text"], "OCR extraction Structured JSON")
        self.assertEqual(result["text_count"], 2)
        self.assertAlmostEqual(result["average_confidence"], 0.90, places=2)
        self.assertEqual(result["structured_results"][0]["text"], "OCR extraction")
        self.assertEqual(fake_engine.calls[0]["path"], "/tmp/preprocessed.png")

    def test_extract_text_from_image_returns_error_when_no_text_detected(self):
        fake_engine = FakeOCREngine([[]])

        with patch.object(ocr_service, "get_numpy") as mock_get_numpy:
            mock_get_numpy.return_value = object()
            result = ocr_service.extract_text_from_image(
                "/tmp/sample.png",
                ocr_engine=fake_engine,
                preprocess_fn=lambda _: "preprocessed-image",
                save_preprocessed_fn=lambda path, image: "/tmp/preprocessed.png",
            )

        self.assertEqual(result, {"status": "error", "message": "No text detected in image"})

    def test_sample_fixture_exists_for_future_ocr_regression_runs(self):
        fixture_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "docs", "image.png")
        )
        self.assertTrue(os.path.exists(fixture_path))
        self.assertGreater(os.path.getsize(fixture_path), 0)

    @unittest.skipUnless(
        (importlib.util.find_spec("paddleocr") or ocr_service.get_tesseract_binary())
        and importlib.util.find_spec("cv2")
        and importlib.util.find_spec("numpy"),
        "No runnable OCR engine is installed in this environment.",
    )
    def test_real_ocr_on_sample_fixture_captures_key_phrases(self):
        fixture_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "docs", "image.png")
        )
        result = ocr_service.extract_text_from_image(fixture_path)
        self.assertEqual(result["status"], "success")

        normalized_text = " ".join(result["full_text"].lower().split())
        # Phrases chosen to be engine-tolerant: EasyOCR drops punctuation like
        # ">" and "/", while Tesseract/PaddleOCR preserve them.
        for phrase in [
            "capture prescription",
            "citation validation",
            "symptom",
            "specialist mapping",
            "user views",
        ]:
            self.assertIn(phrase, normalized_text)


if __name__ == "__main__":
    unittest.main()
