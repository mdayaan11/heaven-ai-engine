"""
Heaven AI Engine — API Routes
"""
from __future__ import annotations
import os
import uuid
import time
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any

router = APIRouter(prefix="/api/v1", tags=["Heaven AI Engine"])


# ── Request / Response Models ──────────────────────────────────────────────

class BuildRequest(BaseModel):
    project_idea: str
    deploy_target: str = "vercel"


class ScopingAnswersRequest(BaseModel):
    task_id: str
    answers: Dict[str, str]


class BuildResponse(BaseModel):
    task_id: str
    status: str
    message: str


# ── In-memory state store (replace with Redis in production) ───────────────

_build_states: Dict[str, Any] = {}
_build_logs: Dict[str, list] = {}


def _get_state(task_id: str) -> Optional[Dict]:
    return _build_states.get(task_id)


def _set_state(task_id: str, state: Dict) -> None:
    _build_states[task_id] = state


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "Heaven AI Engine",
    }


@router.post("/build/start", response_model=BuildResponse)
async def start_build(req: BuildRequest, background_tasks: BackgroundTasks):
    """
    Start a new build pipeline.
    Triggers scoping phase immediately in background.
    """
    task_id = str(uuid.uuid4())

    # Initialize build state
    state = {
        "task_id": task_id,
        "raw_project_idea": req.project_idea,
        "deploy_target": req.deploy_target,
        "current_phase": "SCOPING",
        "status": "running",
        "logs": [],
        "scoping_result": None,
        "feature_agreement": None,
        "architecture": None,
        "synthesis": None,
        "deployment": None,
        "error_message": None,
        "created_at": time.time(),
    }
    _set_state(task_id, state)

    # Launch scoping in background
    background_tasks.add_task(_run_scoping_bg, task_id, req.project_idea)

    return BuildResponse(
        task_id=task_id,
        status="started",
        message="Build pipeline started. Poll /build/status/{task_id} for updates.",
    )


@router.get("/build/status/{task_id}")
async def get_build_status(task_id: str):
    """Poll build status and logs."""
    state = _get_state(task_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
    return state


@router.get("/build/logs/{task_id}")
async def get_build_logs(task_id: str):
    """Get all logs for a build task."""
    state = _get_state(task_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
    return {"task_id": task_id, "logs": state.get("logs", [])}


@router.post("/build/answers")
async def submit_scoping_answers(req: ScopingAnswersRequest, background_tasks: BackgroundTasks):
    """
    Submit answers to scoping questions.
    Triggers the full pipeline (architecture → synthesis → deploy).
    """
    state = _get_state(req.task_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Task {req.task_id} not found.")

    state["scoping_answers"] = req.answers
    state["current_phase"] = "ARCHITECTURE"
    _set_state(req.task_id, state)

    background_tasks.add_task(_run_pipeline_bg, req.task_id)

    return {"task_id": req.task_id, "status": "pipeline_started", "message": "Full pipeline launched."}


@router.delete("/build/{task_id}")
async def cancel_build(task_id: str):
    """Cancel / clear a build task."""
    if task_id not in _build_states:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
    del _build_states[task_id]
    return {"task_id": task_id, "status": "cancelled"}


# ── Background task runners ────────────────────────────────────────────────

def _add_log(task_id: str, phase: str, message: str, level: str = "INFO"):
    state = _get_state(task_id)
    if state:
        state["logs"].append({
            "timestamp": time.time(),
            "phase": phase,
            "level": level,
            "message": message,
        })
        _set_state(task_id, state)


async def _run_scoping_bg(task_id: str, project_idea: str):
    """Run scoping phase using Gemini."""
    try:
        from core.build_runner import run_scoping
        from models.schemas import BuildState, BuildPhase

        state = _get_state(task_id)
        build = BuildState(**state)
        run_scoping(build)
        _set_state(task_id, build.model_dump())
    except ImportError:
        # Graceful fallback if build_runner not available
        _add_log(task_id, "SCOPING", "⚠ build_runner not found — running in stub mode", "WARNING")
        state = _get_state(task_id)
        if state:
            state["scoping_result"] = {
                "questions": ["What is the primary goal of your project?"],
                "estimated_price_usd": 0,
                "complexity_score": 5,
                "estimated_build_time_minutes": 30,
                "feature_summary": "Project scoped successfully.",
            }
            state["current_phase"] = "AWAITING_ANSWERS"
            _set_state(task_id, state)
    except Exception as e:
        state = _get_state(task_id)
        if state:
            state["error_message"] = str(e)
            state["current_phase"] = "FAILED"
            _set_state(task_id, state)


async def _run_pipeline_bg(task_id: str):
    """Run full pipeline after answers received."""
    try:
        from core.build_runner import run_full_pipeline
        from models.schemas import BuildState

        state = _get_state(task_id)
        build = BuildState(**state)
        run_full_pipeline(build)
        _set_state(task_id, build.model_dump())
    except ImportError:
        _add_log(task_id, "PIPELINE", "⚠ build_runner not found — stub mode", "WARNING")
        state = _get_state(task_id)
        if state:
            state["current_phase"] = "COMPLETE"
            _set_state(task_id, state)
    except Exception as e:
        state = _get_state(task_id)
        if state:
            state["error_message"] = str(e)
            state["current_phase"] = "FAILED"
            _set_state(task_id, state)
