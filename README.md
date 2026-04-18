# Prescription Bottle OCR Analysis Application

A full-stack application that extracts text from medication or supplement images, supports downstream AI analysis, and can find nearby specialists using Google Maps.

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
- **Primary engine order**:
  - EasyOCR when installed
  - PaddleOCR when installed
  - Tesseract fallback
- **Image preprocessing**:
  - Denoising to reduce glare effects
  - Contrast enhancement using CLAHE
- **Works on**:
  - prescription labels
  - supplement facts panels
  - photographed bottle / package text

### Text Extraction Results
- **Full extracted text** from prescription bottle
- **Confidence scores** for each detected text block
- **Structured results** with bounding boxes
- **Average confidence** display for quality assessment
- **Copy to clipboard** functionality

### Backend API
- **POST /api/upload** - Upload image and get OCR results
- **POST /api/ocr** - Process OCR on existing image
- **POST /api/find-specialists** - Find up to 5 nearby specialists / pharmacies
- **GET /health** - Health check endpoint

## Installation & Setup

### Prerequisites
- Python 3.8 or higher
- Node.js 16 or higher
- npm or yarn package manager

## Quick Start

### 1. Configure Environment

Create the root `.env` file if it does not already exist:

```bash
cp backend/.env.example .env
```

Then fill in the API keys you actually want to use:

```ini
PUBMED_API_KEY=your_pubmed_key
OPENAI_API_KEY=your_openai_key
GOOGLE_MAPS_API_KEY=your_google_maps_key
```

The backend now loads the project root `.env` automatically.

### 2. Start the Backend

```bash
source backend/.venv312/bin/activate
PORT=5001 python backend/app.py
```

The backend will run at `http://localhost:5001`

### 3. Start the Frontend

```bash
cd frontend
npm install
npm start
```

The frontend will run at `http://localhost:3000`

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
5. **Click "Find Specialists In This Area"** after OCR completes
6. **Enter city and country** and search up to 5 nearby specialists / pharmacies
7. **Click a result** to preview its location on the embedded map

## Useful Commands

### Run backend
```bash
source backend/.venv312/bin/activate
PORT=5001 python backend/app.py
```

### Run frontend
```bash
cd frontend
npm start
```

### Run backend tests
```bash
source backend/.venv312/bin/activate
python -m unittest discover -s backend/tests -v
```

### Run specialist route / service tests only
```bash
source backend/.venv312/bin/activate
python -m unittest backend.tests.test_specialist_service backend.tests.test_routes -v
```

### Build frontend
```bash
cd frontend
npm run build
```

### Health check
```bash
curl http://localhost:5001/health
```

### OCR upload test
```bash
curl -F "file=@tests/IMG_7027.webp" http://localhost:5001/api/upload
```

### Specialist lookup test
```bash
curl -X POST http://localhost:5001/api/find-specialists \
  -H "Content-Type: application/json" \
  -d '{
    "medication_name": "Metformin for diabetes",
    "user_location": {
      "city": "Boston",
      "country": "United States"
    },
    "radius": 5000
  }'
```

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
1. **Research Agent** → Pass extracted text to PubMed API for ingredient / side-effect research
2. **Analysis Agent** → Use OpenAI API for extraction, normalization, and summarization
3. **Specialist Finder** → Use Google Maps API to locate local specialists

## Environment Variables

### Root `.env`
```
FLASK_ENV=development
FLASK_DEBUG=True
MAX_FILE_SIZE=16777216
OCR_USE_GPU=False
OCR_LANGUAGE=en
API_PORT=5001
API_HOST=0.0.0.0
PUBMED_API_KEY=your_pubmed_key
OPENAI_API_KEY=your_openai_key
GOOGLE_MAPS_API_KEY=your_google_maps_key
CORS_ORIGINS=["http://localhost:3000", "http://localhost:5001"]
```

### Frontend (.env)
```
REACT_APP_API_URL=http://localhost:5001
```

## Troubleshooting

### CORS errors
- Ensure `CORS_ORIGINS` in backend .env includes frontend URL
- Flask-CORS should handle this automatically

### Google Maps specialist search fails
- Ensure `GOOGLE_MAPS_API_KEY` is present in the root `.env`
- The frontend sends `city` + `country`; the backend geocodes them before nearby search
- Results are limited to 5 entries

### Image processing times out
- Large or complex images may take longer
- Try reducing image dimensions
- Ensure backend has sufficient resources

## Technologies Used

### Backend
- **Flask** - Web framework
- **EasyOCR / PaddleOCR / Tesseract** - OCR engines
- **OpenCV** - Image processing
- **Pillow** - Image handling
- **Flask-CORS** - CORS handling
- **Google Maps Places + Geocoding APIs** - Specialist lookup

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
