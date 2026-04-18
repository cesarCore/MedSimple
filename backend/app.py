"""
Prescription Bottle Analysis Backend
Thin Flask app — OCR delegated to ocr_service, specialist lookup to specialist_service.
"""

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

try:
    from backend.ocr_service import extract_text_from_image
    from backend.specialist_service import (
        find_specialists as find_specialists_service,
        geocode_location,
    )
except ModuleNotFoundError:
    from ocr_service import extract_text_from_image
    from specialist_service import find_specialists as find_specialists_service, geocode_location

try:
    from flask_cors import CORS
except ImportError:
    CORS = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_environment():
    """Load project-root .env first, then backend/.env as an optional override."""
    backend_dir = Path(__file__).resolve().parent
    project_root = backend_dir.parent

    load_dotenv(project_root / ".env")
    load_dotenv(backend_dir / ".env", override=True)


load_environment()

app = Flask(__name__)
if CORS is not None:
    CORS(app)
else:
    logger.warning("flask_cors is not installed; running without CORS support")

app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file):
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    filename = secure_filename(file.filename)
    unique_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    extension = os.path.splitext(filename)[1]
    saved_filename = f"{timestamp}_{unique_id}{extension}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], saved_filename)
    file.save(filepath)
    return filepath, saved_filename


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": "PrescriptionOCR"}), 200


@app.route("/api/upload", methods=["POST"])
def upload_image():
    try:
        if "file" not in request.files:
            return jsonify({"status": "error", "message": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"status": "error", "message": "No file selected"}), 400

        if not allowed_file(file.filename):
            return jsonify({
                "status": "error",
                "message": f"File type not allowed. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            }), 400

        filepath, saved_filename = save_uploaded_file(file)
        logger.info("File saved: %s", saved_filename)

        ocr_result = extract_text_from_image(filepath)
        if ocr_result["status"] == "error":
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify(ocr_result), 400

        return jsonify({
            "status": "success",
            "message": "Image processed successfully",
            "file_id": saved_filename,
            "upload_time": datetime.now().isoformat(),
            "ocr_data": ocr_result,
        }), 200

    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Error in upload_image: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/ocr", methods=["POST"])
def process_ocr():
    try:
        data = request.get_json(silent=True) or {}
        file_id = data.get("file_id")
        if not file_id:
            return jsonify({"status": "error", "message": "file_id required"}), 400

        filepath = os.path.join(app.config["UPLOAD_FOLDER"], file_id)
        if not os.path.exists(filepath):
            return jsonify({"status": "error", "message": "File not found"}), 404

        ocr_result = extract_text_from_image(filepath)
        return jsonify({
            "status": "success",
            "file_id": file_id,
            "ocr_data": ocr_result,
        }), 200

    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Error in process_ocr: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/text-extraction", methods=["POST"])
def extract_text():
    return upload_image()


@app.route("/api/find-specialists", methods=["POST"])
def find_specialists_route():
    """Find nearby pharmacies / specialists for a medication. Returns up to 5."""
    try:
        api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
        if not api_key:
            return jsonify({
                "status": "error",
                "message": "GOOGLE_MAPS_API_KEY is not configured on the backend",
            }), 500

        data = request.get_json(silent=True) or {}
        medication_name = str(data.get("medication_name", "")).strip()
        user_location = data.get("user_location", {})

        if not medication_name:
            return jsonify({"status": "error", "message": "medication_name is required"}), 400

        if not isinstance(user_location, dict):
            return jsonify({"status": "error", "message": "user_location must be an object"}), 400

        lat = user_location.get("lat")
        lng = user_location.get("lng")
        if lat is None or lng is None:
            city = str(user_location.get("city", "")).strip()
            country = str(user_location.get("country", "")).strip()
            if not city or not country:
                return jsonify({
                    "status": "error",
                    "message": "Provide user_location.lat/lng or user_location.city and user_location.country",
                }), 400

            geocoded = geocode_location(city, country, api_key)
            lat = geocoded["lat"]
            lng = geocoded["lng"]
            user_location = {
                **user_location,
                "city": city,
                "country": country,
                "formatted_address": geocoded["formatted_address"],
                "lat": lat,
                "lng": lng,
            }

        try:
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            return jsonify({
                "status": "error",
                "message": "user_location coordinates must be numeric",
            }), 400

        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return jsonify({
                "status": "error",
                "message": "user_location coordinates are out of range",
            }), 400

        radius = data.get("radius", 5000)
        try:
            radius = int(radius)
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "radius must be an integer"}), 400

        if radius < 1000 or radius > 10000:
            return jsonify({
                "status": "error",
                "message": "radius must be between 1000 and 10000 meters",
            }), 400

        specialist_types, specialists, warnings = find_specialists_service(
            medication_name, lat, lng, radius, api_key
        )

        return jsonify({
            "status": "success",
            "medication_name": medication_name,
            "specialist_types": specialist_types,
            "search_radius_meters": radius,
            "user_location": user_location,
            "count": len(specialists),
            "warnings": warnings,
            "specialists": specialists,
        }), 200

    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Error in find_specialists: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.errorhandler(413)
def request_entity_too_large(_error):
    return jsonify({"status": "error", "message": "File too large. Maximum size: 16MB"}), 413


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(_error):
    return jsonify({"status": "error", "message": "Internal server error"}), 500


if __name__ == "__main__":
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    port = int(os.environ.get("PORT", "5001"))
    app.run(debug=True, host="0.0.0.0", port=port)
