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
    from backend.analysis_service import analyze as analyze_service
except ModuleNotFoundError:
    from ocr_service import extract_text_from_image
    from specialist_service import find_specialists as find_specialists_service, geocode_location
    from analysis_service import analyze as analyze_service

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
    cors_origins = os.getenv("CORS_ORIGINS", "*").strip()
    if cors_origins == "*":
        CORS(app)
    else:
        origins = [o.strip() for o in cors_origins.split(",") if o.strip()]
        CORS(app, resources={r"/api/*": {"origins": origins}})
else:
    logger.warning("flask_cors is not installed; running without CORS support")

app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def build_ocr_response(ocr_result, file_id, original_filename):
    """Flatten ocr_service result into the OCR-agent contract shape."""
    return {
        "status": "success",
        "source_type": "image",
        "file_id": file_id,
        "engine": ocr_result.get("engine", "unknown"),
        "full_text": ocr_result.get("full_text", ""),
        "text_count": ocr_result.get("text_count", 0),
        "average_confidence": ocr_result.get("average_confidence", 0.0),
        "structured_results": ocr_result.get("structured_results", []),
        "metadata": {
            "filename": original_filename,
            "processed_at": datetime.now().isoformat(),
        },
    }


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

        original_filename = secure_filename(file.filename)
        filepath, saved_filename = save_uploaded_file(file)
        logger.info("File saved: %s", saved_filename)

        ocr_result = extract_text_from_image(filepath)
        if ocr_result["status"] == "error":
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify(ocr_result), 400

        response = build_ocr_response(ocr_result, saved_filename, original_filename)
        # Keep `ocr_data` alias for any older frontend builds still reading it.
        response["ocr_data"] = ocr_result
        return jsonify(response), 200

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
        if ocr_result["status"] == "error":
            return jsonify(ocr_result), 400

        response = build_ocr_response(ocr_result, file_id, file_id)
        response["ocr_data"] = ocr_result
        return jsonify(response), 200

    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Error in process_ocr: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/text-extraction", methods=["POST"])
def extract_text():
    return upload_image()


@app.route("/api/analyze", methods=["POST"])
def analyze_route():
    """Run the Analysis agent on an OCR payload. Returns clinical findings + citations."""
    try:
        data = request.get_json(silent=True) or {}
        ocr_payload = data.get("ocr")
        if not isinstance(ocr_payload, dict) or not ocr_payload.get("full_text"):
            return jsonify({
                "status": "error",
                "message": "ocr.full_text is required",
            }), 400

        user_context = data.get("user_context") or {}
        if not isinstance(user_context, dict):
            return jsonify({"status": "error", "message": "user_context must be an object"}), 400

        result = analyze_service(
            ocr_payload,
            user_context=user_context,
            pubmed_api_key=os.getenv("PUBMED_API_KEY") or None,
        )
        return jsonify(result), 200

    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Error in analyze_route: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/pipeline", methods=["POST"])
def pipeline_route():
    """Orchestrator: OCR an uploaded file, analyze it, and (optionally) find specialists."""
    try:
        if "file" not in request.files:
            return jsonify({"status": "error", "message": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "" or not allowed_file(file.filename):
            return jsonify({"status": "error", "message": "Invalid file"}), 400

        original_filename = secure_filename(file.filename)
        filepath, saved_filename = save_uploaded_file(file)

        ocr_result = extract_text_from_image(filepath)
        if ocr_result["status"] == "error":
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify(ocr_result), 400

        ocr_response = build_ocr_response(ocr_result, saved_filename, original_filename)

        user_context_raw = request.form.get("user_context") or "{}"
        try:
            import json as _json
            user_context = _json.loads(user_context_raw)
        except (TypeError, ValueError):
            user_context = {}

        analysis = analyze_service(
            ocr_response,
            user_context=user_context,
            pubmed_api_key=os.getenv("PUBMED_API_KEY") or None,
        )

        specialists_block = None
        location_raw = request.form.get("user_location")
        if location_raw:
            try:
                import json as _json
                user_location = _json.loads(location_raw)
            except (TypeError, ValueError):
                user_location = None

            api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
            if user_location and api_key:
                lat = user_location.get("lat")
                lng = user_location.get("lng")
                if lat is not None and lng is not None:
                    try:
                        radius = int(request.form.get("radius", 5000))
                    except (TypeError, ValueError):
                        radius = 5000
                    med_name = (
                        (analysis.get("product") or {}).get("normalized_name")
                        or (analysis.get("ingredients") or [{}])[0].get("name_normalized")
                        or ""
                    )
                    if med_name:
                        types, specialists, warnings = find_specialists_service(
                            med_name, float(lat), float(lng), radius, api_key
                        )
                        specialists_block = {
                            "medication_name": med_name,
                            "specialist_types": types,
                            "search_radius_meters": radius,
                            "count": len(specialists),
                            "warnings": warnings,
                            "specialists": specialists,
                        }

        return jsonify({
            "status": "success",
            "ocr": ocr_response,
            "analysis": analysis,
            "specialists": specialists_block,
        }), 200

    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Error in pipeline_route: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500


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
