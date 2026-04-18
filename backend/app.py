"""
Prescription Bottle Analysis Backend
Flask application for image upload and OCR processing
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from paddleocr import PaddleOCR
import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
import cv2
import numpy as np
from PIL import Image
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}

# Initialize OCR model (PaddleOCR - excellent for curved text and glare)
# lang=['en'] for English, can be extended for multilingual
# use_angle_cls=True helps with rotated text
# use_gpu=False for CPU, set to True if GPU available
logger.info("Initializing PaddleOCR model...")
ocr = PaddleOCR(use_angle_cls=True, lang=['en'], use_gpu=False)
logger.info("PaddleOCR model loaded successfully")

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def preprocess_image(image_path):
    """
    Preprocess image to improve OCR accuracy
    - Denoise to reduce glare effects
    - Enhance contrast
    - Correct skew if needed
    """
    img = cv2.imread(image_path)
    
    if img is None:
        raise ValueError("Could not read image")
    
    # Apply denoising to reduce glare
    denoised = cv2.fastNlMeansDenoisingColored(img, None, h=10, hForColorComponents=10, templateWindowSize=7, searchWindowSize=21)
    
    # Enhance contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization)
    lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    enhanced = cv2.merge([l, a, b])
    enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    
    return enhanced

def save_uploaded_file(file):
    """Save uploaded file with unique identifier"""
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    filename = secure_filename(file.filename)
    unique_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_extension = os.path.splitext(filename)[1]
    
    saved_filename = f"{timestamp}_{unique_id}{file_extension}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
    
    file.save(filepath)
    return filepath, saved_filename

def extract_text_from_image(image_path):
    """
    Extract text from prescription bottle image using PaddleOCR
    Returns structured data with text and confidence scores
    """
    try:
        # Preprocess image for better OCR accuracy
        preprocessed_img = preprocess_image(image_path)
        
        # Save preprocessed image temporarily for OCR
        temp_path = image_path.replace('.', '_preprocessed.')
        cv2.imwrite(temp_path, preprocessed_img)
        
        # Run OCR
        result = ocr.ocr(temp_path, cls=True)
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        if not result or not result[0]:
            return {"status": "error", "message": "No text detected in image"}
        
        # Structure the results
        extracted_text = []
        for line in result[0]:
            text = line[1][0]  # Extracted text
            confidence = line[1][1]  # Confidence score
            bbox = line[0]  # Bounding box coordinates
            
            extracted_text.append({
                "text": text,
                "confidence": float(confidence),
                "bbox": bbox
            })
        
        # Combine all text for summary
        full_text = " ".join([item["text"] for item in extracted_text])
        
        return {
            "status": "success",
            "full_text": full_text,
            "structured_results": extracted_text,
            "text_count": len(extracted_text),
            "average_confidence": float(np.mean([item["confidence"] for item in extracted_text]))
        }
    
    except Exception as e:
        logger.error(f"Error during OCR processing: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "PrescriptionOCR"}), 200

@app.route('/api/upload', methods=['POST'])
def upload_image():
    """
    Handle image upload and OCR processing
    Expected: multipart/form-data with 'file' field
    Returns: Extracted text and metadata
    """
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file provided"}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"status": "error", "message": "No file selected"}), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                "status": "error",
                "message": f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            }), 400
        
        # Save uploaded file
        filepath, saved_filename = save_uploaded_file(file)
        logger.info(f"File saved: {saved_filename}")
        
        # Extract text using OCR
        ocr_result = extract_text_from_image(filepath)
        
        if ocr_result["status"] == "error":
            # Clean up file if OCR failed
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify(ocr_result), 400
        
        # Return success response
        response = {
            "status": "success",
            "message": "Image processed successfully",
            "file_id": saved_filename,
            "upload_time": datetime.now().isoformat(),
            "ocr_data": ocr_result
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Error in upload_image: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/ocr', methods=['POST'])
def process_ocr():
    """
    Alternative endpoint to process OCR on an already uploaded image
    Expected: JSON with 'file_id' field
    """
    try:
        data = request.get_json()
        
        if not data or 'file_id' not in data:
            return jsonify({"status": "error", "message": "file_id required"}), 400
        
        file_id = data['file_id']
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
        
        if not os.path.exists(filepath):
            return jsonify({"status": "error", "message": "File not found"}), 404
        
        # Extract text using OCR
        ocr_result = extract_text_from_image(filepath)
        
        response = {
            "status": "success",
            "file_id": file_id,
            "ocr_data": ocr_result
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Error in process_ocr: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/text-extraction', methods=['POST'])
def extract_text():
    """
    Process image file directly and return extracted text
    This endpoint combines upload and OCR in one step
    """
    return upload_image()

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error"""
    return jsonify({
        "status": "error",
        "message": "File too large. Maximum size: 16MB"
    }), 413

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({"status": "error", "message": "Internal server error"}), 500

if __name__ == '__main__':
    # Create uploads directory if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Run Flask app (use debug=False for production)
    app.run(debug=True, host='0.0.0.0', port=5000)
