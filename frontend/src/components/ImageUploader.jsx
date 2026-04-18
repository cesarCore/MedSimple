import React, { useState, useRef } from 'react';
import './ImageUploader.css';

/**
 * ImageUploader Component
 * Handles prescription bottle image upload and OCR processing
 */
const ImageUploader = () => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [extractedText, setExtractedText] = useState(null);
  const [error, setError] = useState(null);
  const [confidence, setConfidence] = useState(null);
  const fileInputRef = useRef(null);

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

  /**
   * Handle file selection from input
   */
  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    // Validate file type
    const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/bmp'];
    if (!allowedTypes.includes(file.type)) {
      setError('Invalid file type. Please upload an image file (PNG, JPG, GIF, BMP)');
      return;
    }

    // Validate file size (16MB)
    if (file.size > 16 * 1024 * 1024) {
      setError('File too large. Maximum size: 16MB');
      return;
    }

    setSelectedFile(file);
    setError(null);

    // Create preview
    const reader = new FileReader();
    reader.onloadend = () => {
      setPreview(reader.result);
    };
    reader.readAsDataURL(file);
  };

  /**
   * Handle drag and drop
   */
  const handleDragOver = (event) => {
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.classList.add('drag-over');
  };

  const handleDragLeave = (event) => {
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.classList.remove('drag-over');
  };

  const handleDrop = (event) => {
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.classList.remove('drag-over');

    const files = event.dataTransfer.files;
    if (files.length > 0) {
      setSelectedFile(files[0]);

      // Create preview
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreview(reader.result);
      };
      reader.readAsDataURL(files[0]);
      setError(null);
    }
  };

  /**
   * Upload image and process OCR
   */
  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Please select an image first');
      return;
    }

    setLoading(true);
    setError(null);
    setExtractedText(null);
    setConfidence(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await fetch(`${API_BASE_URL}/api/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Upload failed');
      }

      const data = await response.json();

      if (data.status === 'success') {
        setExtractedText(data.ocr_data.full_text);
        setConfidence(data.ocr_data.average_confidence);
      } else {
        setError(data.message || 'OCR processing failed');
      }
    } catch (err) {
      setError(`Error: ${err.message}`);
      console.error('Upload error:', err);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Clear all data and reset form
   */
  const handleReset = () => {
    setSelectedFile(null);
    setPreview(null);
    setExtractedText(null);
    setConfidence(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  /**
   * Trigger file input click
   */
  const triggerFileInput = () => {
    fileInputRef.current?.click();
  };

  /**
   * Copy extracted text to clipboard
   */
  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(extractedText);
      alert('Text copied to clipboard!');
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className="image-uploader">
      <div className="uploader-container">
        <h1>Prescription Bottle OCR</h1>
        <p className="subtitle">Upload an image of your prescription bottle to extract text</p>

        {/* Drop Zone */}
        <div
          className="drop-zone"
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={triggerFileInput}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />

          {preview ? (
            <div className="preview-container">
              <img src={preview} alt="Preview" className="preview-image" />
              <button className="change-button" onClick={(e) => {
                e.stopPropagation();
                triggerFileInput();
              }}>
                Change Image
              </button>
            </div>
          ) : (
            <div className="drop-zone-content">
              <svg className="drop-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4m17-8l-8-8m0 0L5 7m8-8v12" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <p className="drop-text">Drag and drop your image here</p>
              <p className="drop-subtext">or click to select a file</p>
              <p className="file-format">Supported: PNG, JPG, GIF, BMP (Max 16MB)</p>
            </div>
          )}
        </div>

        {/* Selected File Info */}
        {selectedFile && (
          <div className="file-info">
            <p><strong>File:</strong> {selectedFile.name}</p>
            <p><strong>Size:</strong> {(selectedFile.size / 1024).toFixed(2)} KB</p>
            <p><strong>Type:</strong> {selectedFile.type}</p>
          </div>
        )}

        {/* Error Message */}
        {error && <div className="error-message">{error}</div>}

        {/* Action Buttons */}
        <div className="button-group">
          <button
            className="button button-primary"
            onClick={handleUpload}
            disabled={!selectedFile || loading}
          >
            {loading ? 'Processing...' : 'Extract Text from Image'}
          </button>
          {(selectedFile || extractedText) && (
            <button
              className="button button-secondary"
              onClick={handleReset}
              disabled={loading}
            >
              Clear
            </button>
          )}
        </div>

        {/* Results Section */}
        {extractedText && (
          <div className="results-container">
            <h2>Extracted Text</h2>
            {confidence && (
              <div className="confidence-bar">
                <p className="confidence-label">Confidence Score</p>
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{
                      width: `${confidence * 100}%`,
                      backgroundColor: confidence > 0.8 ? '#4CAF50' : confidence > 0.6 ? '#FFC107' : '#FF5252'
                    }}
                  />
                </div>
                <p className="confidence-percentage">{(confidence * 100).toFixed(2)}%</p>
              </div>
            )}

            <div className="text-output">
              <textarea
                className="text-area"
                value={extractedText}
                readOnly
              />
              <button
                className="copy-button"
                onClick={copyToClipboard}
                title="Copy to clipboard"
              >
                📋 Copy Text
              </button>
            </div>

            <p className="next-step">
              This extracted text will be passed to the research agent for ingredient and side effects analysis.
            </p>
          </div>
        )}

        {/* Loading Spinner */}
        {loading && (
          <div className="loading">
            <div className="spinner" />
            <p>Processing image... This may take a moment</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ImageUploader;
