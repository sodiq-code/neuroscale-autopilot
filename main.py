"""
NeuroScale Autopilot — FastAPI Application Entry Point
Serves the REST API + WebSocket events + React dashboard.
"""

import asyncio
import os
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from orchestrator import Orchestrator, incident_log

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ]
)

logger = structlog.get_logger(__name__)

orchestrator: Optional[Orchestrator] = None
ws_clients: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop orchestrator with app lifecycle."""
    global orchestrator
    orchestrator = Orchestrator()

    # Start detector in background
    detector_task = asyncio.create_task(orchestrator.start())
    logger.info("neuroscale_autopilot_api_ready")

    yield

    # Shutdown
    await orchestrator.stop()
    detector_task.cancel()
    logger.info("neuroscale_autopilot_api_shutdown")


app = FastAPI(
    title="NeuroScale Autopilot",
    description="Self-healing Kubernetes infrastructure agent powered by Qwen AI",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "neuroscale-autopilot", "version": "1.0.0"}


# ─── Incidents ─────────────────────────────────────────────────────────────────

@app.get("/api/incidents")
async def get_incidents():
    """Get all incidents in reverse chronological order."""
    return {"incidents": orchestrator.get_incidents(), "total": len(incident_log)}


@app.get("/api/incidents/{alert_id}")
async def get_incident(alert_id: str):
    inc = orchestrator.get_incident(alert_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc


# ─── Simulation ────────────────────────────────────────────────────────────────

class SimulateRequest(BaseModel):
    scenario: str = "oomkill"  # oomkill | crashloop | policy_violation | cost_spike


@app.post("/api/simulate")
async def simulate(req: SimulateRequest, background_tasks: BackgroundTasks):
    """Trigger a demo incident scenario."""
    valid = ["oomkill", "crashloop", "policy_violation", "cost_spike"]
    if req.scenario not in valid:
        raise HTTPException(status_code=400, detail=f"Scenario must be one of: {valid}")

    result = await orchestrator.simulate(req.scenario)
    await _broadcast_update()
    return result


# ─── Approvals ─────────────────────────────────────────────────────────────────

class ApprovalRequest(BaseModel):
    token: str
    approved: bool
    operator: str
    reason: Optional[str] = ""


@app.post("/api/approve")
async def approve(req: ApprovalRequest):
    """Submit human approval/rejection for a pending remediation."""
    success = orchestrator.escalation.submit_approval(
        token=req.token,
        approved=req.approved,
        operator=req.operator,
        reason=req.reason or "",
    )
    if not success:
        raise HTTPException(status_code=404, detail="Approval token not found or expired")

    await _broadcast_update()
    return {"success": True, "approved": req.approved, "token": req.token}


# ─── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats():
    """Dashboard stats summary."""
    incidents = incident_log
    total = len(incidents)
    resolved = sum(1 for i in incidents if i.get("status") == "resolved")
    failed = sum(1 for i in incidents if i.get("status") == "failed")
    pending = sum(1 for i in incidents if i.get("status") == "awaiting_approval")

    by_type = {}
    for inc in incidents:
        t = inc["alert"].get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    avg_duration = 0
    durations = [i["execution"]["duration_seconds"] for i in incidents if i.get("execution") and i["execution"].get("duration_seconds")]
    if durations:
        avg_duration = sum(durations) / len(durations)

    return {
        "total": total,
        "resolved": resolved,
        "failed": failed,
        "pending_approval": pending,
        "auto_remediation_rate": round(resolved / total * 100, 1) if total > 0 else 0,
        "avg_resolution_seconds": round(avg_duration, 2),
        "by_type": by_type,
    }


# ─── WebSocket (live updates) ───────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    logger.info("websocket_connected", clients=len(ws_clients))
    try:
        # Send current state on connect
        await ws.send_json({"type": "init", "incidents": orchestrator.get_incidents()})
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        ws_clients.remove(ws)
        logger.info("websocket_disconnected", clients=len(ws_clients))


async def _broadcast_update():
    """Push incident updates to all connected WebSocket clients."""
    if not ws_clients:
        return
    payload = {"type": "update", "incidents": orchestrator.get_incidents()}
    dead = []
    for ws in ws_clients:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.remove(ws)


# ─── Serve React Dashboard ──────────────────────────────────────────────────────
dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard", "dist")
if os.path.exists(dashboard_path):
    app.mount("/", StaticFiles(directory=dashboard_path, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8000")),
        reload=os.getenv("ENVIRONMENT", "production") == "development",
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
