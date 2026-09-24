# ✈️ Travel Concierge

A conversational AI travel assistant built with the Google Agent Development Kit (ADK). Travel Concierge helps travelers discover destination recommendations, plan day-by-day itineraries, generate visual postcards and video previews, calculate travel budgets, and remember personal travel preferences across sessions.

![Travel Concierge Demo](demo.gif)

---

## 🌟 Implemented Features & Google Cloud Services

The agent's capabilities are fully implemented and backed by the following integrated Google Cloud services and tools:

- **🧠 Vertex AI Memory Bank**: Preserves user travel preferences (favorite cities, landmark choices, climate/weather tolerances, budget constraints) across chat sessions using `VertexAiMemoryBankService`.
- **🗄️ Cloud Firestore**: Queries destination records (`search_destinations`) and saves new travel recommendations (`add_destination`).
- **☁️ Cloud Storage (GCS)**: Stores generated media assets (postcard images and travel video previews) in a public Cloud Storage bucket.
- **🎨 Vertex AI Imagen 3**: Generates custom AI visual postcards (`generate_destination_image`) using `imagen-3.0-generate-002`, saves them as session artifacts, and uploads them to GCS.
- **🎥 Gemini Omni Video Generation**: Generates short video clips of travel destinations (`generate_destination_video`) using `gemini-omni-flash-preview` in the `global` region, saves them as session artifacts, and uploads them to GCS.
- **🎴 Adaptive A2UI Layout**: Renders structured responses (cards, columns, rows, text elements, and images) using Google ADK's `A2uiSchemaManager` and model callbacks.
- **💻 Code Sandbox Executor**: Executes Python code safely in the agent runtime (`AgentEngineSandboxCodeExecutor`) for complex budget calculations (`calculate_itinerary_budget`).
- **📍 Google Places & Geocoding**: Discovers nearby venues and attractions (`find_nearby_places`) and resolves location coordinates (`geocode_address`).
- **💱 Live Currency Exchange**: Converts international currencies using the Frankfurter API (`get_currency_exchange_rates`).
- **🌤️ Weather & Time Lookup**: Fetches weather forecasts (`get_weather`) and current local time (`get_current_time`).

---

## 🏗️ Architecture

- **Backend Framework**: Google Agent Development Kit (`google-adk`), Python 3.14.
- **Frontend Proxy & Web UI**: FastAPI proxy server with an HTML/CSS dialogue interface.
- **Deployment Targets**: Deployed as an Agent Engine resource on Vertex AI Agent Runtime and containerized on Cloud Run.

---

## 🚀 Setup & Running Instructions

### Prerequisites

- Python 3.10+
- Google Cloud SDK (`gcloud`) authenticated to your GCP project.

### 1. Installation

Clone the repository and install dependencies for the agent and frontend:

```bash
# Set up virtual environment and install agent dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install frontend proxy dependencies
cd frontend
pip install -r requirements.txt
cd ..
```

### 2. Environment Variables

Create a `.env` file in the project root:

```env
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-east1
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_MAPS_API_KEY=your-maps-api-key
```

### 3. Run the Frontend Locally

To start the local chat UI and FastAPI proxy server:

```bash
export AGENT_ENGINE_RESOURCE_NAME="projects/YOUR_PROJECT_NUMBER/locations/us-east1/reasoningEngines/YOUR_REASONING_ENGINE_ID"
export AGENT_DIRECTORY="app"
export PORT=8080

cd frontend
python main.py
```

Once started, open `http://localhost:8080` in your web browser to interact with the agent.

---

## 🛠️ Project Structure

```
.
├── README.md                  # Project documentation
├── demo.gif                   # Looping web app interaction demo
├── agents-cli-manifest.yaml   # Agent manifest configuration
├── requirements.txt           # Agent dependencies
├── app/                       # Main ADK agent package
│   ├── agent.py               # Agent definition, Memory Bank, and prompt setup
│   ├── tools.py               # Firestore, GCS, Imagen, Omni, & external API tools
│   └── a2ui_utils.py          # A2UI callback formatting helpers
└── frontend/                  # FastAPI web proxy and chat interface
    ├── main.py                # FastAPI proxy server connecting to Agent Engine
    ├── requirements.txt       # Frontend proxy dependencies
    └── static/
        └── index.html         # Dialogue layout chat UI
```
