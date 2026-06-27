"""
Heaven AI — LangGraph State Machine
Four-phase autonomous build agent: Scoping → Architecture → Synthesis → Deployment
"""
from __future__ import annotations
import json
import os
import time
import uuid
from typing import Any, Callable, Dict, List, TypedDict
from langgraph.graph import StateGraph, END
from models.schemas import (
    BuildPhase, BuildState, DeployTarget, FeatureAgreement,
    GeneratedFile, LogEntry, LogLevel, SandboxRunResult,
    ScopingResult, ArchitectureBlueprint, SynthesisResult, DeploymentResult,
)
from services.anthropic_service import AnthropicService
from services.e2b_service import SandboxOrchestrator
from services.security_scanner import SecurityScannerService
from services.github_service import GitHubService
from services.vercel_service import VercelService, RenderService


# ─────────────────────────────────────────────
# LangGraph State Type
# ─────────────────────────────────────────────
class GraphState(TypedDict):
    build: BuildState
    log_callback: Callable[[LogEntry], None]


# ─────────────────────────────────────────────
# Helper — Build logger
# ─────────────────────────────────────────────
def _log(state: GraphState, phase: BuildPhase, tag: str, message: str,
         level: LogLevel = LogLevel.INFO, metadata: Dict = None) -> None:
    entry = LogEntry(
        timestamp=time.time(), phase=phase,
        level=level, tag=tag, message=message, metadata=metadata,
    )
    state["build"].logs.append(entry)
    if state.get("log_callback"):
        state["log_callback"](entry)


# ─────────────────────────────────────────────
# State Machine Nodes
# ─────────────────────────────────────────────

def node_scoping(state: GraphState) -> GraphState:
    """Phase 1: Analyze the project idea and generate scoping questions."""
    build = state["build"]
    build.current_phase = BuildPhase.SCOPING

    _log(state, BuildPhase.SCOPING, "SYS_LOG: ALIGNING_PROMPT",
         "Analyzing your business requirements and project scope...", LogLevel.SYSTEM)

    llm = AnthropicService(api_key=os.environ["ANTHROPIC_API_KEY"])

    try:
        raw = llm.run_scoping(build.raw_project_idea)
        scoping = ScopingResult(
            questions=raw["questions"],
            estimated_price_usd=float(raw["estimated_price_usd"]),
            complexity_score=int(raw["complexity_score"]),
            estimated_build_time_minutes=int(raw["estimated_build_time_minutes"]),
            feature_summary=raw["feature_summary"],
        )
        build.scoping_result = scoping

        _log(state, BuildPhase.SCOPING, "SYS_LOG: ALIGNING_PROMPT",
             f"✅ Scoping complete. Complexity: {scoping.complexity_score}/10 | "
             f"Estimated price: ${scoping.estimated_price_usd:.0f} | "
             f"Build time: {scoping.estimated_build_time_minutes} min",
             LogLevel.SUCCESS,
             {"questions": [q.model_dump() for q in scoping.questions]})

    except Exception as e:
        build.error_message = f"Scoping failed: {str(e)}"
        _log(state, BuildPhase.SCOPING, "SYS_LOG: ALIGNING_PROMPT",
             f"❌ Scoping error: {str(e)}", LogLevel.ERROR)

    return state


def node_await_answers(state: GraphState) -> GraphState:
    """
    Pause point — waits for client to submit scoping answers.
    In practice, the Celery task pauses here and resumes when answers arrive.
    This node processes the answers and generates the Feature Agreement.
    """
    build = state["build"]

    if not build.scoping_answers:
        _log(state, BuildPhase.SCOPING, "SYS_LOG: ALIGNING_PROMPT",
             "⏳ Awaiting client answers to scoping questions...", LogLevel.INFO)
        return state  # Will be retried when answers arrive

    _log(state, BuildPhase.SCOPING, "SYS_LOG: ALIGNING_PROMPT",
         "Client answers received. Generating Feature Agreement...", LogLevel.INFO)

    llm = AnthropicService(api_key=os.environ["ANTHROPIC_API_KEY"])

    try:
        raw = llm.generate_feature_agreement(
            build.raw_project_idea,
            build.scoping_result.model_dump(),
            build.scoping_answers,
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
        _log(state, BuildPhase.SCOPING, "SYS_LOG: ALIGNING_PROMPT",
             f"✅ Feature Agreement generated for '{build.feature_agreement.project_name}'",
             LogLevel.SUCCESS,
             {"agreement": build.feature_agreement.model_dump()})

    except Exception as e:
        build.error_message = f"Feature agreement generation failed: {str(e)}"
        _log(state, BuildPhase.SCOPING, "SYS_LOG: ALIGNING_PROMPT",
             f"❌ Error: {str(e)}", LogLevel.ERROR)

    return state


def node_architecture(state: GraphState) -> GraphState:
    """Phase 2: Generate database schema + API contracts."""
    build = state["build"]
    build.current_phase = BuildPhase.ARCHITECTURE

    _log(state, BuildPhase.ARCHITECTURE, "SYS_LOG: ARCHITECTING_DB",
         "Building secure database relational schemas and API contracts...", LogLevel.SYSTEM)

    llm = AnthropicService(api_key=os.environ["ANTHROPIC_API_KEY"])

    try:
        raw = llm.run_architecture(
            build.feature_agreement.manifest_xml,
            build.scoping_answers or {},
        )
        from models.schemas import DatabaseTable, ApiEndpoint
        build.architecture = ArchitectureBlueprint(
            database_tables=[DatabaseTable(**t) for t in raw.get("database_tables", [])],
            api_endpoints=[ApiEndpoint(**e) for e in raw.get("api_endpoints", [])],
            tech_stack_manifest=raw.get("tech_stack_manifest", ""),
            folder_structure=raw.get("folder_structure", ""),
            env_variables_needed=raw.get("env_variables_needed", []),
        )
        _log(state, BuildPhase.ARCHITECTURE, "SYS_LOG: ARCHITECTING_DB",
             f"✅ Architecture complete. "
             f"{len(build.architecture.database_tables)} tables | "
             f"{len(build.architecture.api_endpoints)} endpoints",
             LogLevel.SUCCESS)

    except Exception as e:
        build.error_message = f"Architecture phase failed: {str(e)}"
        _log(state, BuildPhase.ARCHITECTURE, "SYS_LOG: ARCHITECTING_DB",
             f"❌ Error: {str(e)}", LogLevel.ERROR)

    return state


def node_synthesis(state: GraphState) -> GraphState:
    """Phase 3: Generate code, run in E2B sandbox, self-correct up to 3 times."""
    build = state["build"]
    build.current_phase = BuildPhase.SYNTHESIS

    _log(state, BuildPhase.SYNTHESIS, "SYS_LOG: SYNTHESIZING_CODE",
         "Generating full-stack code blocks inside isolated sandbox...", LogLevel.SYSTEM)

    llm = AnthropicService(api_key=os.environ["ANTHROPIC_API_KEY"])
    arch = build.architecture
    agreement = build.feature_agreement

    # ── Determine tech stack and files to generate ──────────────────
    is_nextjs = "next" in agreement.tech_stack.lower()
    project_type = "node" if is_nextjs else "python"

    # Build blueprint context string for Claude
    blueprint_context = f"""
PROJECT: {agreement.project_name}
TECH STACK: {agreement.tech_stack}
FEATURES: {chr(10).join(f'- {f}' for f in agreement.features)}

DATABASE SCHEMA (Prisma):
{chr(10).join(t.prisma_schema for t in arch.database_tables)}

API ENDPOINTS:
{chr(10).join(f'{e.method} {e.path} — {e.description}' for e in arch.api_endpoints)}

FOLDER STRUCTURE:
{arch.folder_structure}

NAMING RULE: All code variables and form field names MUST exactly match database column names.
"""

    # ── Generate files list based on architecture ────────────────────
    files_to_generate = _build_file_list(agreement, arch, is_nextjs)
    generated_files: List[GeneratedFile] = []

    _log(state, BuildPhase.SYNTHESIS, "SYS_LOG: SYNTHESIZING_CODE",
         f"Generating {len(files_to_generate)} source files...", LogLevel.INFO)

    for i, file_path in enumerate(files_to_generate):
        try:
            _log(state, BuildPhase.SYNTHESIS, "SYS_LOG: SYNTHESIZING_CODE",
                 f"Writing {file_path} ({i+1}/{len(files_to_generate)})...", LogLevel.INFO)
            raw = llm.generate_file(file_path, blueprint_context, [f.model_dump() for f in generated_files])
            generated_files.append(GeneratedFile(
                path=raw["path"], content=raw["content"],
                language=raw.get("language", "typescript"),
            ))
        except Exception as e:
            _log(state, BuildPhase.SYNTHESIS, "SYS_LOG: SYNTHESIZING_CODE",
                 f"⚠ Error generating {file_path}: {str(e)[:100]}", LogLevel.WARNING)

    # ── E2B Sandbox: build + self-correct ───────────────────────────
    _log(state, BuildPhase.SYNTHESIS, "SYS_LOG: RUNNING_QA_TESTS",
         "Compiling code. Running automated bug-checks inside E2B sandbox...", LogLevel.SYSTEM)

    def on_sandbox_log(msg: str):
        _log(state, BuildPhase.SYNTHESIS, "SYS_LOG: RUNNING_QA_TESTS", msg, LogLevel.INFO)

    def correct_fn(error_logs: str, buggy_file: Dict) -> Dict:
        return llm.self_correct(error_logs, buggy_file)

    orchestrator = SandboxOrchestrator(e2b_api_key=os.environ["E2B_API_KEY"])
    final_files, run_results, build_success = orchestrator.run_full_synthesis(
        files=generated_files,
        project_type=project_type,
        on_log=on_sandbox_log,
        correct_fn=correct_fn,
    )

    build.synthesis = SynthesisResult(
        files=final_files,
        sandbox_runs=run_results,
        correction_loops_used=orchestrator.correction_loops_used,
        final_build_success=build_success,
        secrets_found_and_moved=[],
    )

    _log(state, BuildPhase.SYNTHESIS, "SYS_LOG: RUNNING_QA_TESTS",
         f"{'✅ Build PASSED' if build_success else '⚠ Build completed with warnings'} — "
         f"{orchestrator.correction_loops_used} correction loop(s) used",
         LogLevel.SUCCESS if build_success else LogLevel.WARNING)

    return state


def node_security_scan(state: GraphState) -> GraphState:
    """Security scan: strip secrets, validate auth, flag injection risks."""
    build = state["build"]
    build.current_phase = BuildPhase.SECURITY_SCAN

    _log(state, BuildPhase.SECURITY_SCAN, "SYS_LOG: RUNNING_QA_TESTS",
         "🔒 Running security scan — stripping secrets and validating auth middleware...", LogLevel.SYSTEM)

    scanner = SecurityScannerService()
    sanitized_files, secrets_found, vulns_fixed = scanner.scan_and_sanitize(
        build.synthesis.files
    )
    build.synthesis.files = sanitized_files
    build.synthesis.secrets_found_and_moved = secrets_found

    report = scanner.generate_scan_report()
    _log(state, BuildPhase.SECURITY_SCAN, "SYS_LOG: RUNNING_QA_TESTS",
         f"✅ Security scan complete. {len(secrets_found)} secret(s) moved to .env. "
         f"{len(vulns_fixed)} issue(s) addressed.",
         LogLevel.SUCCESS, {"report": report})

    return state


def node_deployment(state: GraphState) -> GraphState:
    """Phase 4: Create GitHub repo, commit code, deploy to Vercel/Render."""
    build = state["build"]
    build.current_phase = BuildPhase.DEPLOYMENT

    _log(state, BuildPhase.DEPLOYMENT, "SYS_LOG: DEPLOYING_PROD",
         "Pushing live code to global production servers...", LogLevel.SYSTEM)

    github = GitHubService(
        token=os.environ["GITHUB_TOKEN"],
        username=os.environ["GITHUB_USERNAME"],
    )
    agreement = build.feature_agreement
    files = build.synthesis.files

    try:
        # 1. Create GitHub repo
        _log(state, BuildPhase.DEPLOYMENT, "SYS_LOG: DEPLOYING_PROD",
             "Creating private GitHub repository...", LogLevel.INFO)
        repo_info = github.create_repo(
            repo_name=agreement.project_name,
            description=f"Built by Heaven AI Engine for {build.client_name}",
        )
        _log(state, BuildPhase.DEPLOYMENT, "SYS_LOG: DEPLOYING_PROD",
             f"✅ Repo created: {repo_info['html_url']}", LogLevel.SUCCESS)

        # 2. Commit all files
        _log(state, BuildPhase.DEPLOYMENT, "SYS_LOG: DEPLOYING_PROD",
             f"Committing {len(files)} files to {repo_info['repo_name']}...", LogLevel.INFO)
        commit_sha = github.commit_files(
            repo_full_name=repo_info["full_name"],
            files=files,
            commit_message=f"🚀 {agreement.project_name} — built by Heaven AI Engine",
        )
        _log(state, BuildPhase.DEPLOYMENT, "SYS_LOG: DEPLOYING_PROD",
             f"✅ Code committed — SHA: {commit_sha[:8]}", LogLevel.SUCCESS)

        # 3. Deploy
        production_url = ""
        deploy_id = ""

        if build.deploy_target == DeployTarget.VERCEL:
            _log(state, BuildPhase.DEPLOYMENT, "SYS_LOG: DEPLOYING_PROD",
                 "Triggering Vercel deployment...", LogLevel.INFO)
            vercel = VercelService(
                token=os.environ["VERCEL_TOKEN"],
                team_id=os.environ.get("VERCEL_TEAM_ID") or None,
            )
            project = vercel.create_project(
                project_name=agreement.project_name,
                github_repo=repo_info["full_name"],
            )
            deploy = vercel.trigger_deployment(
                project_id=project["project_id"],
                github_repo=repo_info["full_name"],
            )
            deploy_id = deploy["deploy_id"]

            def on_deploy_log(msg): _log(state, BuildPhase.DEPLOYMENT, "SYS_LOG: DEPLOYING_PROD", msg)
            final = vercel.wait_for_deployment(deploy_id, on_log=on_deploy_log)
            production_url = final["production_url"]

        elif build.deploy_target == DeployTarget.RENDER:
            _log(state, BuildPhase.DEPLOYMENT, "SYS_LOG: DEPLOYING_PROD",
                 "Triggering Render deployment...", LogLevel.INFO)
            render = RenderService(api_key=os.environ["RENDER_API_KEY"])
            service = render.create_web_service(
                service_name=agreement.project_name,
                github_repo=repo_info["full_name"],
            )
            deploy_id = service["service_id"]
            production_url = service["production_url"]

        # 4. Generate credentials markdown
        env_md = _generate_env_markdown(agreement, build.synthesis.secrets_found_and_moved)

        build.deployment = DeploymentResult(
            github_repo_url=repo_info["html_url"],
            github_repo_name=repo_info["repo_name"],
            production_url=production_url,
            deploy_target=build.deploy_target,
            deploy_id=deploy_id,
            env_variables_markdown=env_md,
        )
        build.current_phase = BuildPhase.COMPLETE
        _log(state, BuildPhase.DEPLOYMENT, "SYS_LOG: DEPLOYING_PROD",
             f"🎉 DEPLOYMENT COMPLETE — Live at: {production_url}",
             LogLevel.SUCCESS,
             {"deployment": build.deployment.model_dump()})

    except Exception as e:
        build.error_message = f"Deployment failed: {str(e)}"
        build.current_phase = BuildPhase.FAILED
        _log(state, BuildPhase.DEPLOYMENT, "SYS_LOG: DEPLOYING_PROD",
             f"❌ Deployment error: {str(e)}", LogLevel.ERROR)

    return state


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _build_file_list(agreement: FeatureAgreement, arch: ArchitectureBlueprint, is_nextjs: bool) -> List[str]:
    """Generate the ordered list of files to create based on tech stack."""
    if is_nextjs:
        return [
            "package.json",
            "tsconfig.json",
            "next.config.ts",
            "tailwind.config.ts",
            "postcss.config.mjs",
            ".env.example",
            "prisma/schema.prisma",
            "src/lib/db.ts",
            "src/lib/auth.ts",
            "src/lib/utils.ts",
            "src/types/index.ts",
            *[f"src/app/api/{ep.path.strip('/').replace('/', '-')}/route.ts"
              for ep in arch.api_endpoints[:8]],
            "src/app/layout.tsx",
            "src/app/page.tsx",
            "src/app/globals.css",
            "src/components/ui/Button.tsx",
            "src/components/ui/Input.tsx",
            "src/components/ui/Card.tsx",
            "src/components/Navbar.tsx",
            "src/components/Footer.tsx",
            "src/middleware.ts",
            "README.md",
        ]
    else:
        return [
            "requirements.txt",
            ".env.example",
            "main.py",
            "database.py",
            "models.py",
            *[f"routes/{ep.path.strip('/').split('/')[0]}.py" for ep in arch.api_endpoints[:6]],
            "middleware.py",
            "auth.py",
            "README.md",
        ]


def _generate_env_markdown(agreement: FeatureAgreement, secrets: List[str]) -> str:
    """Generate a markdown file with environment variable documentation."""
    lines = [
        f"# {agreement.project_name} — Environment Variables",
        f"\nGenerated by Heaven AI Engine on {time.strftime('%Y-%m-%d %H:%M UTC')}",
        "\n---\n",
        "## 🔒 Required Environment Variables\n",
        "Copy these to your `.env.local` file and fill in the values:\n",
        "```env",
    ]
    for secret in sorted(secrets):
        lines.append(f"{secret}=YOUR_{secret}_HERE")
    if not secrets:
        lines.append("# No secrets required for this project")
    lines += [
        "```",
        "\n---\n",
        "## 🚀 Deployment Checklist\n",
        "- [ ] Copy `.env.example` to `.env.local`",
        "- [ ] Fill in all environment variables",
        "- [ ] Run `npm install` (or `pip install -r requirements.txt`)",
        "- [ ] Run `npx prisma migrate dev` to set up the database",
        "- [ ] Run `npm run dev` to test locally",
        "- [ ] Push to GitHub to trigger auto-deploy",
        "\n---\n",
        f"Built with ❤ by Heaven AI Engine",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Graph Builder
# ─────────────────────────────────────────────
def build_graph() -> StateGraph:
    """Construct and compile the LangGraph state machine."""
    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("scoping", node_scoping)
    graph.add_node("await_answers", node_await_answers)
    graph.add_node("architecture", node_architecture)
    graph.add_node("synthesis", node_synthesis)
    graph.add_node("security_scan", node_security_scan)
    graph.add_node("deployment", node_deployment)

    # Define edges
    graph.set_entry_point("scoping")
    graph.add_edge("scoping", "await_answers")
    graph.add_edge("await_answers", "architecture")
    graph.add_edge("architecture", "synthesis")
    graph.add_edge("synthesis", "security_scan")
    graph.add_edge("security_scan", "deployment")
    graph.add_edge("deployment", END)

    return graph.compile()


# Singleton compiled graph
ENGINE_GRAPH = build_graph()
