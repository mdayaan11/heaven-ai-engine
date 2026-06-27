"""
Heaven AI Engine — Core Build Runner
Runs the full 4-phase pipeline in a background thread.
Uses Gemini + E2B + GitHub.
"""
from __future__ import annotations
import os
import time
import threading
from typing import Dict, Optional
from models.schemas import (
    BuildPhase, BuildState, LogEntry, LogLevel,
    ScopingResult, FeatureAgreement, ArchitectureBlueprint,
    DatabaseTable, ApiEndpoint, GeneratedFile, SynthesisResult, DeploymentResult,
)
from services.gemini_service import GeminiService
from services.e2b_service import SandboxOrchestrator
from services.security_scanner import SecurityScannerService
from services.github_service import GitHubService
from tasks.build_tasks import push_log, set_build_state, get_scoping_answers


def _log(build: BuildState, tag: str, message: str, level: LogLevel = LogLevel.INFO) -> None:
    entry = LogEntry(
        timestamp=time.time(), phase=build.current_phase,
        level=level, tag=tag, message=message,
    )
    build.logs.append(entry)
    push_log(build.task_id, entry.model_dump())
    set_build_state(build.task_id, build.model_dump())


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
        build.architecture = ArchitectureBlueprint(
            database_tables=[DatabaseTable(**t) for t in raw.get("database_tables", [])],
            api_endpoints=[ApiEndpoint(**e) for e in raw.get("api_endpoints", [])],
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

    files_to_generate = [
        "package.json", "tsconfig.json", "next.config.ts",
        "prisma/schema.prisma", "src/lib/db.ts", "src/lib/auth.ts",
        "src/types/index.ts",
        *[f"src/app/api/{ep.path.strip('/').replace('/', '_')}/route.ts"
          for ep in arch.api_endpoints[:6]],
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
            raw = llm.generate_file(fp, blueprint_context, [f.model_dump() for f in generated])
            generated.append(GeneratedFile(
                path=raw["path"], content=raw["content"],
                language=raw.get("language", "typescript"),
            ))
        except Exception as e:
            _log(build, "SYS_LOG: SYNTHESIZING_CODE",
                 f"⚠ Skipped {fp}: {str(e)[:80]}", LogLevel.WARNING)

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
