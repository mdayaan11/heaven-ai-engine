"""Heaven AI Engine — Updated Routes using BackgroundTasks"""
from __future__ import annotations
import asyncio, io, json, os, time, uuid, zipfile
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from models.schemas import (
    BuildInitResponse, BuildPhase, BuildRequest, BuildState,
    BuildStatusResponse, ScopingAnswer,
)
from tasks.build_tasks import (
    get_build_state, get_logs, ping_redis,
    set_build_state, set_scoping_answers,
)
from agents.build_runner import launch_scoping_thread, launch_pipeline_thread

router = APIRouter(prefix="/api", tags=["engine"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "Heaven AI Engine",
        "model": "Gemini 2.0 Flash",
        "redis": "connected" if ping_redis() else "disconnected",
        "timestamp": time.time(),
    }


@router.post("/build/start", response_model=BuildInitResponse, status_code=201)
async def start_build(request: BuildRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    build = BuildState(
        task_id=task_id,
        client_name=request.client_name,
        client_email=request.client_email,
        deploy_target=request.deploy_target,
        raw_project_idea=request.project_idea,
        current_phase=BuildPhase.QUEUED,
    )
    set_build_state(task_id, build.model_dump())
    # Launch scoping in background thread
    background_tasks.add_task(launch_scoping_thread, build)
    return BuildInitResponse(
        task_id=task_id,
        message="Build initiated. Streaming live...",
        stream_url=f"/api/build/{task_id}/stream",
        status=BuildPhase.QUEUED,
    )


@router.post("/build/{task_id}/answers")
async def submit_answers(task_id: str, payload: ScopingAnswer, background_tasks: BackgroundTasks):
    state = get_build_state(task_id)
    if not state:
        raise HTTPException(404, f"Task {task_id} not found")
    set_scoping_answers(task_id, payload.answers)
    build = BuildState(**state)
    build.scoping_answers = payload.answers
    background_tasks.add_task(launch_pipeline_thread, build)
    return {"task_id": task_id, "message": "Answers received. Full build started.", "stream_url": f"/api/build/{task_id}/stream"}


@router.get("/build/{task_id}/status", response_model=BuildStatusResponse)
async def get_status(task_id: str):
    state = get_build_state(task_id)
    if not state:
        raise HTTPException(404, f"Task {task_id} not found")
    build = BuildState(**state)
    return BuildStatusResponse(
        task_id=task_id, phase=build.current_phase, logs=build.logs,
        scoping_questions=build.scoping_result.questions if build.scoping_result else None,
        feature_agreement=build.feature_agreement,
        deployment=build.deployment,
        error_message=build.error_message,
    )


@router.get("/build/{task_id}/stream")
async def stream_logs(task_id: str, request: Request):
    async def generator():
        idx = 0
        last_phase = None
        while True:
            if await request.is_disconnected():
                break
            for log in get_logs(task_id, since_index=idx):
                yield {"event": "log", "data": json.dumps(log), "id": str(idx)}
                idx += 1
            state = get_build_state(task_id)
            if state:
                phase = state.get("current_phase")
                if phase != last_phase:
                    last_phase = phase
                    yield {"event": "phase_change", "data": json.dumps({"phase": phase})}
                    if phase == BuildPhase.SCOPING and state.get("scoping_result"):
                        yield {"event": "scoping_ready", "data": json.dumps(state["scoping_result"])}
                    if phase == BuildPhase.COMPLETE and state.get("deployment"):
                        yield {"event": "complete", "data": json.dumps(state["deployment"])}
                        break
                    if phase == BuildPhase.FAILED:
                        yield {"event": "error", "data": json.dumps({"message": state.get("error_message", "Build failed")})}
                        break
            yield {"event": "heartbeat", "data": json.dumps({"ts": time.time()})}
            await asyncio.sleep(1.5)
    return EventSourceResponse(generator())


@router.get("/build/{task_id}/download")
async def download(task_id: str):
    state = get_build_state(task_id)
    if not state:
        raise HTTPException(404, "Not found")
    build = BuildState(**state)
    if not build.synthesis:
        raise HTTPException(400, "No files generated yet")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in build.synthesis.files:
            zf.writestr(f.path, f.content)
        if build.deployment:
            zf.writestr("ENV_SETUP.md", build.deployment.env_variables_markdown)
    buf.seek(0)
    name = (build.feature_agreement.project_name if build.feature_agreement else task_id).replace(" ", "-")
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{name}.zip"'})
