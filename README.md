# Prescription Bottle OCR Analysis Application

A full-stack web application that uses OCR technology to extract text from prescription bottle images, which is then analyzed by AI agents for side effects and ingredient research, and used to find local specialists.

## Project Architecture

```
HootHacks_Project/
├── backend/
│   ├── app.py                 # Flask backend with OCR integration
│   ├── requirements.txt       # Python dependencies
│   ├── .env.example          # Environment variables template
│   └── uploads/              # Directory for storing uploaded images
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ImageUploader.jsx    # Main image upload component
│   │   │   └── ImageUploader.css    # Styling for uploader
│   │   ├── App.jsx           # Main App component
│   │   ├── App.css           # App styling
│   │   ├── index.jsx         # React entry point
│   │   └── index.css         # Global styles
│   ├── public/
│   │   └── index.html        # HTML template
│   ├── package.json          # Frontend dependencies
│   └── .env                  # Frontend environment variables
└── README.md                 # This file
```

## Features

### Image Upload & Processing
- **Drag-and-drop interface** for easy image uploading
- **File preview** before processing
- **Supported formats**: PNG, JPG, JPEG, GIF, BMP
- **File size limit**: 16MB

### OCR (Optical Character Recognition)
- **Model**: PaddleOCR from Hugging Face
- **Optimized for**:
  - Curved text on cylindrical surfaces
  - Glare and reflections from plastic bottles
  - Rotated and skewed text
  - Multi-line text extraction
- **Image preprocessing**:
  - Denoising to reduce glare effects
  - Contrast enhancement using CLAHE
  - Automatic angle correction

### Text Extraction Results
- **Full extracted text** from prescription bottle
- **Confidence scores** for each detected text block
- **Structured results** with bounding boxes
- **Average confidence** display for quality assessment
- **Copy to clipboard** functionality

### Backend API
- **POST /api/upload** - Upload image and get OCR results
- **POST /api/ocr** - Process OCR on existing image
- **GET /health** - Health check endpoint

## Installation & Setup

### Prerequisites
- Python 3.8 or higher
- Node.js 16 or higher
- npm or yarn package manager

### Backend Setup

1. **Navigate to backend directory**:
```bash
cd backend
```

2. **Create a Python virtual environment**:
```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

3. **Install Python dependencies**:
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**:
```bash
cp .env.example .env
# Edit .env file with your configuration if needed
```

5. **Run the Flask backend**:
```bash
python app.py
```

The backend will start on `http://localhost:5000`

### Frontend Setup

1. **Navigate to frontend directory**:
```bash
cd frontend
```

2. **Install Node dependencies**:
```bash
npm install
```

3. **Start the React development server**:
```bash
npm start
```

The frontend will automatically open at `http://localhost:3000`

## Usage

1. **Open the application** in your browser at `http://localhost:3000`
2. **Upload an image** of a prescription bottle by:
   - Clicking the drop zone to select a file, or
   - Dragging and dropping an image onto the drop zone
3. **Click "Extract Text from Image"** to process the image
4. **View results** including:
   - Extracted text from the bottle label
   - Confidence score of the OCR detection
   - Copy button to copy extracted text

## OCR Model Details

### PaddleOCR
- **Why PaddleOCR?**
  - Excellent at handling curved text on cylindrical surfaces
  - Built-in support for text angle classification
  - Lightweight model suitable for web deployment
  - Good performance with glare and reflections
  - Open-source and free

- **Configuration**:
  - Language: English (can be extended)
  - Angle classification: Enabled
  - GPU support: Optional (CPU mode by default)

### Image Preprocessing
The backend applies several preprocessing steps to improve OCR accuracy:

1. **Denoising**: FastNlMeansDenoising to reduce glare and noise
2. **Contrast Enhancement**: CLAHE (Contrast Limited Adaptive Histogram Equalization)
3. **Angle Detection**: Automatic rotation correction

## API Documentation

### POST /api/upload
Upload an image and get OCR results

**Request**:
```
Content-Type: multipart/form-data
Body: {
  "file": <binary image data>
}
```

**Response (Success)**:
```json
{
  "status": "success",
  "message": "Image processed successfully",
  "file_id": "20240418_120530_abc123.jpg",
  "upload_time": "2024-04-18T12:05:30.123456",
  "ocr_data": {
    "status": "success",
    "full_text": "Aspirin 500mg...",
    "structured_results": [
      {
        "text": "Aspirin",
        "confidence": 0.98,
        "bbox": [[x1, y1], [x2, y2], ...]
      }
    ],
    "text_count": 15,
    "average_confidence": 0.95
  }
}
```

**Response (Error)**:
```json
{
  "status": "error",
  "message": "Error description"
}
```

## Performance Considerations

- **Image Processing Time**: 2-5 seconds depending on image quality
- **Model Memory**: ~250MB RAM
- **Optimal Image Size**: 1080x1920px to 2160x3840px
- **Recommended Lighting**: Well-lit environment, minimize glare on bottle

## Next Steps in the Pipeline

After image upload and OCR:
1. **Research Agent** → Pass extracted text to PubMed API for ingredient/side effects research
2. **Summary Generation** → Create concise summary of findings
3. **Specialist Finder** → Use Google Maps API to locate local specialists

## Environment Variables

### Backend (.env)
```
FLASK_ENV=development
FLASK_DEBUG=True
MAX_FILE_SIZE=16777216
OCR_USE_GPU=False
OCR_LANGUAGE=en
API_PORT=5000
API_HOST=0.0.0.0
CORS_ORIGINS=["http://localhost:3000", "http://localhost:5000"]
```

### Frontend (.env)
```
REACT_APP_API_URL=http://localhost:5000
```

## Troubleshooting

### PaddleOCR model download fails
- The model will be automatically downloaded on first use (~100MB)
- Ensure you have internet connectivity
- Check Python downloads directory permissions

### CORS errors
- Ensure `CORS_ORIGINS` in backend .env includes frontend URL
- Flask-CORS should handle this automatically

### Image processing times out
- Large or complex images may take longer
- Try reducing image dimensions
- Ensure backend has sufficient resources

## Technologies Used

### Backend
- **Flask** 3.0.0 - Web framework
- **PaddleOCR** 2.7.0 - OCR model
- **OpenCV** 4.8.1 - Image processing
- **Pillow** 10.1.0 - Image manipulation
- **Flask-CORS** 4.0.0 - CORS handling

### Frontend
- **React** 18.2.0 - UI framework
- **CSS3** - Styling with animations
- **Fetch API** - HTTP requests

## File Structure Explained

```
backend/app.py
├── Flask app initialization
├── OCR model initialization (PaddleOCR)
├── Image preprocessing pipeline
├── API routes:
│   ├── /health - Health check
│   ├── /api/upload - Main upload endpoint
│   ├── /api/ocr - Process stored image
│   └── /api/text-extraction - Combined upload + OCR
└── Error handlers

frontend/src/components/ImageUploader.jsx
├── React component with hooks
├── File upload handling
├── Drag-and-drop functionality
├── API integration
├── Results display
└── Accessibility features
```

## Future Enhancements

- [ ] GPU acceleration support for faster processing
- [ ] Multi-language OCR support
- [ ] Batch image processing
- [ ] Image quality feedback
- [ ] OCR result editing interface
- [ ] Database integration for history
- [ ] Authentication and user accounts
- [ ] Integration with PubMed research API
- [ ] Integration with Google Maps API for specialist finder
- [ ] Mobile app version

## License

MIT License - Feel free to use this project for educational and commercial purposes

## Support

For issues or questions, please check:
1. Backend logs in terminal
2. Browser console for frontend errors
3. OCR model initialization logs
