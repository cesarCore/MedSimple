# API Integration Guide

This guide outlines how to integrate the PubMed Research API and Google Maps API with the OCR system for the next phases of development.

## Architecture Overview

```
User Input (Image)
     ↓
[Phase 1] Image Upload & OCR Processing ✓ (COMPLETE)
     ↓
[Phase 2] Research Agent (PubMed API) - TO DO
     ↓
[Phase 3] Summary Generation - TO DO
     ↓
[Phase 4] Specialist Finder (Google Maps API) - TO DO
     ↓
User Output (Summary + Specialists)
```

## Phase 2: Research Agent - PubMed Integration

### Overview
The extracted medication text will be passed to the PubMed API to research:
- Side effects
- Active ingredients
- Contraindications
- Drug interactions

### PubMed API Details

**API Endpoint**: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/
**Documentation**: https://www.ncbi.nlm.nih.gov/books/NBK25499/

### Implementation Plan

```python
# backend/agents/research_agent.py (To be created)

import requests
from typing import List, Dict

class PubMedResearchAgent:
    """
    Research agent to query PubMed for medication information
    """
    
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    def __init__(self, api_key: str = None):
        """Initialize research agent"""
        self.api_key = api_key
    
    def search_medication(self, medication_name: str) -> List[str]:
        """
        Search PubMed for medication articles
        
        Args:
            medication_name: Name of medication to research
            
        Returns:
            List of PubMed article IDs
        """
        params = {
            'db': 'pubmed',
            'term': f'{medication_name} AND (side effects OR contraindications)',
            'retmax': 10,  # Get top 10 results
            'tool': 'prescription_ocr',
            'email': 'your_email@example.com'
        }
        
        response = requests.get(
            f'{self.BASE_URL}/esearch.fcgi',
            params=params
        )
        
        # Parse XML response to get article IDs
        # Return list of IDs
    
    def fetch_article_details(self, article_ids: List[str]) -> List[Dict]:
        """
        Fetch detailed information about articles
        
        Args:
            article_ids: List of PubMed article IDs
            
        Returns:
            List of article information dictionaries
        """
        params = {
            'db': 'pubmed',
            'id': ','.join(article_ids),
            'rettype': 'abstract',
            'retmode': 'json',
            'tool': 'prescription_ocr',
            'email': 'your_email@example.com'
        }
        
        response = requests.get(
            f'{self.BASE_URL}/efetch.fcgi',
            params=params
        )
        
        # Parse JSON response
        # Return article details
    
    def extract_side_effects(self, articles: List[Dict]) -> List[str]:
        """
        Extract side effects from article abstracts
        
        Args:
            articles: List of article information
            
        Returns:
            List of identified side effects
        """
        side_effects = []
        
        # Use NLP or keyword matching to extract side effects
        # from article abstracts
        
        return side_effects
    
    def extract_ingredients(self, medication_name: str) -> Dict:
        """
        Extract active ingredients information
        
        Args:
            medication_name: Name of medication
            
        Returns:
            Dictionary with ingredient information
        """
        # Query for pharmacological information
        # Extract active ingredients and their purposes
        pass
```

### Integration Endpoint

```python
# In app.py

@app.route('/api/research', methods=['POST'])
def research_medication():
    """
    Research medication and side effects
    
    Expected JSON:
    {
        "medication_name": "Aspirin",
        "extracted_text": "Full OCR text from bottle"
    }
    """
    try:
        data = request.get_json()
        medication_name = data.get('medication_name')
        extracted_text = data.get('extracted_text')
        
        if not medication_name:
            return jsonify({
                "status": "error",
                "message": "medication_name required"
            }), 400
        
        # Initialize research agent
        research_agent = PubMedResearchAgent()
        
        # Search for medication
        results = research_agent.search_medication(medication_name)
        
        return jsonify({
            "status": "success",
            "medication": medication_name,
            "research_results": results
        }), 200
        
    except Exception as e:
        logger.error(f"Research error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
```

## Phase 3: Summary Generation

### Overview
Use an AI model (Claude, GPT, etc.) to create a concise summary of findings.

### Implementation Plan

```python
# backend/agents/summary_agent.py (To be created)

import anthropic  # or openai

class SummaryAgent:
    """
    Generate concise summaries of research findings
    """
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
    
    def generate_summary(
        self,
        medication_name: str,
        side_effects: List[str],
        ingredients: Dict,
        research_articles: List[Dict]
    ) -> str:
        """
        Generate concise summary using Claude
        
        Args:
            medication_name: Name of medication
            side_effects: List of identified side effects
            ingredients: Dictionary of active ingredients
            research_articles: List of relevant articles
            
        Returns:
            Summary text
        """
        prompt = f"""
        Create a concise, patient-friendly summary of the following medication information.
        
        Medication: {medication_name}
        
        Active Ingredients:
        {self._format_ingredients(ingredients)}
        
        Common Side Effects:
        {', '.join(side_effects[:5])}  # Top 5 side effects
        
        Please provide:
        1. What this medication is used for (2-3 sentences)
        2. Common side effects (3-5 items)
        3. Important precautions (2-3 items)
        
        Keep the summary under 250 words and patient-friendly.
        """
        
        message = self.client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return message.content[0].text
```

### Integration Endpoint

```python
@app.route('/api/generate-summary', methods=['POST'])
def generate_summary():
    """
    Generate summary from research data
    
    Expected JSON:
    {
        "medication_name": "Aspirin",
        "side_effects": [...],
        "ingredients": {...},
        "research_articles": [...]
    }
    """
    try:
        data = request.get_json()
        
        summary_agent = SummaryAgent(
            api_key=os.getenv('CLAUDE_API_KEY')
        )
        
        summary = summary_agent.generate_summary(
            medication_name=data['medication_name'],
            side_effects=data['side_effects'],
            ingredients=data['ingredients'],
            research_articles=data['research_articles']
        )
        
        return jsonify({
            "status": "success",
            "summary": summary
        }), 200
        
    except Exception as e:
        logger.error(f"Summary generation error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
```

## Phase 4: Specialist Finder - Google Maps API

### Overview
Use Google Maps API to find specialists based on medication type and user location.

### Setup Instructions

1. **Create Google Cloud Project**:
   - Go to https://console.cloud.google.com/
   - Create new project
   - Enable Maps JavaScript API, Places API, and Distance Matrix API

2. **Get API Key**:
   - Go to Credentials
   - Create API key
   - Add to backend .env: `GOOGLE_MAPS_API_KEY=your_key`

### Implementation Plan

```python
# backend/agents/specialist_finder.py (To be created)

import googlemaps
from typing import List, Dict

class SpecialistFinder:
    """
    Find local specialists based on medication
    """
    
    def __init__(self, api_key: str):
        self.gmaps = googlemaps.Client(key=api_key)
    
    def get_specialist_types(self, medication_name: str) -> List[str]:
        """
        Determine specialist types based on medication
        Maps medication to relevant specialist types
        """
        medication_specialist_map = {
            'heart': ['cardiologist', 'pharmacist'],
            'blood pressure': ['cardiologist', 'pharmacist'],
            'arthritis': ['rheumatologist', 'orthopedic surgeon'],
            'diabetes': ['endocrinologist', 'pharmacist'],
            'asthma': ['pulmonologist', 'allergist'],
            # ... more mappings
        }
        
        specialists = []
        med_lower = medication_name.lower()
        
        for keyword, specialist_list in medication_specialist_map.items():
            if keyword in med_lower:
                specialists.extend(specialist_list)
        
        return specialists or ['pharmacist', 'general practitioner']
    
    def find_specialists(
        self,
        medication_name: str,
        user_location: Dict[str, float],  # {'lat': ..., 'lng': ...}
        radius: int = 5000  # 5km radius
    ) -> List[Dict]:
        """
        Find specialists near user
        
        Args:
            medication_name: Name of medication
            user_location: User's latitude and longitude
            radius: Search radius in meters
            
        Returns:
            List of specialist locations
        """
        specialists = self.get_specialist_types(medication_name)
        results = []
        
        for specialist_type in specialists:
            places = self.gmaps.places_nearby(
                location=(
                    user_location['lat'],
                    user_location['lng']
                ),
                type=specialist_type,
                radius=radius
            )
            
            for place in places['results']:
                results.append({
                    'name': place['name'],
                    'type': specialist_type,
                    'address': place['vicinity'],
                    'lat': place['geometry']['location']['lat'],
                    'lng': place['geometry']['location']['lng'],
                    'rating': place.get('rating', 'N/A'),
                    'distance': self._calculate_distance(
                        user_location,
                        place['geometry']['location']
                    )
                })
        
        # Sort by distance
        results.sort(key=lambda x: x['distance'])
        
        return results[:10]  # Return top 10
```

### Integration Endpoint

```python
@app.route('/api/find-specialists', methods=['POST'])
def find_specialists():
    """
    Find specialists for medication
    
    Expected JSON:
    {
        "medication_name": "Aspirin",
        "user_location": {
            "lat": 37.7749,
            "lng": -122.4194
        },
        "radius": 5000
    }
    """
    try:
        data = request.get_json()
        
        finder = SpecialistFinder(
            api_key=os.getenv('GOOGLE_MAPS_API_KEY')
        )
        
        specialists = finder.find_specialists(
            medication_name=data['medication_name'],
            user_location=data['user_location'],
            radius=data.get('radius', 5000)
        )
        
        return jsonify({
            "status": "success",
            "specialists": specialists
        }), 200
        
    except Exception as e:
        logger.error(f"Specialist finder error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
```

## Complete Workflow Example

### Frontend Integration

```javascript
// frontend/src/services/prescriptionService.js

export class PrescriptionService {
  constructor(apiUrl = process.env.REACT_APP_API_URL) {
    this.apiUrl = apiUrl;
  }

  // Step 1: Upload and extract text
  async uploadImage(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${this.apiUrl}/api/upload`, {
      method: 'POST',
      body: formData
    });
    
    return response.json();
  }

  // Step 2: Research medication
  async researchMedication(medicationName, extractedText) {
    const response = await fetch(`${this.apiUrl}/api/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        medication_name: medicationName,
        extracted_text: extractedText
      })
    });
    
    return response.json();
  }

  // Step 3: Generate summary
  async generateSummary(researchData) {
    const response = await fetch(`${this.apiUrl}/api/generate-summary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(researchData)
    });
    
    return response.json();
  }

  // Step 4: Find specialists
  async findSpecialists(medicationName, userLocation) {
    const response = await fetch(`${this.apiUrl}/api/find-specialists`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        medication_name: medicationName,
        user_location: userLocation
      })
    });
    
    return response.json();
  }

  // Complete workflow
  async processCompletely(file, userLocation) {
    try {
      // 1. Extract text
      const ocrResult = await this.uploadImage(file);
      const extractedText = ocrResult.ocr_data.full_text;
      
      // 2. Research
      const researchResult = await this.researchMedication(
        /* extract medication name */,
        extractedText
      );
      
      // 3. Summarize
      const summaryResult = await this.generateSummary(
        researchResult.research_results
      );
      
      // 4. Find specialists
      const specialistsResult = await this.findSpecialists(
        /* medication name */,
        userLocation
      );
      
      return {
        extracted_text: extractedText,
        research: researchResult,
        summary: summaryResult,
        specialists: specialistsResult
      };
      
    } catch (error) {
      console.error('Complete processing error:', error);
      throw error;
    }
  }
}
```

## Environment Variables Required

```ini
# .env files for Phase 2-4

# Phase 2: Research
PUBMED_API_KEY=optional_but_recommended

# Phase 3: Summary Generation
CLAUDE_API_KEY=your_anthropic_key
# OR
OPENAI_API_KEY=your_openai_key

# Phase 4: Maps
GOOGLE_MAPS_API_KEY=your_google_maps_key
```

## Testing

### Test Research Agent
```bash
curl -X POST http://localhost:5000/api/research \
  -H "Content-Type: application/json" \
  -d '{
    "medication_name": "Aspirin",
    "extracted_text": "Aspirin 500mg..."
  }'
```

### Test Specialist Finder
```bash
curl -X POST http://localhost:5000/api/find-specialists \
  -H "Content-Type: application/json" \
  -d '{
    "medication_name": "Aspirin",
    "user_location": {
      "lat": 37.7749,
      "lng": -122.4194
    }
  }'
```

## Next Steps

1. **Implement Research Agent** (Phase 2)
2. **Implement Summary Generator** (Phase 3)
3. **Implement Specialist Finder** (Phase 4)
4. **Update Frontend** with full workflow UI
5. **Add Error Handling** for all phases
6. **Implement Rate Limiting** for API calls
7. **Add Caching** to reduce API calls
8. **Deploy** with all components

---

**Document Version**: 1.0
**Last Updated**: April 2024
**Status**: Planning Complete, Implementation Pending
