"""Specialist / pharmacy finder backed by Google Places Nearby Search."""

import logging
import math

import requests

logger = logging.getLogger(__name__)


SPECIALIST_KEYWORDS = {
    "heart": ["cardiologist", "pharmacy"],
    "blood pressure": ["cardiologist", "pharmacy"],
    "hypertension": ["cardiologist", "pharmacy"],
    "diabetes": ["endocrinologist", "pharmacy"],
    "insulin": ["endocrinologist", "pharmacy"],
    "asthma": ["pulmonologist", "allergist", "pharmacy"],
    "allergy": ["allergist", "pharmacy"],
    "thyroid": ["endocrinologist", "pharmacy"],
    "arthritis": ["rheumatologist", "pharmacy"],
}

DEFAULT_SPECIALISTS = ["pharmacy", "general practitioner"]
PLACES_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def infer_specialist_types(medication_text):
    """Map a medication label / free text to a sorted list of specialist types."""
    text = (medication_text or "").lower()
    inferred = set()

    for keyword, specialists in SPECIALIST_KEYWORDS.items():
        if keyword in text:
            inferred.update(specialists)

    if not inferred:
        inferred.update(DEFAULT_SPECIALISTS)

    return sorted(inferred)


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two lat/lng pairs, in kilometers."""
    earth_radius_km = 6371.0

    lat1r = math.radians(lat1)
    lon1r = math.radians(lon1)
    lat2r = math.radians(lat2)
    lon2r = math.radians(lon2)

    dlat = lat2r - lat1r
    dlon = lon2r - lon1r

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1r) * math.cos(lat2r) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_km * c


def geocode_location(city, country, api_key, http_get=None):
    """Resolve a city/country pair to coordinates using Google Geocoding."""
    http_get = http_get or requests.get
    address = ", ".join([part.strip() for part in [city, country] if part and part.strip()])
    if not address:
        raise ValueError("city and country are required")

    response = http_get(
        GEOCODE_URL,
        params={"address": address, "key": api_key},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    status = payload.get("status")
    if status != "OK" or not payload.get("results"):
        raise ValueError(payload.get("error_message") or f"Google Geocoding error: {status}")

    result = payload["results"][0]
    location = result.get("geometry", {}).get("location", {})
    lat = location.get("lat")
    lng = location.get("lng")
    if lat is None or lng is None:
        raise ValueError("Geocoding result did not include coordinates")

    return {
        "formatted_address": result.get("formatted_address", address),
        "lat": float(lat),
        "lng": float(lng),
    }


def google_places_search(lat, lng, radius, specialist_type, api_key, http_get=None):
    """Query Google Places nearby search and return up to 5 normalized results.

    `http_get` is injectable for tests; defaults to `requests.get`.
    """
    http_get = http_get or requests.get

    if specialist_type == "pharmacy":
        place_type = "pharmacy"
        keyword = "pharmacy"
    else:
        place_type = "doctor"
        keyword = specialist_type

    params = {
        "location": f"{lat},{lng}",
        "radius": radius,
        "type": place_type,
        "keyword": keyword,
        "key": api_key,
    }

    response = http_get(PLACES_URL, params=params, timeout=10)
    response.raise_for_status()
    payload = response.json()

    status = payload.get("status")
    if status not in {"OK", "ZERO_RESULTS"}:
        raise ValueError(payload.get("error_message") or f"Google Places error: {status}")

    results = []
    for place in payload.get("results", [])[:5]:
        location = place.get("geometry", {}).get("location", {})
        place_lat = location.get("lat")
        place_lng = location.get("lng")

        if place_lat is None or place_lng is None:
            continue

        distance_km = haversine_km(float(lat), float(lng), float(place_lat), float(place_lng))
        map_url = (
            f"https://www.google.com/maps/search/?api=1&query={place_lat},{place_lng}"
            f"&query_place_id={place.get('place_id', '')}"
        )

        results.append({
            "place_id": place.get("place_id"),
            "name": place.get("name", "Unknown"),
            "address": place.get("vicinity") or place.get("formatted_address", "Address unavailable"),
            "specialist_type": specialist_type,
            "rating": place.get("rating"),
            "distance_km": round(distance_km, 2),
            "latitude": float(place_lat),
            "longitude": float(place_lng),
            "map_url": map_url,
        })

    return results


def find_specialists(medication_name, lat, lng, radius, api_key, search_fn=None):
    """Compose specialist inference + place search into a ranked result set.

    Returns `(specialist_types, specialists, warnings)`. `search_fn` is injectable
    for tests and defaults to `google_places_search`.
    """
    search_fn = search_fn or google_places_search
    specialist_types = infer_specialist_types(medication_name)
    by_place = {}
    warnings = []

    for specialist_type in specialist_types:
        try:
            results = search_fn(lat, lng, radius, specialist_type, api_key)
        except Exception as search_error:  # pylint: disable=broad-except
            logger.error("Specialist search failed for %s: %s", specialist_type, search_error)
            warnings.append(f"{specialist_type}: search failed")
            continue

        for item in results:
            dedupe_key = item.get("place_id") or f"{item['name']}|{item['address']}"
            existing = by_place.get(dedupe_key)
            if existing is None or item["distance_km"] < existing["distance_km"]:
                by_place[dedupe_key] = item

    specialists = sorted(
        by_place.values(),
        key=lambda x: (x.get("distance_km", 9999), -(x.get("rating") or 0)),
    )[:5]

    return specialist_types, specialists, warnings
