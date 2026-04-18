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
  const [specialistOpen, setSpecialistOpen] = useState(false);
  const [specialistLoading, setSpecialistLoading] = useState(false);
  const [specialistError, setSpecialistError] = useState(null);
  const [specialistResults, setSpecialistResults] = useState(null);
  const [locationCity, setLocationCity] = useState('');
  const [locationCountry, setLocationCountry] = useState('');
  const [selectedSpecialist, setSelectedSpecialist] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);
  const fileInputRef = useRef(null);
  const cameraInputRef = useRef(null);

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';

  /**
   * Handle file selection from input
   */
  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    // Validate file type
    const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/bmp', 'image/webp'];
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
    setSpecialistOpen(false);
    setSpecialistLoading(false);
    setSpecialistError(null);
    setSpecialistResults(null);
    setSelectedSpecialist(null);
    setAnalysis(null);
    setAnalysisError(null);

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
        runAnalysis(data);
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
    setSpecialistOpen(false);
    setSpecialistLoading(false);
    setSpecialistError(null);
    setSpecialistResults(null);
    setSelectedSpecialist(null);
    setLocationCity('');
    setLocationCountry('');
    setAnalysis(null);
    setAnalysisError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    if (cameraInputRef.current) {
      cameraInputRef.current.value = '';
    }
  };

  const runAnalysis = async (uploadData) => {
    setAnalysisLoading(true);
    setAnalysisError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ocr: {
            full_text: uploadData.ocr_data.full_text,
            average_confidence: uploadData.ocr_data.average_confidence,
            structured_results: uploadData.ocr_data.structured_results || [],
          },
        }),
      });
      const data = await response.json();
      if (!response.ok || data.status !== 'success') {
        throw new Error(data.message || 'Analysis failed');
      }
      setAnalysis(data);
    } catch (err) {
      setAnalysisError(err.message);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const handleFindSpecialists = async () => {
    if (!extractedText) {
      setSpecialistError('Extract text from the image before searching for specialists.');
      return;
    }

    if (!locationCity.trim() || !locationCountry.trim()) {
      setSpecialistError('Enter both city and country to search for specialists.');
      return;
    }

    setSpecialistLoading(true);
    setSpecialistError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/find-specialists`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          medication_name: extractedText,
          user_location: {
            city: locationCity.trim(),
            country: locationCountry.trim(),
          },
          radius: 5000,
        }),
      });

      const data = await response.json();
      if (!response.ok || data.status !== 'success') {
        throw new Error(data.message || 'Specialist search failed');
      }

      setSpecialistResults(data);
      setSelectedSpecialist(data.specialists?.[0] || null);
    } catch (err) {
      setSpecialistError(`Error: ${err.message}`);
      setSpecialistResults(null);
      setSelectedSpecialist(null);
    } finally {
      setSpecialistLoading(false);
    }
  };

  const embeddedMapUrl = selectedSpecialist
    ? `https://www.google.com/maps?q=${selectedSpecialist.latitude},${selectedSpecialist.longitude}&z=14&output=embed`
    : null;

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
          <input
            ref={cameraInputRef}
            type="file"
            accept="image/*"
            capture="environment"
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
          <button
            className="button button-secondary"
            onClick={(e) => { e.stopPropagation(); cameraInputRef.current?.click(); }}
            disabled={loading}
            type="button"
          >
            📷 Take Photo
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

            <div className="analysis-panel">
              <h2>Medication Analysis</h2>
              {analysisLoading && <p>Analyzing ingredients and pulling PubMed citations…</p>}
              {analysisError && <div className="error-message">{analysisError}</div>}
              {analysis && (
                <>
                  {analysis.product?.normalized_name && (
                    <p><strong>Product:</strong> {analysis.product.normalized_name} ({analysis.product.product_type})</p>
                  )}
                  {analysis.ingredients?.length > 0 && (
                    <p><strong>Ingredients:</strong> {analysis.ingredients.map((i) => i.name_normalized).join(', ')}</p>
                  )}
                  {analysis.clinical_findings?.map((f) => (
                    <div key={f.ingredient} className="finding-card">
                      <h3>{f.ingredient} <span className={`severity severity-${f.severity}`}>{f.severity}</span></h3>
                      <p>{f.summary}</p>
                      {f.effects?.length > 0 && (
                        <ul>{f.effects.map((e, idx) => <li key={idx}>{e}</li>)}</ul>
                      )}
                      {f.citations?.length > 0 && (
                        <div className="citations">
                          <strong>PubMed citations:</strong>
                          <ul>
                            {f.citations.map((c) => (
                              <li key={c.pmid}>
                                <a href={c.url} target="_blank" rel="noreferrer">PMID {c.pmid}: {c.title}</a>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ))}
                  {analysis.warnings?.length > 0 && (
                    <p className="analysis-warnings"><strong>Warnings:</strong> {analysis.warnings.join('; ')}</p>
                  )}
                </>
              )}
            </div>

            <div className="specialist-section">
              <button
                className="button button-secondary specialist-toggle"
                onClick={() => setSpecialistOpen((current) => !current)}
                type="button"
              >
                {specialistOpen ? 'Hide Specialist Search' : 'Find Specialists In This Area'}
              </button>

              {specialistOpen && (
                <div className="specialist-panel">
                  <p className="specialist-helper">
                    Enter a city and country to search Google Maps for up to 5 nearby specialists.
                  </p>

                  <div className="location-grid">
                    <label className="field-group">
                      <span>City</span>
                      <input
                        type="text"
                        value={locationCity}
                        onChange={(event) => setLocationCity(event.target.value)}
                        placeholder="Boston"
                      />
                    </label>
                    <label className="field-group">
                      <span>Country</span>
                      <input
                        type="text"
                        value={locationCountry}
                        onChange={(event) => setLocationCountry(event.target.value)}
                        placeholder="United States"
                      />
                    </label>
                  </div>

                  <button
                    className="button button-primary specialist-search-button"
                    onClick={handleFindSpecialists}
                    disabled={specialistLoading}
                    type="button"
                  >
                    {specialistLoading ? 'Searching...' : 'Search Nearby Specialists'}
                  </button>

                  {specialistError && <div className="error-message specialist-error">{specialistError}</div>}

                  {specialistResults && (
                    <div className="specialist-results">
                      <p className="specialist-summary">
                        Search area: {specialistResults.user_location?.formatted_address || `${locationCity}, ${locationCountry}`}
                      </p>
                      <p className="specialist-summary">
                        Inferred specialist types: {specialistResults.specialist_types.join(', ')}
                      </p>

                      <div className="specialist-list">
                        {specialistResults.specialists.map((specialist) => (
                          <button
                            key={specialist.place_id || `${specialist.name}-${specialist.address}`}
                            className={`specialist-card ${selectedSpecialist?.place_id === specialist.place_id ? 'active' : ''}`}
                            onClick={() => setSelectedSpecialist(specialist)}
                            type="button"
                          >
                            <strong>{specialist.name}</strong>
                            <span>{specialist.specialist_type}</span>
                            <span>{specialist.address}</span>
                            <span>{specialist.distance_km} km away</span>
                          </button>
                        ))}
                      </div>

                      {selectedSpecialist && (
                        <div className="map-preview">
                          <div className="map-preview-header">
                            <h3>{selectedSpecialist.name}</h3>
                            <a href={selectedSpecialist.map_url} target="_blank" rel="noreferrer">
                              Open in Google Maps
                            </a>
                          </div>
                          <iframe
                            title={`Map for ${selectedSpecialist.name}`}
                            src={embeddedMapUrl}
                            loading="lazy"
                            className="map-frame"
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
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
