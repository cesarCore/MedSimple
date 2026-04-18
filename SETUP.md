# Getting Started Guide - Prescription Bottle OCR App

This guide will help you set up and run the Prescription Bottle OCR Analysis application on your local machine.

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Backend Setup](#backend-setup)
3. [Frontend Setup](#frontend-setup)
4. [Running the Application](#running-the-application)
5. [Testing the Application](#testing-the-application)
6. [Troubleshooting](#troubleshooting)

## System Requirements

### Minimum Requirements
- **CPU**: Dual-core processor
- **RAM**: 4GB (8GB recommended)
- **Disk Space**: 2GB free space
- **Internet**: Needed for downloading model on first run

### Software Requirements
- **Python 3.8+**: [Download Python](https://www.python.org/downloads/)
- **Node.js 16+**: [Download Node.js](https://nodejs.org/)
- **npm 7+**: Comes with Node.js
- **Git**: [Download Git](https://git-scm.com/)

## Backend Setup

### Step 1: Navigate to Backend Directory
```bash
cd backend
```

### Step 2: Create Virtual Environment
```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Note**: First installation may take 5-10 minutes as PaddleOCR model is downloaded (~100MB)

### Step 4: Configure Environment
```bash
cp .env.example .env
```

Edit `.env` file if you need to change any settings:
- `FLASK_DEBUG`: Set to `False` for production
- `OCR_USE_GPU`: Set to `True` if you have CUDA-capable GPU
- `API_PORT`: Default is 5000

### Step 5: Verify Installation
```bash
python app.py
```

You should see output like:
```
Initializing PaddleOCR model...
PaddleOCR model loaded successfully
 * Running on http://0.0.0.0:5000
```

Press `Ctrl+C` to stop the server.

## Frontend Setup

### Step 1: Navigate to Frontend Directory
```bash
cd frontend
```

### Step 2: Install Dependencies
```bash
npm install
```

This may take 2-3 minutes.

### Step 3: Configure API URL
The `.env` file is already configured to point to `http://localhost:5000`. If your backend runs on a different URL, edit `.env`:

```
REACT_APP_API_URL=http://localhost:5000
```

### Step 4: Verify Installation
```bash
npm start
```

This will automatically open your browser to `http://localhost:3000`

## Running the Application

### Terminal 1: Start Backend
```bash
cd backend

# Activate virtual environment (if not already activated)
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

python app.py
```

**Expected output**:
```
Initializing PaddleOCR model...
PaddleOCR model loaded successfully
 * Running on http://0.0.0.0:5000
```

### Terminal 2: Start Frontend
```bash
cd frontend
npm start
```

**Expected output**:
```
Compiled successfully!
You can now view prescription-ocr-frontend in the browser.
Local: http://localhost:3000
```

### Access the Application
Open your browser and navigate to: `http://localhost:3000`

You should see the prescription bottle OCR interface with a purple gradient background.

## Testing the Application

### Manual Testing Steps

1. **Test Image Upload**:
   - Click on the drop zone or drag an image
   - Supported formats: PNG, JPG, JPEG, GIF, BMP
   - File size limit: 16MB

2. **Test with Sample Image**:
   - Use any image with text
   - For best results, use a decently lit image

3. **Verify OCR Results**:
   - Check that text is extracted
   - Look for confidence score > 0.7
   - Verify extracted text makes sense

4. **Test Copy Function**:
   - Click "Copy Text" button
   - Paste in a text editor to verify

### API Testing with cURL

```bash
# Test health check
curl http://localhost:5000/health

# Test image upload (replace image.jpg with actual file)
curl -F "file=@image.jpg" http://localhost:5000/api/upload
```

## Troubleshooting

### Backend Issues

#### Issue: Python not found
**Solution**:
```bash
# On Windows, use python3 instead
python3 --version
pip3 install -r requirements.txt
python3 app.py
```

#### Issue: PaddleOCR model fails to download
**Solution**:
- Check internet connection
- Model is ~100MB, ensure you have space
- Try again - downloads sometimes fail on first attempt
- Check Python temp directory permissions

#### Issue: Port 5000 already in use
**Solution**:
```bash
# Change port in .env file
# Or kill the process using port 5000

# Windows:
netstat -ano | findstr :5000
taskkill /PID <process_id> /F

# macOS/Linux:
lsof -i :5000
kill -9 <process_id>
```

#### Issue: CORS errors in browser console
**Solution**:
- Ensure backend is running on http://localhost:5000
- Check CORS_ORIGINS in backend .env file
- Restart both frontend and backend

### Frontend Issues

#### Issue: npm install fails
**Solution**:
```bash
# Clear npm cache
npm cache clean --force
rm -rf node_modules package-lock.json

# Try again
npm install
```

#### Issue: Port 3000 already in use
**Solution**:
```bash
# Windows:
netstat -ano | findstr :3000
taskkill /PID <process_id> /F

# macOS/Linux:
lsof -i :3000
kill -9 <process_id>
```

#### Issue: Blank white page or errors in console
**Solution**:
- Open browser console (F12)
- Check for specific error messages
- Ensure backend is running
- Clear browser cache: Ctrl+Shift+Delete

### OCR Issues

#### Issue: Low confidence scores (< 0.5)
**Causes and Solutions**:
- Poor image quality → Use clearer images
- Bad lighting → Improve lighting
- Curved text not recognized → This is normal, PaddleOCR handles some curve
- Partial bottle view → Capture more of the label

#### Issue: No text detected
**Solutions**:
- Verify image contains text
- Try with different image angle
- Ensure image is in supported format
- Check file isn't corrupted

#### Issue: Slow processing (> 10 seconds)
**Solutions**:
- Enable GPU acceleration (set `OCR_USE_GPU=True`)
- Reduce image resolution
- Close other applications
- Restart backend service

## Performance Optimization

### For Production Deployment:
1. Set `FLASK_DEBUG=False` in backend .env
2. Use a production WSGI server (e.g., Gunicorn)
3. Enable GPU acceleration if available
4. Implement image compression on frontend
5. Add caching for frequently processed images

### For Development:
- Current setup is optimized for development
- Reload behaviors are enabled for faster iteration

## Next Steps

1. **Verify Setup**: Run test image through OCR
2. **Integrate Research Agent**: Connect to PubMed API
3. **Add Specialist Finder**: Integrate Google Maps API
4. **Deploy**: Use Docker/Docker Compose for containerization

## Support Resources

- **PaddleOCR Docs**: https://github.com/PaddlePaddle/PaddleOCR
- **Flask Docs**: https://flask.palletsprojects.com/
- **React Docs**: https://react.dev/
- **OpenCV Docs**: https://docs.opencv.org/

---

**Created**: April 2024
**Last Updated**: April 2024
