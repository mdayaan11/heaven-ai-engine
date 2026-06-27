"""
Heaven AI Engine — Pydantic Schemas
All request/response models and state machine types live here.
"""
from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import time


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────
class BuildPhase(str, Enum):
    QUEUED = "QUEUED"
    SCOPING = "SCOPING"
    ARCHITECTURE = "ARCHITECTURE"
    SYNTHESIS = "SYNTHESIS"
    SECURITY_SCAN = "SECURITY_SCAN"
    DEPLOYMENT = "DEPLOYMENT"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class LogLevel(str, Enum):
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SYSTEM = "SYSTEM"


class DeployTarget(str, Enum):
    VERCEL = "vercel"
    RENDER = "render"
    GITHUB_PAGES = "github_pages"


# ─────────────────────────────────────────────
# Request Models
# ─────────────────────────────────────────────
class BuildRequest(BaseModel):
    """Initial client project brief."""
    project_idea: str = Field(..., min_length=10, description="Raw project idea from client")
    client_name: str = Field(..., min_length=2)
    client_email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    deploy_target: DeployTarget = DeployTarget.VERCEL
    budget_usd: Optional[float] = Field(None, ge=0)


class ScopingAnswer(BaseModel):
    """Client answers to scoping questions."""
    build_task_id: str
    answers: Dict[str, str] = Field(..., description="Map of question_id → answer")


# ─────────────────────────────────────────────
# Log + Stream Models
# ─────────────────────────────────────────────
class LogEntry(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    phase: BuildPhase
    level: LogLevel = LogLevel.INFO
    tag: str  # e.g. SYS_LOG: SYNTHESIZING_CODE
    message: str
    metadata: Optional[Dict[str, Any]] = None


class StreamEvent(BaseModel):
    event: str  # "log" | "phase_change" | "complete" | "error"
    data: Dict[str, Any]


# ─────────────────────────────────────────────
# Scoping Phase Output
# ─────────────────────────────────────────────
class ScopingQuestion(BaseModel):
    question_id: str
    question_text: str
    options: Optional[List[str]] = None  # None = free text
    required: bool = True


class ScopingResult(BaseModel):
    questions: List[ScopingQuestion]
    estimated_price_usd: float
    complexity_score: int = Field(..., ge=1, le=10)
    estimated_build_time_minutes: int
    feature_summary: str


class FeatureAgreement(BaseModel):
    """Generated after scoping answers collected."""
    project_name: str
    tech_stack: str
    features: List[str]
    out_of_scope: List[str]
    price_usd: float
    delivery_estimate: str
    manifest_xml: str


# ─────────────────────────────────────────────
# Architecture Phase Output
# ─────────────────────────────────────────────
class DatabaseTable(BaseModel):
    table_name: str
    prisma_schema: str
    sql_schema: str


class ApiEndpoint(BaseModel):
    method: str  # GET POST PUT DELETE PATCH
    path: str
    description: str
    request_body: Optional[Dict[str, Any]] = None
    response_schema: Dict[str, Any]
    status_codes: List[int]
    auth_required: bool = True


class ArchitectureBlueprint(BaseModel):
    database_tables: List[DatabaseTable]
    api_endpoints: List[ApiEndpoint]
    tech_stack_manifest: str  # XML manifest
    folder_structure: str
    env_variables_needed: List[str]


# ─────────────────────────────────────────────
# Synthesis Phase Output
# ─────────────────────────────────────────────
class GeneratedFile(BaseModel):
    path: str
    content: str
    language: str  # typescript | python | json | prisma | css | html


class SandboxRunResult(BaseModel):
    command: str
    stdout: str
    stderr: str
    exit_code: int
    success: bool


class SynthesisResult(BaseModel):
    files: List[GeneratedFile]
    sandbox_runs: List[SandboxRunResult]
    correction_loops_used: int
    final_build_success: bool
    secrets_found_and_moved: List[str]


# ─────────────────────────────────────────────
# Deployment Phase Output
# ─────────────────────────────────────────────
class DeploymentResult(BaseModel):
    github_repo_url: str
    github_repo_name: str
    production_url: str
    deploy_target: DeployTarget
    deploy_id: str
    env_variables_markdown: str
    build_logs_url: Optional[str] = None


# ─────────────────────────────────────────────
# Full Build State (LangGraph GraphState)
# ─────────────────────────────────────────────
class BuildState(BaseModel):
    """Complete state passed through LangGraph nodes."""
    # Identity
    task_id: str
    client_name: str
    client_email: str
    deploy_target: DeployTarget

    # Phase tracking
    current_phase: BuildPhase = BuildPhase.QUEUED
    logs: List[LogEntry] = Field(default_factory=list)
    error_message: Optional[str] = None

    # Phase 1: Scoping
    raw_project_idea: str = ""
    scoping_result: Optional[ScopingResult] = None
    scoping_answers: Optional[Dict[str, str]] = None
    feature_agreement: Optional[FeatureAgreement] = None

    # Phase 2: Architecture
    architecture: Optional[ArchitectureBlueprint] = None

    # Phase 3: Synthesis
    synthesis: Optional[SynthesisResult] = None

    # Phase 4: Deployment
    deployment: Optional[DeploymentResult] = None

    class Config:
        arbitrary_types_allowed = True


# ─────────────────────────────────────────────
# API Response Models
# ─────────────────────────────────────────────
class BuildInitResponse(BaseModel):
    task_id: str
    message: str
    stream_url: str
    status: BuildPhase = BuildPhase.QUEUED


class BuildStatusResponse(BaseModel):
    task_id: str
    phase: BuildPhase
    logs: List[LogEntry]
    scoping_questions: Optional[List[ScopingQuestion]] = None
    feature_agreement: Optional[FeatureAgreement] = None
    deployment: Optional[DeploymentResult] = None
    error_message: Optional[str] = None
