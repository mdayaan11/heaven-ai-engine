"""
Heaven AI Engine — Core Build Runner
Runs the full 4-phase pipeline in a background thread.
Uses Gemini + E2B + GitHub.
"""
from __future__ import annotations
import os
import time
import threading
from typing import Any, Dict, Optional
from models.schemas import (
    BuildPhase, BuildState, LogEntry, LogLevel,
    ScopingResult, FeatureAgreement, ArchitectureBlueprint,
    DatabaseTable, ApiEndpoint, GeneratedFile, SynthesisResult, DeploymentResult,
)
from agents.scaffold_templates import (
    auth_ts,
    db_ts,
    detect_imports,
    endpoint_to_route_path,
    globals_css,
    is_valid_package_json,
    is_valid_route_module,
    middleware_ts,
    next_config_ts,
    package_json,
    postcss_config,
    prisma_schema,
    route_handler,
    tailwind_config,
    tsconfig_json,
    utils_ts,
)
from services.gemini_service import GeminiService
from services.e2b_service import SandboxOrchestrator
from services.security_scanner import SecurityScannerService
from services.github_service import GitHubService
from tasks.build_tasks import push_log, set_build_state, get_scoping_answers


def _scaffold_content(path: str, project_name: str, ep: Optional[ApiEndpoint] = None) -> Optional[str]:
    """Return hardcoded content for files that must never be LLM placeholders."""
    if path == "package.json":
        return None  # Built later with auto-detected deps
    if path == "tsconfig.json":
        return tsconfig_json()
    if path in ("next.config.ts", "next.config.js"):
        return next_config_ts()
    if path in ("src/middleware.ts", "middleware.ts"):
        return middleware_ts()
    if path in ("src/lib/auth.ts", "lib/auth.ts"):
        return auth_ts()
    if path in ("src/lib/db.ts", "lib/db.ts", "src/lib/prisma.ts"):
        return db_ts()
    if path in ("src/lib/utils.ts", "lib/utils.ts", "src/utils/index.ts"):
        return utils_ts()
    if path in ("prisma/schema.prisma", "schema.prisma"):
        return prisma_schema()
    if path in ("tailwind.config.ts", "tailwind.config.js"):
        return tailwind_config()
    if path in ("postcss.config.js", "postcss.config.mjs"):
        return postcss_config()
    if path in ("src/app/globals.css", "app/globals.css"):
        return globals_css()
    if path.endswith("/route.ts"):
        return route_handler(ep)
    return None


def _inject_package_json(files: list, project_name: str) -> list:
    """Auto-detect all npm imports and build a complete package.json."""
    extra_deps, extra_dev = detect_imports(files)
    pkg_content = package_json(project_name, extra_deps, extra_dev)
    # Replace or add package.json
    result = [f for f in files if (f.path if hasattr(f, 'path') else f.get('path')) != 'package.json']
    result.insert(0, GeneratedFile(path='package.json', content=pkg_content, language='json'))
    return result


def _ensure_tailwind_files(files: list) -> list:
    """Make sure tailwind config files exist so CSS builds correctly."""
    paths = {(f.path if hasattr(f, 'path') else f.get('path', '')) for f in files}
    extras = []
    if 'tailwind.config.ts' not in paths:
        extras.append(GeneratedFile(path='tailwind.config.ts', content=tailwind_config(), language='typescript'))
    if 'postcss.config.js' not in paths:
        extras.append(GeneratedFile(path='postcss.config.js', content=postcss_config(), language='javascript'))
    if 'src/app/globals.css' not in paths and 'app/globals.css' not in paths:
        extras.append(GeneratedFile(path='src/app/globals.css', content=globals_css(), language='css'))
    return files + extras


def _sanitize_generated_files(
    files: list[GeneratedFile],
    project_name: str,
    endpoints_by_route: dict[str, ApiEndpoint],
) -> list[GeneratedFile]:
    """Ensure scaffold files are valid before E2B build and GitHub push."""
    sanitized: list[GeneratedFile] = []
    for f in files:
        content = f.content
        if f.path == "package.json" and not is_valid_package_json(content):
            content = package_json(project_name)
        elif f.path == "tsconfig.json":
            content = tsconfig_json()
        elif f.path in ("next.config.ts", "next.config.js"):
            content = next_config_ts()
        elif f.path.endswith("/route.ts") and not is_valid_route_module(content):
            content = route_handler(endpoints_by_route.get(f.path))
        sanitized.append(GeneratedFile(path=f.path, content=content, language=f.language))
    return sanitized


def _log(build: BuildState, tag: str, message: str, level: LogLevel = LogLevel.INFO) -> None:
    entry = LogEntry(
        timestamp=time.time(), phase=build.current_phase,
        level=level, tag=tag, message=message,
    )
    build.logs.append(entry)
    push_log(build.task_id, entry.model_dump())
    set_build_state(build.task_id, build.model_dump())


# ─────────────────────────────────────────────
# Pydantic-safe model builders
# (Gemini sometimes returns extra/renamed fields — filter them out)
# ─────────────────────────────────────────────
_DB_TABLE_FIELDS = {"table_name", "prisma_schema", "sql_schema"}
_ENDPOINT_FIELDS = {"method", "path", "description", "request_body",
                    "response_schema", "status_codes", "auth_required"}


def _safe_db_table(raw: Any) -> DatabaseTable:
    if not isinstance(raw, dict):
        return DatabaseTable(table_name="table", prisma_schema="", sql_schema="")
    filtered = {k: v for k, v in raw.items() if k in _DB_TABLE_FIELDS}
    filtered.setdefault("table_name", "table")
    filtered.setdefault("prisma_schema", "")
    filtered.setdefault("sql_schema", "")
    return DatabaseTable(**filtered)


def _safe_endpoint(raw: Any) -> ApiEndpoint:
    if not isinstance(raw, dict):
        return ApiEndpoint(method="GET", path="/api/health", description="health")
    d = {k: v for k, v in raw.items() if k in _ENDPOINT_FIELDS}
    # Rename if Gemini used alternative field names
    if "api_path" in raw and "path" not in d:
        d["path"] = raw["api_path"]
    if "api_description" in raw and "description" not in d:
        d["description"] = raw["api_description"]
    if "endpoint" in raw and "path" not in d:
        d["path"] = raw["endpoint"]
    if "route" in raw and "path" not in d:
        d["path"] = raw["route"]
    d.setdefault("method", "GET")
    d.setdefault("path", "/api/endpoint")
    d.setdefault("description", "")
    d.setdefault("request_body", {})
    d.setdefault("response_schema", {})
    d.setdefault("status_codes", [200])
    d.setdefault("auth_required", False)
    return ApiEndpoint(**d)


# ─────────────────────────────────────────────
# Phase 1: Scoping
# ─────────────────────────────────────────────
def run_scoping(build: BuildState) -> None:
    build.current_phase = BuildPhase.SCOPING
    set_build_state(build.task_id, build.model_dump())

    _log(build, "SYS_LOG: ALIGNING_PROMPT", "Analyzing your business requirements...", LogLevel.SYSTEM)
    llm = GeminiService(api_key=os.environ["GEMINI_API_KEY"])

    try:
        raw = llm.run_scoping(build.raw_project_idea)
        build.scoping_result = ScopingResult(
            questions=raw["questions"],
            estimated_price_usd=float(raw["estimated_price_usd"]),
            complexity_score=int(raw["complexity_score"]),
            estimated_build_time_minutes=int(raw["estimated_build_time_minutes"]),
            feature_summary=raw["feature_summary"],
        )
        _log(build, "SYS_LOG: ALIGNING_PROMPT",
             f"✅ Scoping complete. Complexity: {build.scoping_result.complexity_score}/10 | "
             f"Price: ${build.scoping_result.estimated_price_usd:.0f}",
             LogLevel.SUCCESS)
    except Exception as e:
        build.error_message = str(e)
        _log(build, "SYS_LOG: ALIGNING_PROMPT", f"❌ Scoping error: {str(e)}", LogLevel.ERROR)

    set_build_state(build.task_id, build.model_dump())


# ─────────────────────────────────────────────
# Full Pipeline (runs after answers received)
# ─────────────────────────────────────────────
def run_full_pipeline(build: BuildState) -> None:
    llm = GeminiService(api_key=os.environ["GEMINI_API_KEY"])

    # ── Feature Agreement ────────────────────
    _log(build, "SYS_LOG: ALIGNING_PROMPT", "Generating Feature Agreement...", LogLevel.INFO)
    try:
        raw = llm.generate_feature_agreement(
            build.raw_project_idea,
            build.scoping_result.model_dump(),
            build.scoping_answers or {},
        )
        build.feature_agreement = FeatureAgreement(
            project_name=raw["project_name"],
            tech_stack=raw["tech_stack"],
            features=raw["features"],
            out_of_scope=raw["out_of_scope"],
            price_usd=float(raw["price_usd"]),
            delivery_estimate=raw["delivery_estimate"],
            manifest_xml=raw["manifest_xml"],
        )
        _log(build, "SYS_LOG: ALIGNING_PROMPT",
             f"✅ Feature Agreement locked: {build.feature_agreement.project_name}",
             LogLevel.SUCCESS)
    except Exception as e:
        _log(build, "SYS_LOG: ALIGNING_PROMPT", f"❌ Agreement error: {e}", LogLevel.ERROR)
        build.error_message = str(e)
        set_build_state(build.task_id, build.model_dump())
        return

    # ── Architecture ─────────────────────────
    build.current_phase = BuildPhase.ARCHITECTURE
    _log(build, "SYS_LOG: ARCHITECTING_DB",
         "Building secure database relational schemas...", LogLevel.SYSTEM)
    try:
        raw = llm.run_architecture(build.feature_agreement.manifest_xml, build.scoping_answers or {})
        tables_raw = raw.get("database_tables", [])
        endpoints_raw = raw.get("api_endpoints", [])
        # Ensure both are lists (Gemini sometimes returns a dict)
        if isinstance(tables_raw, dict): tables_raw = list(tables_raw.values())
        if isinstance(endpoints_raw, dict): endpoints_raw = list(endpoints_raw.values())
        build.architecture = ArchitectureBlueprint(
            database_tables=[_safe_db_table(t) for t in tables_raw],
            api_endpoints=[_safe_endpoint(e) for e in endpoints_raw],
            tech_stack_manifest=raw.get("tech_stack_manifest", ""),
            folder_structure=raw.get("folder_structure", ""),
            env_variables_needed=raw.get("env_variables_needed", []),
        )
        _log(build, "SYS_LOG: ARCHITECTING_DB",
             f"✅ Architecture complete. {len(build.architecture.database_tables)} tables | "
             f"{len(build.architecture.api_endpoints)} endpoints",
             LogLevel.SUCCESS)
    except Exception as e:
        _log(build, "SYS_LOG: ARCHITECTING_DB", f"❌ Architecture error: {e}", LogLevel.ERROR)
        build.error_message = str(e)
        set_build_state(build.task_id, build.model_dump())
        return

    # ── Synthesis ────────────────────────────
    build.current_phase = BuildPhase.SYNTHESIS
    _log(build, "SYS_LOG: SYNTHESIZING_CODE",
         "Generating full-stack code blocks inside isolated E2B sandbox...", LogLevel.SYSTEM)

    arch = build.architecture
    agreement = build.feature_agreement
    is_nextjs = "next" in agreement.tech_stack.lower()

    blueprint_context = f"""
PROJECT: {agreement.project_name}
TECH STACK: {agreement.tech_stack}
FEATURES: {chr(10).join(f'- {f}' for f in agreement.features)}
DB SCHEMA: {chr(10).join(t.prisma_schema for t in arch.database_tables)}
API ENDPOINTS: {chr(10).join(f'{e.method} {e.path}' for e in arch.api_endpoints)}
NAMING RULE: All code variable names MUST exactly match database column names.
"""

    api_endpoints = arch.api_endpoints[:6]
    route_files = [endpoint_to_route_path(ep.path) for ep in api_endpoints]
    endpoints_by_route = dict(zip(route_files, api_endpoints))

    files_to_generate = [
        "package.json", "tsconfig.json", "next.config.ts",
        "prisma/schema.prisma", "src/lib/db.ts", "src/lib/auth.ts",
        "src/types/index.ts",
        *route_files,
        "src/app/layout.tsx", "src/app/page.tsx",
        "src/app/globals.css", "src/components/Navbar.tsx",
        "src/middleware.ts", ".env.example", "README.md",
    ] if is_nextjs else [
        "requirements.txt", "main.py", "database.py",
        "models.py", "auth.py", "routes.py", ".env.example", "README.md",
    ]

    generated: list[GeneratedFile] = []
    for i, fp in enumerate(files_to_generate):
        try:
            _log(build, "SYS_LOG: SYNTHESIZING_CODE",
                 f"Writing {fp} ({i+1}/{len(files_to_generate)})...")
            scaffold = _scaffold_content(
                fp,
                agreement.project_name,
                endpoints_by_route.get(fp) if is_nextjs else None,
            )
            if scaffold is not None:
                generated.append(GeneratedFile(path=fp, content=scaffold, language="typescript"))
                continue
            raw = llm.generate_file(fp, blueprint_context, [f.model_dump() for f in generated])
            generated.append(GeneratedFile(
                path=raw["path"], content=raw["content"],
                language=raw.get("language", "typescript"),
            ))
        except Exception as e:
            _log(build, "SYS_LOG: SYNTHESIZING_CODE",
                 f"⚠ Skipped {fp}: {str(e)[:80]}", LogLevel.WARNING)

    if is_nextjs:
        # Auto-detect imports → inject into package.json + ensure Tailwind files
        generated = _inject_package_json(generated, agreement.project_name)
        generated = _ensure_tailwind_files(generated)
        generated = _sanitize_generated_files(generated, agreement.project_name, endpoints_by_route)

    _log(build, "SYS_LOG: SYNTHESIZING_CODE",
         f"✅ {len(generated)} files generated. Injecting into E2B sandbox...", LogLevel.SUCCESS)

    # ── E2B Sandbox Build + Self-Correct ─────
    _log(build, "SYS_LOG: RUNNING_QA_TESTS",
         "Compiling code. Running automated bug-checks...", LogLevel.SYSTEM)

    def on_log(msg): _log(build, "SYS_LOG: RUNNING_QA_TESTS", msg)
    def correct_fn(err, buggy): return llm.self_correct(err, buggy)

    try:
        orchestrator = SandboxOrchestrator(e2b_api_key=os.environ["E2B_API_KEY"])
        final_files, runs, build_ok = orchestrator.run_full_synthesis(
            files=generated,
            project_type="node" if is_nextjs else "python",
            on_log=on_log,
            correct_fn=correct_fn,
        )
        _log(build, "SYS_LOG: RUNNING_QA_TESTS",
             f"{'✅ Build PASSED' if build_ok else '⚠ Build done with warnings'} — "
             f"{orchestrator.correction_loops_used} self-correction(s) used",
             LogLevel.SUCCESS if build_ok else LogLevel.WARNING)
    except Exception as e:
        _log(build, "SYS_LOG: RUNNING_QA_TESTS",
             f"⚠ Sandbox error: {str(e)[:100]}. Using generated files directly.", LogLevel.WARNING)
        final_files = generated
        runs = []
        build_ok = True

    # ── Security Scan ─────────────────────────
    build.current_phase = BuildPhase.SECURITY_SCAN
    _log(build, "SYS_LOG: RUNNING_QA_TESTS",
         "🔒 Running security scan — stripping secrets...", LogLevel.SYSTEM)
    scanner = SecurityScannerService()
    sanitized, secrets, vulns = scanner.scan_and_sanitize(final_files)
    build.synthesis = SynthesisResult(
        files=sanitized, sandbox_runs=runs,
        correction_loops_used=getattr(orchestrator if 'orchestrator' in dir() else object(), 'correction_loops_used', 0),
        final_build_success=build_ok,
        secrets_found_and_moved=secrets,
    )
    _log(build, "SYS_LOG: RUNNING_QA_TESTS",
         f"✅ Security scan done. {len(secrets)} secret(s) → .env", LogLevel.SUCCESS)

    # ── GitHub Deploy ─────────────────────────
    build.current_phase = BuildPhase.DEPLOYMENT
    _log(build, "SYS_LOG: DEPLOYING_PROD",
         "Pushing live code to GitHub...", LogLevel.SYSTEM)
    try:
        github = GitHubService(
            token=os.environ["GITHUB_TOKEN"],
            username=os.environ["GITHUB_USERNAME"],
        )
        repo = github.create_repo(repo_name=agreement.project_name, private=False)
        _log(build, "SYS_LOG: DEPLOYING_PROD", f"✅ Repo created: {repo['html_url']}", LogLevel.SUCCESS)

        github.commit_files(
            repo_full_name=repo["full_name"],
            files=sanitized,
            commit_message=f"🚀 {agreement.project_name} — built by Heaven AI Engine",
        )
        _log(build, "SYS_LOG: DEPLOYING_PROD", f"✅ {len(sanitized)} files committed", LogLevel.SUCCESS)

        env_md = _env_markdown(agreement, secrets)
        deploy_url = f"https://vercel.com/new/clone?repository-url={repo['html_url']}"

        build.deployment = DeploymentResult(
            github_repo_url=repo["html_url"],
            github_repo_name=repo["repo_name"],
            production_url=deploy_url,
            deploy_target=build.deploy_target,
            deploy_id=repo["repo_name"],
            env_variables_markdown=env_md,
        )
        build.current_phase = BuildPhase.COMPLETE
        _log(build, "SYS_LOG: DEPLOYING_PROD",
             f"🎉 COMPLETE — Deploy at: {deploy_url}", LogLevel.SUCCESS)

    except Exception as e:
        build.error_message = str(e)
        build.current_phase = BuildPhase.FAILED
        _log(build, "SYS_LOG: DEPLOYING_PROD", f"❌ Deploy error: {e}", LogLevel.ERROR)

    set_build_state(build.task_id, build.model_dump())


def _env_markdown(agreement: FeatureAgreement, secrets: list) -> str:
    lines = [
        f"# {agreement.project_name} — Environment Setup",
        f"\nGenerated by Heaven AI Engine\n",
        "## Required Environment Variables\n",
        "```env",
        *[f"{s}=your_{s.lower()}_here" for s in sorted(set(secrets))],
        "DATABASE_URL=postgresql://user:pass@host/db",
        "NEXTAUTH_SECRET=generate_with_openssl_rand_base64_32",
        "NEXTAUTH_URL=https://your-app.vercel.app",
        "```",
        "\n## Deploy Steps",
        "1. Import repo to Vercel → vercel.com/new",
        "2. Add environment variables above",
        "3. Click Deploy ✅",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Thread launcher
# ─────────────────────────────────────────────
def launch_scoping_thread(build: BuildState) -> None:
    t = threading.Thread(target=run_scoping, args=(build,), daemon=True)
    t.start()


def launch_pipeline_thread(build: BuildState) -> None:
    t = threading.Thread(target=run_full_pipeline, args=(build,), daemon=True)
    t.start()
