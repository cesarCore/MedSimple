import React from 'react';
import ImageUploader from './components/ImageUploader';
import './App.css';

/**
 * Main App Component
 * Root component for the Prescription Bottle Analysis application
 */
function App() {
  return (
    <div className="app">
      <ImageUploader />
    </div>
  );
}

export default App;
