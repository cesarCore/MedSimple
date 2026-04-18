"""
OCR service helpers for preprocessing and text extraction.
Kept separate from Flask wiring so unit tests can run without web deps.
"""

import logging
import os
import shutil
import subprocess
from io import StringIO
import csv

logger = logging.getLogger(__name__)

ocr = None
easyocr_reader = None


def get_cv2():
    """Import cv2 lazily so the module remains testable without native deps."""
    try:
        import cv2  # pylint: disable=import-outside-toplevel
    except ImportError as exc:
        raise RuntimeError("opencv-python is required for OCR preprocessing") from exc

    return cv2


def get_numpy():
    """Import numpy lazily so tests can stub OCR logic without the full stack."""
    try:
        import numpy as np  # pylint: disable=import-outside-toplevel
    except ImportError as exc:
        raise RuntimeError("numpy is required for OCR confidence calculations") from exc

    return np


def get_easyocr_reader():
    """Initialize EasyOCR lazily so the service can run without it installed."""
    global easyocr_reader

    if easyocr_reader is None:
        try:
            import easyocr  # pylint: disable=import-outside-toplevel
        except ImportError as exc:
            raise RuntimeError("easyocr is required for EasyOCR extraction") from exc

        logger.info("Initializing EasyOCR model...")
        easyocr_reader = easyocr.Reader(["en"], gpu=False)
        logger.info("EasyOCR model loaded successfully")

    return easyocr_reader


def get_ocr_engine():
    """
    Initialize PaddleOCR only when needed.
    This keeps the module importable in lightweight test environments.
    """
    global ocr

    if ocr is None:
        try:
            from paddleocr import PaddleOCR  # pylint: disable=import-outside-toplevel
        except ImportError as exc:
            raise RuntimeError("paddleocr is required for OCR extraction") from exc

        logger.info("Initializing PaddleOCR model...")
        ocr = PaddleOCR(use_angle_cls=True, lang=['en'], use_gpu=False)
        logger.info("PaddleOCR model loaded successfully")

    return ocr


def get_tesseract_binary():
    """Return the local tesseract binary path when available."""
    binary = shutil.which("tesseract")
    if not binary:
        raise RuntimeError("tesseract is not installed or not on PATH")

    return binary


def preprocess_image(image_path):
    """
    Preprocess image to improve OCR accuracy.
    - Denoise to reduce glare effects
    - Enhance contrast
    - Correct skew if needed
    """
    cv2 = get_cv2()
    img = cv2.imread(image_path)

    if img is None:
        raise ValueError("Could not read image")

    denoised = cv2.fastNlMeansDenoisingColored(
        img,
        None,
        10,
        10,
        7,
        21,
    )

    lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    enhanced = cv2.merge([l_channel, a_channel, b_channel])
    enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    return enhanced


def build_preprocessed_image_path(image_path):
    """Generate a temp filename without corrupting paths containing multiple dots."""
    base, extension = os.path.splitext(image_path)
    return f"{base}_preprocessed{extension}"


def save_preprocessed_image(source_path, image):
    """Persist the preprocessed image and return the temp file path."""
    cv2 = get_cv2()
    temp_path = build_preprocessed_image_path(source_path)

    if not cv2.imwrite(temp_path, image):
        raise ValueError("Could not write preprocessed image")

    return temp_path


def parse_tesseract_tsv(tsv_text):
    """Convert Tesseract TSV output into the existing structured OCR shape."""
    rows = csv.DictReader(StringIO(tsv_text), delimiter="\t")
    extracted_text = []

    for row in rows:
        text = (row.get("text") or "").strip()
        confidence_raw = row.get("conf")

        if not text or confidence_raw in (None, "", "-1"):
            continue

        try:
            confidence = max(0.0, min(1.0, float(confidence_raw) / 100.0))
            left = int(row["left"])
            top = int(row["top"])
            width = int(row["width"])
            height = int(row["height"])
        except (TypeError, ValueError, KeyError):
            continue

        bbox = [
            [left, top],
            [left + width, top],
            [left + width, top + height],
            [left, top + height],
        ]
        extracted_text.append({
            "text": text,
            "confidence": confidence,
            "bbox": bbox,
        })

    return extracted_text


def extract_text_with_tesseract(image_path):
    """Run OCR using the local Tesseract CLI."""
    binary = get_tesseract_binary()
    command = [binary, image_path, "stdout", "tsv"]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        stderr = completed.stderr.strip() or "tesseract failed"
        raise RuntimeError(stderr)

    extracted_text = parse_tesseract_tsv(completed.stdout)
    if not extracted_text:
        return {"status": "error", "message": "No text detected in image"}

    np = get_numpy()
    full_text = " ".join([item["text"] for item in extracted_text])
    return {
        "status": "success",
        "full_text": full_text,
        "structured_results": extracted_text,
        "text_count": len(extracted_text),
        "average_confidence": float(np.mean([item["confidence"] for item in extracted_text])),
        "engine": "tesseract",
    }


def extract_text_with_easyocr(image_path, reader=None):
    """Run OCR using EasyOCR and normalize the result structure."""
    reader = reader or get_easyocr_reader()
    result = reader.readtext(image_path, detail=1)

    if not result:
        return {"status": "error", "message": "No text detected in image"}

    np = get_numpy()
    extracted_text = []
    for detection in result:
        bbox = [[float(x), float(y)] for x, y in detection[0]]
        text = detection[1]
        confidence = float(detection[2])
        extracted_text.append({
            "text": text,
            "confidence": confidence,
            "bbox": bbox,
        })

    full_text = " ".join([item["text"] for item in extracted_text])
    return {
        "status": "success",
        "full_text": full_text,
        "structured_results": extracted_text,
        "text_count": len(extracted_text),
        "average_confidence": float(np.mean([item["confidence"] for item in extracted_text])),
        "engine": "easyocr",
    }


def select_better_ocr_result(candidates):
    """Choose the strongest OCR result from a list of candidate payloads."""
    successful = [candidate for candidate in candidates if candidate.get("status") == "success"]
    if not successful:
        return candidates[0] if candidates else {"status": "error", "message": "No OCR result"}

    def score(result):
        return (
            result.get("text_count", 0),
            len(result.get("full_text", "")),
            result.get("average_confidence", 0.0),
        )

    return max(successful, key=score)


def extract_text_from_image(image_path, ocr_engine=None, preprocess_fn=None, save_preprocessed_fn=None):
    """
    Extract text from an image using PaddleOCR.
    Returns structured data with text and confidence scores.
    """
    try:
        preprocess_fn = preprocess_fn or preprocess_image
        save_preprocessed_fn = save_preprocessed_fn or save_preprocessed_image
        preprocessed_img = preprocess_fn(image_path)

        temp_path = save_preprocessed_fn(image_path, preprocessed_img)
        try:
            if ocr_engine is None:
                try:
                    return select_better_ocr_result([
                        extract_text_with_easyocr(temp_path),
                        extract_text_with_easyocr(image_path),
                    ])
                except RuntimeError as easyocr_error:
                    logger.warning("EasyOCR unavailable: %s", easyocr_error)

                try:
                    ocr_engine = get_ocr_engine()
                except RuntimeError as paddle_error:
                    logger.warning("PaddleOCR unavailable, falling back to Tesseract: %s", paddle_error)
                    return select_better_ocr_result([
                        extract_text_with_tesseract(image_path),
                        extract_text_with_tesseract(temp_path),
                    ])

            result = ocr_engine.ocr(temp_path, cls=True)

            if not result or not result[0]:
                return {"status": "error", "message": "No text detected in image"}

            np = get_numpy()
            extracted_text = []
            for line in result[0]:
                text = line[1][0]
                confidence = line[1][1]
                bbox = line[0]

                extracted_text.append({
                    "text": text,
                    "confidence": float(confidence),
                    "bbox": bbox,
                })

            full_text = " ".join([item["text"] for item in extracted_text])

            return {
                "status": "success",
                "full_text": full_text,
                "structured_results": extracted_text,
                "text_count": len(extracted_text),
                "average_confidence": float(np.mean([item["confidence"] for item in extracted_text])),
                "engine": "paddleocr",
            }
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as exc:
        logger.error("Error during OCR processing: %s", exc)
        return {"status": "error", "message": str(exc)}
