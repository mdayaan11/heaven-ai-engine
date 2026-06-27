"""
Heaven AI Engine — All Pydantic Schemas
"""
from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import time


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


class BuildRequest(BaseModel):
    project_idea: str = Field(..., min_length=10)
    client_name: str = Field(..., min_length=2)
    client_email: str
    deploy_target: DeployTarget = DeployTarget.VERCEL
    budget_usd: Optional[float] = None


class ScopingAnswer(BaseModel):
    build_task_id: str
    answers: Dict[str, str]


class LogEntry(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    phase: BuildPhase = BuildPhase.QUEUED
    level: LogLevel = LogLevel.INFO
    tag: str = ""
    message: str = ""
    metadata: Optional[Dict[str, Any]] = None


class ScopingQuestion(BaseModel):
    question_id: str
    question_text: str
    options: Optional[List[str]] = None
    required: bool = True


class ScopingResult(BaseModel):
    questions: List[ScopingQuestion] = []
    estimated_price_usd: float = 0.0
    complexity_score: int = 5
    estimated_build_time_minutes: int = 10
    feature_summary: str = ""


class FeatureAgreement(BaseModel):
    project_name: str
    tech_stack: str
    features: List[str] = []
    out_of_scope: List[str] = []
    price_usd: float = 0.0
    delivery_estimate: str = ""
    manifest_xml: str = ""


class DatabaseTable(BaseModel):
    table_name: str = ""
    prisma_schema: str = ""
    sql_schema: str = ""


class ApiEndpoint(BaseModel):
    method: str = "GET"
    path: str = "/"
    description: str = ""
    request_body: Optional[Dict[str, Any]] = None
    response_schema: Dict[str, Any] = {}
    status_codes: List[int] = [200]
    auth_required: bool = True


class ArchitectureBlueprint(BaseModel):
    database_tables: List[DatabaseTable] = []
    api_endpoints: List[ApiEndpoint] = []
    tech_stack_manifest: str = ""
    folder_structure: str = ""
    env_variables_needed: List[str] = []


class GeneratedFile(BaseModel):
    path: str
    content: str
    language: str = "typescript"


# Alias used in build_runner
SandboxRun = dict


class SynthesisResult(BaseModel):
    files: List[GeneratedFile] = []
    sandbox_runs: List[Dict[str, Any]] = []
    correction_loops_used: int = 0
    final_build_success: bool = True
    secrets_found_and_moved: List[str] = []


class DeploymentResult(BaseModel):
    github_repo_url: str = ""
    github_repo_name: str = ""
    production_url: str = ""
    deploy_target: DeployTarget = DeployTarget.VERCEL
    deploy_id: str = ""
    env_variables_markdown: str = ""
    build_logs_url: Optional[str] = None


class BuildState(BaseModel):
    task_id: str
    client_name: str = ""
    client_email: str = ""
    deploy_target: DeployTarget = DeployTarget.VERCEL
    current_phase: BuildPhase = BuildPhase.QUEUED
    logs: List[LogEntry] = []
    error_message: Optional[str] = None
    raw_project_idea: str = ""
    scoping_result: Optional[ScopingResult] = None
    scoping_answers: Optional[Dict[str, str]] = None
    feature_agreement: Optional[FeatureAgreement] = None
    architecture: Optional[ArchitectureBlueprint] = None
    synthesis: Optional[SynthesisResult] = None
    deployment: Optional[DeploymentResult] = None

    model_config = {"arbitrary_types_allowed": True}


class BuildInitResponse(BaseModel):
    task_id: str
    message: str
    stream_url: str
    status: BuildPhase = BuildPhase.QUEUED


class BuildStatusResponse(BaseModel):
    task_id: str
    phase: BuildPhase
    logs: List[LogEntry] = []
    scoping_questions: Optional[List[ScopingQuestion]] = None
    feature_agreement: Optional[FeatureAgreement] = None
    deployment: Optional[DeploymentResult] = None
    error_message: Optional[str] = None
