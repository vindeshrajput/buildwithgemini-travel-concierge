# Copyright 2026 Google LLC
# Firestore tools for Travel Concierge agent

import json
import os
import subprocess
import urllib.parse
import urllib.request
import uuid
from typing import Optional
from dotenv import load_dotenv
from google import genai
from google.adk.tools import ToolContext
import google.auth
from google.cloud import firestore, storage
from google.genai import types
from google.oauth2.credentials import Credentials

# Automatically load environment variables from local .env
load_dotenv()

# CRITICAL REQUIREMENT: Hardcode project ID and bucket name as string constants.
# On Agent Platform, google.auth.default() and GOOGLE_CLOUD_PROJECT env var
# return project NUMBER which breaks Firestore client.
FIRESTORE_PROJECT = "qwiklabs-gcp-02-29bb15443b20"
GCS_BUCKET_NAME = "travel-concierge-media-29bb15443b20"


def _get_firestore_client() -> firestore.Client:
    """Helper to initialize Firestore client with hardcoded project ID."""
    token = ""
    try:
        token = subprocess.check_output(
            ["gcloud", "auth", "application-default", "print-access-token"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        pass

    if token:
        creds = Credentials(token)
        return firestore.Client(project=FIRESTORE_PROJECT, credentials=creds)
    
    return firestore.Client(project=FIRESTORE_PROJECT)


def search_destinations(
    city: Optional[str] = None,
    category: Optional[str] = None,
    max_cost_usd: Optional[float] = None,
) -> str:
    """Searches the Firestore database for travel destinations matching criteria.

    Args:
        city: Optional city name to filter by (e.g. 'Paris', 'Kyoto', 'New York').
        category: Optional category filter (e.g. 'Landmark', 'Museum', 'Nature', 'Park', 'Entertainment').
        max_cost_usd: Optional maximum average cost in USD.

    Returns:
        JSON string list of matching destination items.
    """
    db = _get_firestore_client()
    collection_ref = db.collection("destinations")
    docs = collection_ref.stream()

    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id

        if city and city.strip().lower() not in data.get("city", "").lower():
            continue
        if category:
            cat_lower = category.strip().lower()
            text_to_search = f"{data.get('category', '')} {data.get('name', '')} {data.get('description', '')} {' '.join(data.get('tags', []))}".lower()
            if not any(word in text_to_search for word in cat_lower.split()):
                continue
        if max_cost_usd is not None and max_cost_usd > 0:
            if data.get("avg_cost_usd", 0.0) > max_cost_usd:
                continue

        results.append(data)

    if not results:
        return json.dumps({"status": "empty", "message": "No matching destinations found.", "destinations": []})

    return json.dumps({"status": "success", "count": len(results), "destinations": results}, indent=2)


def add_destination(
    name: str,
    city: str,
    category: str,
    description: str,
    avg_cost_usd: float = 0.0,
    best_time_to_visit: str = "Anytime",
) -> str:
    """Adds a new destination entry into the Firestore database.

    Args:
        name: Name of the landmark or attraction (e.g. 'Arc de Triomphe').
        city: City location (e.g. 'Paris').
        category: Category (e.g. 'Landmark', 'Museum', 'Dining').
        description: A helpful description of the attraction.
        avg_cost_usd: Average estimated cost per person in USD.
        best_time_to_visit: Recommended time of day to visit.

    Returns:
        A confirmation message with the newly created document ID.
    """
    db = _get_firestore_client()
    doc_id = name.strip().lower().replace(" ", "-")
    doc_ref = db.collection("destinations").document(doc_id)

    new_dest = {
        "id": doc_id,
        "name": name.strip(),
        "city": city.strip(),
        "category": category.strip(),
        "description": description.strip(),
        "avg_cost_usd": float(avg_cost_usd),
        "best_time_to_visit": best_time_to_visit.strip(),
    }

    doc_ref.set(new_dest)
    return f"Successfully added destination '{name}' (ID: {doc_id}) in {city} to Firestore."


def calculate_itinerary_budget(
    destination_costs_usd: list[float],
    days: int = 3,
    daily_expense_usd: float = 50.0,
    target_budget_usd: float = 500.0,
) -> str:
    """Calculates total estimated travel expenses and compares with target budget.

    Args:
        destination_costs_usd: List of ticket/entrance fees in USD for planned destinations.
        days: Duration of the trip in days.
        daily_expense_usd: Estimated daily food, transit, and misc expense per day in USD.
        target_budget_usd: Total target budget limit in USD.

    Returns:
        JSON string breakdown of total costs, daily breakdown, and budget surplus or deficit.
    """
    total_tickets = sum(destination_costs_usd) if destination_costs_usd else 0.0
    total_daily = days * daily_expense_usd
    total_cost = total_tickets + total_daily
    remaining_budget = target_budget_usd - total_cost

    return json.dumps(
        {
            "trip_duration_days": days,
            "total_ticket_costs_usd": total_tickets,
            "total_daily_expenses_usd": total_daily,
            "total_estimated_cost_usd": total_cost,
            "target_budget_usd": target_budget_usd,
            "remaining_budget_usd": remaining_budget,
            "within_budget": remaining_budget >= 0,
        },
        indent=2,
    )


def get_currency_exchange_rates(
    base_currency: str = "USD",
    target_currencies: Optional[list[str]] = None,
) -> str:
    """Fetches real-time foreign currency exchange rates for travel budgeting.

    Args:
        base_currency: Source currency code (e.g. 'USD', 'EUR', 'GBP'). Default is 'USD'.
        target_currencies: Optional list of target currency codes to filter (e.g. ['EUR', 'JPY', 'GBP']).

    Returns:
        JSON string containing live exchange rates and timestamp.
    """
    api_key = os.environ.get("EXCHANGE_RATE_API_KEY", "")
    base = base_currency.strip().upper()
    url = f"https://open.er-api.com/v6/latest/{base}"
    if api_key:
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/{base}"

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "TravelConciergeAgent/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        rates = data.get("rates", {})
        if target_currencies:
            targets = [t.strip().upper() for t in target_currencies]
            rates = {k: v for k, v in rates.items() if k in targets}

        return json.dumps(
            {
                "status": "success",
                "base_currency": base,
                "last_updated": data.get("time_last_update_utc", ""),
                "rates": rates,
            },
            indent=2,
        )
    except Exception as err:
        return json.dumps({"status": "error", "message": str(err)})


def geocode_address(address: str) -> str:
    """Uses Google Maps Geocoding API to convert an address or landmark into coordinates.

    Args:
        address: The location, address, or landmark to geocode (e.g., 'Eiffel Tower, Paris').

    Returns:
        JSON string containing latitude, longitude, and formatted address.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return json.dumps({"status": "error", "message": "GOOGLE_MAPS_API_KEY environment variable not set."})

    encoded_address = urllib.parse.quote(address)
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        if data.get("status") != "OK" or not data.get("results"):
            return json.dumps({"status": "error", "message": f"Geocoding failed: {data.get('status')}"})

        first = data["results"][0]
        location = first["geometry"]["location"]
        formatted_address = first["formatted_address"]

        return json.dumps(
            {
                "status": "success",
                "name": address,
                "address": formatted_address,
                "location": {
                    "latitude": location["lat"],
                    "longitude": location["lng"],
                },
            },
            indent=2,
        )
    except Exception as err:
        return json.dumps({"status": "error", "message": str(err)})


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "restaurant",
    radius_meters: float = 1000.0,
) -> str:
    """Uses Google Places API (New) to search for nearby places around coordinates.

    Args:
        latitude: Latitude of center location.
        longitude: Longitude of center location.
        place_type: Type of place to search for (e.g. 'restaurant', 'cafe', 'tourist_attraction', 'museum').
        radius_meters: Radius in meters around the center point (default 1000m).

    Returns:
        JSON string list of nearby places with name, formatted address, and location.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return json.dumps({"status": "error", "message": "GOOGLE_MAPS_API_KEY environment variable not set."})

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.primaryType",
    }
    payload = {
        "includedTypes": [place_type.strip().lower()],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": float(radius_meters),
            }
        },
    }

    try:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        places = []
        for p in data.get("places", []):
            places.append(
                {
                    "name": p.get("displayName", {}).get("text", "Unknown"),
                    "address": p.get("formattedAddress", ""),
                    "location": p.get("location", {}),
                    "primary_type": p.get("primaryType", place_type),
                }
            )

        return json.dumps({"status": "success", "count": len(places), "places": places}, indent=2)
    except Exception as err:
        return json.dumps({"status": "error", "message": str(err)})


def generate_destination_image(
    prompt: str,
    tool_context: ToolContext,
) -> str:
    """Generates an image for a travel destination, saves it as a session artifact, and uploads to Cloud Storage.

    Args:
        prompt: Detailed description of the travel destination, landmark, or postcard scene to generate.
        tool_context: Provided automatically by the agent framework to save artifacts.

    Returns:
        JSON string containing the public HTTPS URL of the image in Cloud Storage.
    """
    try:
        genai_client = genai.Client(
            vertexai=True,
            project=FIRESTORE_PROJECT,
            location="global",
        )

        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=f"High quality travel photo / postcard: {prompt}",
        )

        image_bytes = None
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                image_bytes = part.inline_data.data
                break

        if not image_bytes:
            return json.dumps({"status": "error", "message": "No image data was generated by the model."})

        filename = f"postcard_{uuid.uuid4().hex[:8]}.jpg"

        # 1. Save artifact to Playground session
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload image bytes to public GCS bucket
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type="image/jpeg")

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        return json.dumps(
            {
                "status": "success",
                "message": "Image generated successfully, saved as session artifact, and uploaded to GCS.",
                "image_url": public_url,
            },
            indent=2,
        )
    except Exception as err:
        return json.dumps({"status": "error", "message": str(err)})


def generate_destination_video(
    prompt: str,
    tool_context: ToolContext,
) -> str:
    """Generates a short video clip for a travel destination using Google's Omni model (gemini-omni-flash-preview), saves it as a session artifact, and uploads to Cloud Storage.

    Args:
        prompt: Detailed description of the travel destination video or landmark scene to generate.
        tool_context: Provided automatically by the agent framework to save artifacts.

    Returns:
        JSON string containing the public HTTPS URL of the video in Cloud Storage.
    """
    try:
        genai_client = genai.Client(
            vertexai=True,
            project=FIRESTORE_PROJECT,
            location="global",
        )

        resp = genai_client.interactions.create(
            model="gemini-omni-flash-preview",
            input=f"Generate a short video clip of travel destination: {prompt}",
            response_modalities=["text", "video"],
        )

        video_bytes = None
        if resp and hasattr(resp, "steps") and resp.steps:
            for step in resp.steps:
                if hasattr(step, "content") and step.content:
                    for item in step.content:
                        if hasattr(item, "data") and item.data:
                            video_bytes = item.data
                            break
                        elif hasattr(item, "inline_data") and item.inline_data and item.inline_data.data:
                            video_bytes = item.inline_data.data
                            break

        if not video_bytes:
            return json.dumps({"status": "error", "message": "No video data was generated by the model."})

        filename = f"video_{uuid.uuid4().hex[:8]}.mp4"

        # 1. Save artifact to Playground session
        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")
        tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload video bytes to public GCS bucket
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type="video/mp4")

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        return json.dumps(
            {
                "status": "success",
                "message": "Video generated successfully, saved as session artifact, and uploaded to GCS.",
                "video_url": public_url,
            },
            indent=2,
        )
    except Exception as err:
        return json.dumps({"status": "error", "message": str(err)})





