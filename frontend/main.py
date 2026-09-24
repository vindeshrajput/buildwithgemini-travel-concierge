"""Minimal FastAPI proxy for a deployed A2A agent (Agent Runtime, agents-cli 1.1.0+).

The browser talks ONLY to this proxy (same origin, no CORS, no GCP creds in the
browser). The proxy authenticates with Application Default Credentials and
forwards chat to the deployed agent over the A2A protocol, returning replies as
structured parts the chat UI knows how to show:

  * {"kind": "text", "text": ...}  -> a normal chat bubble
  * {"kind": "a2ui", "data": ...}  -> one A2UI message (beginRendering /
    surfaceUpdate); static/index.html renders these as a card.

Why A2A: agents-cli 1.1.0 (GA) deploys ADK agents to Agent Runtime as A2A agents
and no longer registers the reasoning-engine operation schema the old
`agent_engines.get(...).stream_query()` path relied on (operation_schemas() comes
back empty). The container serves the A2A protocol over the Agent Engine HTTP
passthrough, so this proxy fetches the agent's card and sends messages with the
a2a-sdk client (the same path `agents-cli run --mode a2a` uses). This works for
both A2A and plain ADK 1.1.0 deployments (the container serves A2A either way).

Run:
  pip install -r requirements.txt
  export AGENT_ENGINE_RESOURCE_NAME="projects/.../locations/.../reasoningEngines/..."
  export AGENT_DIRECTORY="app"   # your agent's app directory (agents-cli-manifest.yaml)
  python main.py                 # -> http://localhost:8080
"""

import os
import uuid

import google.auth
import google.auth.transport.requests
import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.types import (
    AgentCard,
    Message,
    Part,
    Role,
    SendMessageRequest,
)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

RESOURCE = os.environ["AGENT_ENGINE_RESOURCE_NAME"]
# The agent's app directory (matches agent_directory in agents-cli-manifest.yaml).
AGENT_DIRECTORY = os.environ.get("AGENT_DIRECTORY", "app")
# Location is embedded in the resource name: projects/<p>/locations/<loc>/reasoningEngines/<id>.
LOCATION = RESOURCE.split("/locations/")[1].split("/")[0]

# A2A endpoint for an Agent Runtime deployment, via the Agent Engine HTTP
# passthrough. The card lives at the well-known path under this base.
A2A_BASE = (
    f"https://{LOCATION}-aiplatform.googleapis.com/reasoningEngines/v1/"
    f"{RESOURCE}/api/a2a/{AGENT_DIRECTORY}"
)
A2A_CARD_URL = f"{A2A_BASE}/.well-known/agent-card.json"

# The agent tags its A2UI data parts with this mime type.
_A2UI_MIME = "application/json+a2ui"

# One set of ADC credentials, refreshed per request (access tokens expire ~1h).
_creds, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)


def _auth_headers() -> dict[str, str]:
    _creds.refresh(google.auth.transport.requests.Request())
    return {
        "Authorization": f"Bearer {_creds.token}",
        "Content-Type": "application/json",
    }


app = FastAPI()


@app.exception_handler(Exception)
async def _json_errors(request: Request, exc: Exception):
    # Always return JSON so the browser never receives a plain-text 500 page
    # (which shows up in the chat as "Unexpected token 'I', "Internal S"... is
    # not valid JSON"). Any server-side failure now surfaces as a readable
    # message in the chat bubble instead.
    return JSONResponse(
        status_code=200,
        content={
            "parts": [{"kind": "text", "text": f"Error: {type(exc).__name__}: {exc}"}]
        },
    )


# Reuse ONE A2A context per user so the agent remembers the conversation.
_contexts: dict[str, str] = {}
# Cache the agent card after the first fetch.
_card: AgentCard | None = None


async def _get_card(client: httpx.AsyncClient) -> AgentCard:
    global _card
    if _card is None:
        resp = await client.get(A2A_CARD_URL)
        resp.raise_for_status()
        card_data = resp.json()
        if isinstance(card_data, dict):
            if hasattr(AgentCard, "model_validate"):
                card = AgentCard.model_validate(card_data)
            elif hasattr(AgentCard, "parse_obj"):
                card = AgentCard.parse_obj(card_data)
            else:
                from google.protobuf.json_format import ParseDict
                card = ParseDict(card_data, AgentCard(), ignore_unknown_fields=True)
        else:
            card = card_data

        interfaces = getattr(card, "supported_interfaces", None) or getattr(card, "supportedInterfaces", None) or []
        for interface in interfaces:
            if hasattr(interface, "url"):
                interface.url = A2A_BASE
            elif isinstance(interface, dict):
                interface["url"] = A2A_BASE

        _card = card
    return _card


def _extract_parts(parts: list) -> list[dict]:
    out: list[dict] = []
    from google.protobuf.json_format import MessageToDict
    for p in parts:
        root = getattr(p, "root", p)
        if hasattr(root, "HasField") and root.HasField("text"):
            if root.text:
                out.append({"kind": "text", "text": root.text})
                continue
        elif getattr(root, "text", None):
            out.append({"kind": "text", "text": root.text})
            continue

        if hasattr(root, "HasField") and root.HasField("data"):
            data_dict = MessageToDict(root.data)
            if data_dict:
                out.append({"kind": "a2ui", "data": data_dict})
                continue
        elif getattr(root, "data", None):
            d = root.data
            if hasattr(d, "DESCRIPTOR"):
                d = MessageToDict(d)
            if d:
                out.append({"kind": "a2ui", "data": d})
                continue

        file_obj = getattr(root, "file", None)
        if file_obj:
            uri = getattr(file_obj, "uri", None)
            if uri:
                out.append({"kind": "text", "text": uri})
    return out


@app.post("/chat")
async def chat(req: Request):
    import logging
    logging.basicConfig(level=logging.INFO)
    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "web-user"
    parts: list[dict] = []

    async with httpx.AsyncClient(headers=_auth_headers(), timeout=120) as client:
        card = await _get_card(client)
        factory = ClientFactory(
            ClientConfig(
                httpx_client=client,
            )
        )
        a2a_client = factory.create(card)

        user_role = getattr(Role, "ROLE_USER", getattr(Role, "user", "user"))
        msg = Message(
            message_id=str(uuid.uuid4()),
            role=user_role,
            parts=[Part(text=message)],
            context_id=_contexts.get(user_id),
        )
        last_task = None
        async for event in a2a_client.send_message(SendMessageRequest(message=msg)):
            payload = event.WhichOneof("payload") if hasattr(event, "WhichOneof") else None
            if payload == "task" or (hasattr(event, "HasField") and event.HasField("task")):
                last_task = event.task
                if event.task.context_id:
                    _contexts[user_id] = event.task.context_id
            if payload == "message" or (hasattr(event, "HasField") and event.HasField("message")):
                parts.extend(_extract_parts(event.message.parts))
            if payload == "artifact_update" or (hasattr(event, "HasField") and event.HasField("artifact_update")):
                parts.extend(_extract_parts(event.artifact_update.artifact.parts))
            if isinstance(event, tuple):
                task, update = event
                if task is not None:
                    last_task = task
                    if getattr(task, "context_id", None):
                        _contexts[user_id] = task.context_id
                if getattr(update, "artifact", None):
                    parts.extend(_extract_parts(update.artifact.parts))

        # Fallback: if streaming yielded no parts, pull parts from the final task's artifacts.
        if not parts and last_task is not None:
            for artifact in getattr(last_task, "artifacts", None) or []:
                parts.extend(_extract_parts(artifact.parts))

    if not parts:
        # The turn produced no text or UI (e.g. the agent only ran tools, or a
        # tool stalled). Be honest rather than silent.
        parts = [{"kind": "text", "text": "(The agent didn't return a reply.)"}]
    return JSONResponse({"parts": parts})


STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
