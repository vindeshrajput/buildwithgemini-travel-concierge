# Copyright 2026 Google LLC
# Seed script for Travel Concierge Firestore collection

import subprocess
import sys
import time
import google.auth
from google.cloud import firestore
from google.oauth2.credentials import Credentials

# CRITICAL REQUIREMENT: Hardcode the GCP Project ID as a string constant.
# Do NOT read from google.auth.default() or GOOGLE_CLOUD_PROJECT env var.
FIRESTORE_PROJECT = "qwiklabs-gcp-02-29bb15443b20"

SEED_DESTINATIONS = [
    {
        "id": "eiffel-tower",
        "name": "Eiffel Tower",
        "city": "Paris",
        "category": "Landmark",
        "description": "Iconic 330-meter-tall wrought-iron lattice tower offering panoramic city views of Paris.",
        "avg_cost_usd": 35.0,
        "tags": ["iconic", "views", "romantic", "must-see"],
        "best_time_to_visit": "Sunset / Evening",
    },
    {
        "id": "louvre-museum",
        "name": "Louvre Museum",
        "city": "Paris",
        "category": "Museum",
        "description": "The world's largest art museum, home to the Mona Lisa and thousands of historic masterpieces.",
        "avg_cost_usd": 22.0,
        "tags": ["art", "history", "culture", "museum"],
        "best_time_to_visit": "Morning",
    },
    {
        "id": "fushimi-inari-shrine",
        "name": "Fushimi Inari Shrine",
        "city": "Kyoto",
        "category": "Shrine",
        "description": "Famous Shinto shrine in southern Kyoto known for thousands of vibrant vermilion torii gates.",
        "avg_cost_usd": 0.0,
        "tags": ["culture", "scenic", "nature", "historic"],
        "best_time_to_visit": "Early Morning",
    },
    {
        "id": "arashiyama-bamboo-grove",
        "name": "Arashiyama Bamboo Grove",
        "city": "Kyoto",
        "category": "Nature",
        "description": "Mesmerizing natural bamboo forest path near Kyoto's Tenryu-ji temple.",
        "avg_cost_usd": 0.0,
        "tags": ["nature", "photography", "peaceful"],
        "best_time_to_visit": "Early Morning",
    },
    {
        "id": "central-park",
        "name": "Central Park",
        "city": "New York",
        "category": "Park",
        "description": "Sprawling 843-acre urban park in Manhattan featuring lakes, walking paths, and historic landmarks.",
        "avg_cost_usd": 0.0,
        "tags": ["nature", "outdoors", "family-friendly", "relaxing"],
        "best_time_to_visit": "Afternoon",
    },
    {
        "id": "broadway-theater-district",
        "name": "Broadway Theater District",
        "city": "New York",
        "category": "Entertainment",
        "description": "World-famous center of American commercial theater in Midtown Manhattan.",
        "avg_cost_usd": 130.0,
        "tags": ["theater", "shows", "nightlife", "entertainment"],
        "best_time_to_visit": "Evening",
    },
]


def get_fresh_db_client():
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
    else:
        creds, _ = google.auth.default()
    return firestore.Client(project=FIRESTORE_PROJECT, credentials=creds)


def seed_firestore():
    print(f"Connecting to Firestore using project ID: '{FIRESTORE_PROJECT}'...")
    count = 0
    for dest in SEED_DESTINATIONS:
        doc_id = dest["id"]
        # Retry loop for eventual IAM / token consistency
        for attempt in range(3):
            try:
                db = get_fresh_db_client()
                doc_ref = db.collection("destinations").document(doc_id)
                doc_ref.set(dest)
                print(f"  ✓ Seeded destination: {dest['name']} ({dest['city']}) -> id: {doc_id}")
                count += 1
                break
            except Exception as err:
                if attempt == 2:
                    raise err
                time.sleep(1)

    print(f"Successfully seeded {count} items into 'destinations' collection in Firestore ({FIRESTORE_PROJECT}).")


if __name__ == "__main__":
    try:
        seed_firestore()
    except Exception as e:
        print(f"Error seeding Firestore: {e}", file=sys.stderr)
        sys.exit(1)
