"""WA/D - Wisdom Assistor/Distributor: Main FastAPI application."""

from __future__ import annotations

import asyncio
import io
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

from app.action.controller import ActionController
from app.agents.manager import AgentManager
from app.config import settings
from app.decision.engine import DecisionEngine
from app.memory.store import MemoryStore
from app.safety.monitor import SafetyMonitor
from app.screen.parser import ScreenParser

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Global state
# ──────────────────────────────────────────────
agent_manager: AgentManager
decision_engine: DecisionEngine
screen_parser: ScreenParser
action_controller: ActionController
memory_store: MemoryStore
safety_monitor: SafetyMonitor

# WebSocket connections for live updates
ws_connections: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown."""
    global agent_manager, decision_engine, screen_parser
    global action_controller, memory_store, safety_monitor

    agent_manager = AgentManager()
    decision_engine = DecisionEngine()
    screen_parser = ScreenParser(ocr_enabled=settings.ocr_enabled)
    action_controller = ActionController()
    memory_store = MemoryStore()
    safety_monitor = SafetyMonitor()

    # Wire safety monitor to action controller
    safety_monitor.register_stop_callback(action_controller.emergency_stop)

    # Initialize memory store
    await memory_store.initialize()

    logger.info("WA/D started on http://%s:%s", settings.host, settings.port)
    yield
    logger.info("WA/D shutting down")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ──────────────────────────────────────────────
# Request / response models
# ──────────────────────────────────────────────

class QueryRequest(BaseModel):
    instruction: str
    include_screen: bool = False
    monitor_index: int = 0
    agent_keys: Optional[list[str]] = None
    use_memory_context: bool = True


class ActionRequest(BaseModel):
    action_type: str  # click, double_click, right_click, move, type, hotkey, scroll, drag
    x: Optional[int] = None
    y: Optional[int] = None
    text: Optional[str] = None
    keys: Optional[list[str]] = None
    clicks: Optional[int] = None
    end_x: Optional[int] = None
    end_y: Optional[int] = None
    duration: Optional[float] = None
    button: Optional[str] = "left"


class APIKeyUpdate(BaseModel):
    agent_key: str
    api_key: str


class OutcomeUpdate(BaseModel):
    entry_id: int
    outcome: str
    feedback: str = ""


class SettingsUpdate(BaseModel):
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    microsoft_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    anthropic_model: Optional[str] = None
    gemini_model: Optional[str] = None
    capture_interval: Optional[float] = None
    ocr_enabled: Optional[bool] = None


# ──────────────────────────────────────────────
# WebSocket helpers
# ──────────────────────────────────────────────

async def broadcast(event: str, data: dict) -> None:
    """Broadcast an event to all connected WebSocket clients."""
    message = json.dumps({"event": event, "data": data})
    disconnected = []
    for ws in ws_connections:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        ws_connections.remove(ws)


# ──────────────────────────────────────────────
# Routes: UI
# ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the main UI."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text())
    return HTMLResponse(content="<h1>WA/D</h1><p>Static files not found.</p>")


# ──────────────────────────────────────────────
# Routes: Agent Management
# ──────────────────────────────────────────────

@app.get("/api/agents")
async def get_agents():
    """Get status of all AI agents."""
    return {"agents": agent_manager.get_agent_statuses()}


@app.post("/api/agents/key")
async def update_agent_key(req: APIKeyUpdate):
    """Update an agent's API key."""
    success = agent_manager.update_api_key(req.agent_key, req.api_key)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"success": True, "agents": agent_manager.get_agent_statuses()}


# ──────────────────────────────────────────────
# Routes: Query / Chat
# ──────────────────────────────────────────────

@app.post("/api/query")
async def query_agents(req: QueryRequest):
    """Send a query to all enabled AI agents and get consensus result."""
    screen_text = ""
    screen_image_b64 = ""

    # Capture screen if requested
    if req.include_screen:
        screen_state = screen_parser.parse_screen(monitor_index=req.monitor_index)
        screen_text = screen_state.text
        screen_image_b64 = screen_state.image_b64

    # Get context from memory
    context = ""
    if req.use_memory_context:
        context = await memory_store.get_context_for_instruction(req.instruction)

    # Broadcast that we're processing
    await broadcast("status", {"state": "processing", "instruction": req.instruction})

    # Query all agents
    responses = await agent_manager.query_all(
        instruction=req.instruction,
        screen_text=screen_text,
        screen_image_b64=screen_image_b64,
        context=context,
        agent_keys=req.agent_keys,
    )

    # Run consensus engine
    consensus = decision_engine.evaluate(responses)

    # Store in memory
    entry_id = await memory_store.store(
        instruction=req.instruction,
        screen_text=screen_text,
        agent_responses=[r.to_dict() for r in responses],
        selected_answer=consensus.selected_answer,
        selected_agent=consensus.selected_agent,
        confidence=consensus.confidence,
    )

    result = consensus.to_dict()
    result["memory_entry_id"] = entry_id

    # Broadcast result
    await broadcast("result", result)

    return result


@app.post("/api/query/upload")
async def query_with_image(
    instruction: str,
    image: UploadFile,
    use_memory_context: bool = True,
):
    """Query agents with an uploaded screenshot."""
    image_data = await image.read()
    pil_image = Image.open(io.BytesIO(image_data))

    # Parse the uploaded image
    state = screen_parser.parse_image(pil_image)

    context = ""
    if use_memory_context:
        context = await memory_store.get_context_for_instruction(instruction)

    responses = await agent_manager.query_all(
        instruction=instruction,
        screen_text=state.text,
        screen_image_b64=state.image_b64,
        context=context,
    )

    consensus = decision_engine.evaluate(responses)

    entry_id = await memory_store.store(
        instruction=instruction,
        screen_text=state.text,
        agent_responses=[r.to_dict() for r in responses],
        selected_answer=consensus.selected_answer,
        selected_agent=consensus.selected_agent,
        confidence=consensus.confidence,
    )

    result = consensus.to_dict()
    result["memory_entry_id"] = entry_id
    return result


# ──────────────────────────────────────────────
# Routes: Screen
# ──────────────────────────────────────────────

@app.post("/api/screen/permission")
async def set_screen_permission(grant: bool = True):
    """Grant or revoke screen capture permission."""
    if grant:
        screen_parser.grant_permission()
    else:
        screen_parser.revoke_permission()
    return {"permission_granted": grant}


@app.get("/api/screen/monitors")
async def list_monitors():
    """List all available monitors/screens."""
    try:
        monitors = screen_parser.capture.list_monitors()
        return {"monitors": monitors}
    except Exception:
        return {"monitors": [{"index": 0, "label": "Default (All)", "width": 0, "height": 0, "left": 0, "top": 0}]}


@app.get("/api/screen/capture")
async def capture_screen(monitor_index: int = 0):
    """Capture the current screen and return analysis."""
    screen_state = screen_parser.parse_screen(monitor_index=monitor_index)
    return screen_state.to_dict()


# ──────────────────────────────────────────────
# Routes: Actions (Desktop Control)
# ──────────────────────────────────────────────

@app.post("/api/action/permission")
async def set_action_permission(grant: bool = True):
    """Grant or revoke desktop control permission."""
    if grant:
        safety_monitor.grant_permission()
        safety_monitor.start_automation()
        action_controller.enable()
    else:
        safety_monitor.revoke_permission()
        action_controller.disable()
    return safety_monitor.get_status()


@app.post("/api/action/execute")
async def execute_action(req: ActionRequest):
    """Execute a desktop action."""
    if not safety_monitor.is_automation_allowed:
        raise HTTPException(
            status_code=403,
            detail="Automation not allowed. Grant permission first.",
        )

    safety_monitor.record_action(req.action_type, f"Execute {req.action_type}")

    result = None
    if req.action_type == "click" and req.x is not None and req.y is not None:
        result = action_controller.click(req.x, req.y, req.button or "left")
    elif req.action_type == "double_click" and req.x is not None and req.y is not None:
        result = action_controller.double_click(req.x, req.y)
    elif req.action_type == "right_click" and req.x is not None and req.y is not None:
        result = action_controller.right_click(req.x, req.y)
    elif req.action_type == "move" and req.x is not None and req.y is not None:
        result = action_controller.move_to(req.x, req.y, req.duration or 0.3)
    elif req.action_type == "type" and req.text:
        result = action_controller.type_text(req.text)
    elif req.action_type == "hotkey" and req.keys:
        result = action_controller.press_hotkey(*req.keys)
    elif req.action_type == "scroll" and req.clicks is not None:
        result = action_controller.scroll(req.clicks, req.x, req.y)
    elif (
        req.action_type == "drag"
        and req.x is not None
        and req.y is not None
        and req.end_x is not None
        and req.end_y is not None
    ):
        result = action_controller.drag_to(
            req.x, req.y, req.end_x, req.end_y, req.duration or 0.5
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action type or missing parameters: {req.action_type}",
        )

    await broadcast("action", result.to_dict())
    return result.to_dict()


@app.post("/api/action/pause")
async def pause_automation():
    """Pause automation."""
    safety_monitor.pause_automation()
    action_controller.pause()
    await broadcast("status", {"state": "paused"})
    return {"state": "paused"}


@app.post("/api/action/resume")
async def resume_automation():
    """Resume automation."""
    safety_monitor.resume_automation()
    action_controller.resume()
    await broadcast("status", {"state": "active"})
    return {"state": "active"}


@app.post("/api/action/stop")
async def emergency_stop():
    """Emergency stop all automation."""
    safety_monitor.emergency_stop()
    await broadcast("status", {"state": "emergency_stopped"})
    return {"state": "emergency_stopped"}


# ──────────────────────────────────────────────
# Routes: Memory
# ──────────────────────────────────────────────

@app.get("/api/memory/recent")
async def get_recent_memory(limit: int = 20):
    """Get recent memory entries."""
    entries = await memory_store.get_recent(limit)
    return {"entries": [e.to_dict() for e in entries]}


@app.post("/api/memory/outcome")
async def update_memory_outcome(req: OutcomeUpdate):
    """Update the outcome of a memory entry."""
    success = await memory_store.update_outcome(req.entry_id, req.outcome, req.feedback)
    return {"success": success}


@app.get("/api/memory/stats")
async def get_memory_stats():
    """Get memory statistics."""
    return await memory_store.get_stats()


@app.post("/api/memory/clear")
async def clear_memory():
    """Clear all memory."""
    await memory_store.clear()
    return {"success": True}


# ──────────────────────────────────────────────
# Routes: Safety
# ──────────────────────────────────────────────

@app.get("/api/safety/status")
async def get_safety_status():
    """Get current safety status."""
    return safety_monitor.get_status()


@app.get("/api/safety/events")
async def get_safety_events(limit: int = 50):
    """Get recent safety events."""
    return {"events": safety_monitor.get_events(limit)}


# ──────────────────────────────────────────────
# Routes: Settings
# ──────────────────────────────────────────────

@app.get("/api/settings")
async def get_settings():
    """Get current settings (API keys masked)."""
    return {
        "openai_api_key": _mask_key(settings.openai_api_key),
        "anthropic_api_key": _mask_key(settings.anthropic_api_key),
        "google_api_key": _mask_key(settings.google_api_key),
        "microsoft_api_key": _mask_key(settings.microsoft_api_key),
        "openai_model": settings.openai_model,
        "anthropic_model": settings.anthropic_model,
        "gemini_model": settings.gemini_model,
        "capture_interval": settings.capture_interval,
        "ocr_enabled": settings.ocr_enabled,
        "automation_enabled": settings.automation_enabled,
    }


@app.post("/api/settings")
async def update_settings(req: SettingsUpdate):
    """Update application settings and reinitialize agents."""
    if req.openai_api_key is not None:
        settings.openai_api_key = req.openai_api_key
        agent_manager.update_api_key("openai", req.openai_api_key)
    if req.anthropic_api_key is not None:
        settings.anthropic_api_key = req.anthropic_api_key
        agent_manager.update_api_key("anthropic", req.anthropic_api_key)
    if req.google_api_key is not None:
        settings.google_api_key = req.google_api_key
        agent_manager.update_api_key("gemini", req.google_api_key)
    if req.microsoft_api_key is not None:
        settings.microsoft_api_key = req.microsoft_api_key
        agent_manager.update_api_key("copilot", req.microsoft_api_key)
    if req.openai_model is not None:
        settings.openai_model = req.openai_model
    if req.anthropic_model is not None:
        settings.anthropic_model = req.anthropic_model
    if req.gemini_model is not None:
        settings.gemini_model = req.gemini_model
    if req.capture_interval is not None:
        settings.capture_interval = req.capture_interval
    if req.ocr_enabled is not None:
        settings.ocr_enabled = req.ocr_enabled
        screen_parser.ocr_enabled = req.ocr_enabled

    return {"success": True}


# ──────────────────────────────────────────────
# WebSocket
# ──────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await ws.accept()
    ws_connections.append(ws)
    logger.info("WebSocket client connected (%d total)", len(ws_connections))

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            event = msg.get("event", "")

            if event == "ping":
                await ws.send_text(json.dumps({"event": "pong", "data": {}}))

            elif event == "query":
                # Handle query via WebSocket
                instruction = msg.get("data", {}).get("instruction", "")
                include_screen = msg.get("data", {}).get("include_screen", False)
                if instruction:
                    # Process in background so we don't block
                    asyncio.create_task(
                        _ws_query(ws, instruction, include_screen)
                    )

            elif event == "capture":
                state = screen_parser.parse_screen()
                await ws.send_text(
                    json.dumps({"event": "screen_state", "data": state.to_dict()})
                )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket error: %s", e)
    finally:
        if ws in ws_connections:
            ws_connections.remove(ws)
        logger.info("WebSocket client disconnected (%d remaining)", len(ws_connections))


async def _ws_query(ws: WebSocket, instruction: str, include_screen: bool) -> None:
    """Process a query received via WebSocket."""
    try:
        screen_text = ""
        screen_image_b64 = ""

        if include_screen:
            state = screen_parser.parse_screen()
            screen_text = state.text
            screen_image_b64 = state.image_b64

        context = await memory_store.get_context_for_instruction(instruction)

        await ws.send_text(
            json.dumps({"event": "processing", "data": {"instruction": instruction}})
        )

        responses = await agent_manager.query_all(
            instruction=instruction,
            screen_text=screen_text,
            screen_image_b64=screen_image_b64,
            context=context,
        )

        consensus = decision_engine.evaluate(responses)

        entry_id = await memory_store.store(
            instruction=instruction,
            screen_text=screen_text,
            agent_responses=[r.to_dict() for r in responses],
            selected_answer=consensus.selected_answer,
            selected_agent=consensus.selected_agent,
            confidence=consensus.confidence,
        )

        result = consensus.to_dict()
        result["memory_entry_id"] = entry_id

        await ws.send_text(json.dumps({"event": "result", "data": result}))

    except Exception as e:
        await ws.send_text(
            json.dumps({"event": "error", "data": {"message": str(e)}})
        )


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _mask_key(key: str) -> str:
    """Mask an API key for display."""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


def run() -> None:
    """Run the application via CLI."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
