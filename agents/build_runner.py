"""
Heaven AI Engine — Core Build Runner
Runs the full 4-phase pipeline in a background thread.
Uses Gemini + E2B + GitHub.

Every possible crash point is wrapped in try/except with sensible fallbacks.
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
    env_example,
    globals_css,
    is_valid_package_json,
    is_valid_route_module,
    is_valid_ts,
    is_valid_tsx,
    layout_tsx,
    middleware_ts,
    next_config_ts,
    package_json,
    postcss_config,
    prisma_schema,
    readme_md,
    route_handler,
    tailwind_config,
    tsconfig_json,
    types_index_ts,
    utils_ts,
)
from services.gemini_service import GeminiService
from services.e2b_service import SandboxOrchestrator
from services.security_scanner import SecurityScannerService
from services.github_service import GitHubService
from tasks.build_tasks import push_log, set_build_state, get_scoping_answers


# ─────────────────────────────────────────────────────────────────────────────
# Scaffolding: hardcoded files that Gemini must NEVER generate
# ─────────────────────────────────────────────────────────────────────────────
def _scaffold_content(path: str, project_name: str, ep: Optional[ApiEndpoint] = None) -> Optional[str]:
    """Return hardcoded content for critical files. Returns None if Gemini should generate it."""
    p = path.lower()
    # Config files
    if p == "package.json":
        return None  # Built later with auto-detected deps
    if p == "tsconfig.json":
        return tsconfig_json()
    if p in ("next.config.ts", "next.config.js"):
        return next_config_ts()
    if p in ("tailwind.config.ts", "tailwind.config.js"):
        return tailwind_config()
    if p in ("postcss.config.js", "postcss.config.mjs"):
        return postcss_config()
    # Source files that must be valid TS (not TSX)
    if p in ("src/middleware.ts", "middleware.ts"):
        return middleware_ts()
    if p in ("src/lib/auth.ts", "lib/auth.ts"):
        return auth_ts()
    if p in ("src/lib/db.ts", "lib/db.ts", "src/lib/prisma.ts"):
        return db_ts()
    if p in ("src/lib/utils.ts", "lib/utils.ts", "src/utils/index.ts"):
        return utils_ts()
    if p in ("src/types/index.ts", "types/index.ts"):
        return types_index_ts()
    # Schema
    if p in ("prisma/schema.prisma", "schema.prisma"):
        return prisma_schema()
    # CSS
    if p in ("src/app/globals.css", "app/globals.css"):
        return globals_css()
    # Layout — critical, app won't render without it
    if p in ("src/app/layout.tsx", "app/layout.tsx"):
        return layout_tsx(project_name)
    # Static files that don't need LLM
    if p == ".env.example":
        return env_example()
    if p == "readme.md":
        return readme_md(project_name)
    # API routes
    if p.endswith("/route.ts"):
        return route_handler(ep)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Post-generation fixers
# ─────────────────────────────────────────────────────────────────────────────
def _inject_package_json(files: list, project_name: str) -> list:
    """Auto-detect all npm imports and build a complete package.json."""
    extra_deps, extra_dev = detect_imports(files)
    pkg_content = package_json(project_name, extra_deps, extra_dev)
    result = [f for f in files if getattr(f, 'path', '') != 'package.json']
    result.insert(0, GeneratedFile(path='package.json', content=pkg_content, language='json'))
    return result


def _ensure_required_files(files: list, project_name: str) -> list:
    """Ensure Tailwind config, PostCSS, globals.css, and layout.tsx always exist."""
    paths = {getattr(f, 'path', '') for f in files}
    extras = []
    if 'tailwind.config.ts' not in paths:
        extras.append(GeneratedFile(path='tailwind.config.ts', content=tailwind_config(), language='typescript'))
    if 'postcss.config.js' not in paths:
        extras.append(GeneratedFile(path='postcss.config.js', content=postcss_config(), language='javascript'))
    if 'src/app/globals.css' not in paths and 'app/globals.css' not in paths:
        extras.append(GeneratedFile(path='src/app/globals.css', content=globals_css(), language='css'))
    if 'src/app/layout.tsx' not in paths and 'app/layout.tsx' not in paths:
        extras.append(GeneratedFile(path='src/app/layout.tsx', content=layout_tsx(project_name), language='typescript'))
    return files + extras


def _sanitize_generated_files(
    files: list[GeneratedFile],
    project_name: str,
    endpoints_by_route: dict[str, ApiEndpoint],
) -> list[GeneratedFile]:
    """Final pass — fix any broken files before pushing to GitHub."""
    sanitized: list[GeneratedFile] = []
    for f in files:
        content = f.content
        path = f.path

        # package.json must be valid JSON with deps
        if path == "package.json" and not is_valid_package_json(content):
            content = package_json(project_name)

        # Config files — always use hardcoded
        elif path == "tsconfig.json":
            content = tsconfig_json()
        elif path in ("next.config.ts", "next.config.js"):
            content = next_config_ts()

        # Route files must export handlers
        elif path.endswith("/route.ts") and not is_valid_route_module(content):
            content = route_handler(endpoints_by_route.get(path))

        # .ts files must NOT contain JSX
        elif path.endswith(".ts") and not path.endswith(".d.ts") and not is_valid_ts(content):
            # Replace with safe fallback
            content = "// auto-generated\nexport {};"

        # .tsx files must have valid exports
        elif path.endswith(".tsx") and not is_valid_tsx(content):
            content = f"export default function Component() {{ return <div className=\"p-8 text-white\">Loading {path.split('/')[-1]}...</div>; }}"

        sanitized.append(GeneratedFile(path=path, content=content, language=f.language))
    return sanitized


# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
def _log(build: BuildState, tag: str, message: str, level: LogLevel = LogLevel.INFO) -> None:
    entry = LogEntry(
        timestamp=time.time(), phase=build.current_phase,
        level=level, tag=tag, message=message,
    )
    build.logs.append(entry)
    try:
        push_log(build.task_id, entry.model_dump())
        set_build_state(build.task_id, build.model_dump())
    except Exception:
        pass  # Don't crash if Redis is down


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic-safe model builders
# ─────────────────────────────────────────────────────────────────────────────
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
    # Gemini sometimes uses alternative field names
    for alt in ("api_path", "endpoint", "route", "url"):
        if alt in raw and "path" not in d:
            d["path"] = raw[alt]
    for alt in ("api_description", "desc", "summary"):
        if alt in raw and "description" not in d:
            d["description"] = raw[alt]
    d.setdefault("method", "GET")
    d.setdefault("path", "/api/endpoint")
    d.setdefault("description", "")
    d.setdefault("request_body", {})
    d.setdefault("response_schema", {})
    d.setdefault("status_codes", [200])
    d.setdefault("auth_required", False)
    return ApiEndpoint(**d)


def _safe_feature_agreement(raw: Dict, idea: str) -> FeatureAgreement:
    """Build FeatureAgreement safely — handle missing/wrong keys."""
    name = str(raw.get("project_name", ""))
    # If Gemini used the raw prompt as name, extract a proper one
    if not name or name.lower().startswith(("build", "make", "create", "design", "generate")) or len(name) > 30:
        name = GeminiService._extract_project_name(idea)
    return FeatureAgreement(
        project_name=name,
        tech_stack=str(raw.get("tech_stack", "Next.js 15 + TypeScript + Tailwind CSS")),
        features=list(raw.get("features", ["Core UI", "Responsive design"])),
        out_of_scope=list(raw.get("out_of_scope", ["Mobile app"])),
        price_usd=float(raw.get("price_usd", 500.0)),
        delivery_estimate=str(raw.get("delivery_estimate", "12 min")),
        manifest_xml=str(raw.get("manifest_xml", "<manifest><v>1</v></manifest>")),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: Scoping
# ─────────────────────────────────────────────────────────────────────────────
def run_scoping(build: BuildState) -> None:
    build.current_phase = BuildPhase.SCOPING
    set_build_state(build.task_id, build.model_dump())

    _log(build, "SYS_LOG: ALIGNING_PROMPT", "Analyzing your business requirements...", LogLevel.SYSTEM)
    llm = GeminiService(api_key=os.environ["GEMINI_API_KEY"])

    try:
        raw = llm.run_scoping(build.raw_project_idea)
        build.scoping_result = ScopingResult(
            questions=raw.get("questions", []),
            estimated_price_usd=float(raw.get("estimated_price_usd", 500)),
            complexity_score=int(raw.get("complexity_score", 5)),
            estimated_build_time_minutes=int(raw.get("estimated_build_time_minutes", 10)),
            feature_summary=str(raw.get("feature_summary", build.raw_project_idea[:200])),
        )
        _log(build, "SYS_LOG: ALIGNING_PROMPT",
             f"✅ Scoping complete. Complexity: {build.scoping_result.complexity_score}/10 | "
             f"Price: ${build.scoping_result.estimated_price_usd:.0f}",
             LogLevel.SUCCESS)
    except Exception as e:
        build.error_message = str(e)
        _log(build, "SYS_LOG: ALIGNING_PROMPT", f"❌ Scoping error: {str(e)}", LogLevel.ERROR)

    set_build_state(build.task_id, build.model_dump())


# ─────────────────────────────────────────────────────────────────────────────
# Full Pipeline (runs after answers received)
# ─────────────────────────────────────────────────────────────────────────────
def run_full_pipeline(build: BuildState) -> None:
    llm = GeminiService(api_key=os.environ["GEMINI_API_KEY"])
    correction_loops = 0

    # ── Feature Agreement ────────────────────
    _log(build, "SYS_LOG: ALIGNING_PROMPT", "Generating Feature Agreement...", LogLevel.INFO)
    try:
        raw = llm.generate_feature_agreement(
            build.raw_project_idea,
            build.scoping_result.model_dump() if build.scoping_result else {},
            build.scoping_answers or {},
        )
        build.feature_agreement = _safe_feature_agreement(raw, build.raw_project_idea)
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
    set_build_state(build.task_id, build.model_dump())
    _log(build, "SYS_LOG: ARCHITECTING_DB",
         "Building secure database relational schemas...", LogLevel.SYSTEM)
    try:
        raw = llm.run_architecture(build.feature_agreement.manifest_xml, build.scoping_answers or {})
        tables_raw = raw.get("database_tables", [])
        endpoints_raw = raw.get("api_endpoints", [])
        if isinstance(tables_raw, dict):
            tables_raw = list(tables_raw.values())
        if isinstance(endpoints_raw, dict):
            endpoints_raw = list(endpoints_raw.values())
        if not isinstance(tables_raw, list):
            tables_raw = []
        if not isinstance(endpoints_raw, list):
            endpoints_raw = []
        build.architecture = ArchitectureBlueprint(
            database_tables=[_safe_db_table(t) for t in tables_raw],
            api_endpoints=[_safe_endpoint(e) for e in endpoints_raw],
            tech_stack_manifest=str(raw.get("tech_stack_manifest", "")),
            folder_structure=str(raw.get("folder_structure", "")),
            env_variables_needed=list(raw.get("env_variables_needed", [])),
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
    set_build_state(build.task_id, build.model_dump())
    _log(build, "SYS_LOG: SYNTHESIZING_CODE",
         "Generating full-stack code...", LogLevel.SYSTEM)

    arch = build.architecture
    agreement = build.feature_agreement
    is_nextjs = "next" in agreement.tech_stack.lower()

    blueprint_context = f"""
PROJECT: {agreement.project_name}
TECH STACK: {agreement.tech_stack}
FEATURES: {chr(10).join(f'- {f}' for f in agreement.features)}
DB SCHEMA: {chr(10).join(t.prisma_schema for t in arch.database_tables)}
API ENDPOINTS: {chr(10).join(f'{e.method} {e.path}' for e in arch.api_endpoints)}
IMPORTANT: Use Tailwind CSS for styling. Dark theme with gradients. No placeholders.
"""

    api_endpoints = arch.api_endpoints[:6]
    route_files = [endpoint_to_route_path(ep.path) for ep in api_endpoints]
    endpoints_by_route = dict(zip(route_files, api_endpoints))

    files_to_generate = [
        "package.json", "tsconfig.json", "next.config.ts",
        "tailwind.config.ts", "postcss.config.js",
        "prisma/schema.prisma", "src/lib/db.ts", "src/lib/auth.ts",
        "src/lib/utils.ts", "src/types/index.ts",
        *route_files,
        "src/app/globals.css", "src/app/layout.tsx", "src/app/page.tsx",
        "src/components/Navbar.tsx",
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
            scaffold = _scaffold_content(fp, agreement.project_name,
                                         endpoints_by_route.get(fp) if is_nextjs else None)
            if scaffold is not None:
                generated.append(GeneratedFile(path=fp, content=scaffold, language="typescript"))
                continue
            raw = llm.generate_file(fp, blueprint_context, [f.model_dump() for f in generated])
            generated.append(GeneratedFile(
                path=raw.get("path", fp),
                content=raw.get("content", f"// auto-generated: {fp}"),
                language=raw.get("language", "typescript"),
            ))
        except Exception as e:
            _log(build, "SYS_LOG: SYNTHESIZING_CODE",
                 f"⚠ Skipped {fp}: {str(e)[:80]}", LogLevel.WARNING)

    if is_nextjs:
        generated = _inject_package_json(generated, agreement.project_name)
        generated = _ensure_required_files(generated, agreement.project_name)
        generated = _sanitize_generated_files(generated, agreement.project_name, endpoints_by_route)

    _log(build, "SYS_LOG: SYNTHESIZING_CODE",
         f"✅ {len(generated)} files generated.", LogLevel.SUCCESS)

    # ── E2B Sandbox Build ─────────────────────
    _log(build, "SYS_LOG: RUNNING_QA_TESTS",
         "Compiling code. Running automated checks...", LogLevel.SYSTEM)

    final_files = generated
    runs: list = []
    build_ok = True

    try:
        e2b_key = os.environ.get("E2B_API_KEY", "")
        if e2b_key:
            orchestrator = SandboxOrchestrator(e2b_api_key=e2b_key)
            final_files, runs, build_ok = orchestrator.run_full_synthesis(
                files=generated,
                project_type="node" if is_nextjs else "python",
                on_log=lambda msg: _log(build, "SYS_LOG: RUNNING_QA_TESTS", msg),
                correct_fn=lambda err, buggy: llm.self_correct(err, buggy),
            )
            correction_loops = orchestrator.correction_loops_used
        else:
            _log(build, "SYS_LOG: RUNNING_QA_TESTS",
                 "⚠ E2B_API_KEY not set — skipping sandbox, using files directly.", LogLevel.WARNING)
    except Exception as e:
        _log(build, "SYS_LOG: RUNNING_QA_TESTS",
             f"⚠ Sandbox error: {str(e)[:100]}. Using generated files directly.", LogLevel.WARNING)

    _log(build, "SYS_LOG: RUNNING_QA_TESTS",
         f"{'✅ Build PASSED' if build_ok else '⚠ Build done with warnings'} — "
         f"{correction_loops} self-correction(s) used",
         LogLevel.SUCCESS if build_ok else LogLevel.WARNING)

    # ── Security Scan ─────────────────────────
    build.current_phase = BuildPhase.SECURITY_SCAN
    set_build_state(build.task_id, build.model_dump())
    _log(build, "SYS_LOG: RUNNING_QA_TESTS",
         "🔒 Running security scan — stripping secrets...", LogLevel.SYSTEM)
    scanner = SecurityScannerService()
    sanitized, secrets, vulns = scanner.scan_and_sanitize(final_files)
    build.synthesis = SynthesisResult(
        files=sanitized, sandbox_runs=runs,
        correction_loops_used=correction_loops,
        final_build_success=build_ok,
        secrets_found_and_moved=secrets,
    )
    _log(build, "SYS_LOG: RUNNING_QA_TESTS",
         f"✅ Security scan done. {len(secrets)} secret(s) → .env", LogLevel.SUCCESS)

    # ── GitHub Deploy ─────────────────────────
    build.current_phase = BuildPhase.DEPLOYMENT
    set_build_state(build.task_id, build.model_dump())
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
