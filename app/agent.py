# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools.load_memory_tool import LoadMemoryTool
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

# Load remote Agent Engine runtime ID from deployment_metadata.json if available
deployment_metadata_path = Path(__file__).parent.parent / "deployment_metadata.json"
agent_engine_resource_name = None
if deployment_metadata_path.exists():
    try:
        with open(deployment_metadata_path) as f:
            metadata = json.load(f)
            agent_engine_resource_name = metadata.get("remote_agent_runtime_id")
    except Exception:
        pass

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name
)

# Vertex AI Memory Bank configuration
PROJECT_ID = "qwiklabs-gcp-02-29bb15443b20"
LOCATION = "us-east1"
MEMORY_BANK_ID = agent_engine_resource_name.split("/")[-1] if agent_engine_resource_name else "7061848724879704064"


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: after each agent turn, send session events to Memory Bank for fact extraction."""
    try:
        await callback_context.add_session_to_memory()
    except Exception:
        pass
    return None


def memory_bank_service_builder():
    """Builds VertexAiMemoryBankService for deployed container runtime."""
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location=LOCATION,
        agent_engine_id=MEMORY_BANK_ID,
    )


MODEL = "gemini-2.5-flash"


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        city: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager

from app.a2ui_utils import a2ui_callback
from app.tools import (
    add_destination,
    calculate_itinerary_budget,
    find_nearby_places,
    generate_destination_image,
    generate_destination_video,
    geocode_address,
    get_currency_exchange_rates,
    search_destinations,
)

schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are a helpful Travel Concierge AI assistant. You actively remember all user travel "
        "destination preferences (favorite cities, landmark choices, budget limits, travel style) "
        "and all weather preferences (preferred climate, heat/cold tolerance, outdoor weather conditions). "
        "You recall these saved facts across conversations and incorporate them into all destination searches, "
        "itinerary planning, and recommendations. Use search_destinations to look up travel options, "
        "add_destination to save recommendations, calculate_itinerary_budget to compute travel expenses, "
        "get_currency_exchange_rates for exchange rates, geocode_address to get coordinates, find_nearby_places "
        "to discover nearby spots, generate_destination_image to create visual postcard images, and "
        "generate_destination_video to generate short video clips of travel destinations. "
        "You can also execute Python code using the code executor when complex calculations or data manipulation are required."
    ),
    workflow_description=(
        "Analyze the request and ALWAYS present lists, destinations, weather info, places, exchange rates, "
        "and budget figures as structured tabular data using Rows and Columns inside an A2UI Card."
    ),
    ui_description=(
        "Keep every surface clean and flat: ONE Card > ONE Column containing multiple Rows for tabular format. "
        "To format tabular data, create a header Row with bold/h2 Text cells, followed by data Rows with body Text cells. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported in adk web), or Buttons, actions, or forms. "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    # Keep in sync with agents-cli-manifest.yaml: agents-cli derives this name
    # from the project `name:` recorded there, and telemetry reports it as
    # gen_ai.agent.name. Renaming the agent only here makes the two disagree,
    # and anything selecting traces by name stops finding this agent's.
    name="simple_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=code_executor,
    tools=[
        get_weather,
        get_current_time,
        search_destinations,
        add_destination,
        calculate_itinerary_budget,
        get_currency_exchange_rates,
        geocode_address,
        find_nearby_places,
        generate_destination_image,
        generate_destination_video,
        PreloadMemoryTool(),
        LoadMemoryTool(),
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
