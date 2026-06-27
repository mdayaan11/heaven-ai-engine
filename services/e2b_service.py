"""
Heaven AI — E2B Sandbox Orchestration Service
Manages isolated cloud sandboxes for safe code execution, build testing, and self-correction.
"""
from __future__ import annotations
import os
import json
import time
from typing import Callable, Dict, List, Optional, Tuple
from e2b_code_interpreter import CodeInterpreter
from models.schemas import GeneratedFile, SandboxRunResult


class E2BSandboxService:
    """
    Manages an E2B cloud sandbox lifecycle for a single build session.
    
    Flow:
        1. open()  — spin up sandbox
        2. write_files() — inject generated files
        3. run_install() — npm install / pip install
        4. run_build()   — npm run build / python -m py_compile
        5. capture errors if any
        6. close()  — terminate sandbox
    """

    def __init__(self, api_key: str, timeout_seconds: int = 300):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self._sandbox: Optional[CodeInterpreter] = None
        self.run_log: List[SandboxRunResult] = []

    def open(self, template: str = "node") -> None:
        """
        Open a new E2B sandbox.
        template: 'node' for Next.js/TypeScript, 'python' for FastAPI
        """
        self._sandbox = CodeInterpreter(
            template=template,
            api_key=self.api_key,
            timeout=self.timeout_seconds,
        )

    def close(self) -> None:
        """Terminate the sandbox and release resources."""
        if self._sandbox:
            try:
                self._sandbox.close()
            except Exception:
                pass
            self._sandbox = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    def _exec(self, command: str, cwd: str = "/home/user/project") -> SandboxRunResult:
        """Execute a shell command in the sandbox and capture output."""
        assert self._sandbox, "Sandbox not open. Call open() first."
        result = self._sandbox.notebook.exec_cell(
            f"import subprocess, sys\n"
            f"r = subprocess.run({repr(command)}, shell=True, cwd={repr(cwd)}, "
            f"capture_output=True, text=True, timeout=240)\n"
            f"print('STDOUT:', r.stdout)\n"
            f"print('STDERR:', r.stderr)\n"
            f"print('EXIT:', r.returncode)\n"
        )
        stdout = ""
        stderr = ""
        exit_code = 0
        for line in result.logs.stdout:
            if line.startswith("STDOUT: "):
                stdout += line[8:]
            elif line.startswith("STDERR: "):
                stderr += line[8:]
            elif line.startswith("EXIT: "):
                try:
                    exit_code = int(line[6:].strip())
                except ValueError:
                    exit_code = 1
        run_result = SandboxRunResult(
            command=command,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            success=(exit_code == 0),
        )
        self.run_log.append(run_result)
        return run_result

    def write_files(self, files: List[GeneratedFile], base_path: str = "/home/user/project") -> None:
        """Write all generated files into the sandbox filesystem."""
        assert self._sandbox, "Sandbox not open."
        # Create project directory
        self._exec(f"mkdir -p {base_path}")
        for file in files:
            full_path = f"{base_path}/{file.path}"
            # Create parent directories
            parent = "/".join(full_path.split("/")[:-1])
            if parent:
                self._exec(f"mkdir -p {parent}")
            # Escape content and write
            escaped = file.content.replace("'", "'\"'\"'")
            self._exec(f"cat > '{full_path}' << 'HEAVENEOF'\n{file.content}\nHEAVENEOF")

    def run_install(self, project_type: str = "node") -> SandboxRunResult:
        """Install dependencies."""
        if project_type == "node":
            return self._exec("npm install --legacy-peer-deps 2>&1")
        elif project_type == "python":
            return self._exec("pip install -r requirements.txt 2>&1")
        else:
            raise ValueError(f"Unknown project type: {project_type}")

    def run_build(self, project_type: str = "node") -> SandboxRunResult:
        """Run the build/compile check."""
        if project_type == "node":
            return self._exec("npm run build 2>&1")
        elif project_type == "python":
            return self._exec(
                "python -m py_compile $(find . -name '*.py' | head -20) 2>&1 "
                "&& python -c 'import main' 2>&1"
            )
        else:
            raise ValueError(f"Unknown project type: {project_type}")

    def run_type_check(self) -> SandboxRunResult:
        """TypeScript type check without full build."""
        return self._exec("npx tsc --noEmit 2>&1")

    def get_build_errors(self, result: SandboxRunResult) -> str:
        """Extract and format build errors from a failed run result."""
        if result.success:
            return ""
        errors = []
        if result.stderr.strip():
            errors.append(f"STDERR:\n{result.stderr.strip()}")
        if result.stdout.strip():
            # Filter stdout for error lines
            error_lines = [
                line for line in result.stdout.split("\n")
                if any(kw in line.lower() for kw in ["error", "failed", "cannot", "unexpected", "type"])
            ]
            if error_lines:
                errors.append(f"BUILD OUTPUT ERRORS:\n" + "\n".join(error_lines[:40]))
        return "\n\n".join(errors) or f"Build failed with exit code {result.exit_code}"

    def read_file(self, path: str) -> str:
        """Read a file from the sandbox."""
        result = self._exec(f"cat '{path}' 2>&1")
        return result.stdout

    def list_files(self, path: str = "/home/user/project") -> List[str]:
        """List all files in the project."""
        result = self._exec(f"find {path} -type f | grep -v node_modules | grep -v .git | grep -v .next 2>&1")
        return [line.strip() for line in result.stdout.split("\n") if line.strip()]

    def get_package_json(self) -> Dict:
        """Read and parse package.json."""
        content = self.read_file("/home/user/project/package.json")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}


# ─────────────────────────────────────────────
# Orchestrator — Self-Correction Loop
# ─────────────────────────────────────────────
class SandboxOrchestrator:
    """
    High-level orchestrator that manages the full synthesis + self-correction cycle.
    """
    MAX_CORRECTION_LOOPS = 3

    def __init__(self, e2b_api_key: str):
        self.service = E2BSandboxService(api_key=e2b_api_key)
        self.correction_loops_used = 0

    def run_full_synthesis(
        self,
        files: List[GeneratedFile],
        project_type: str,
        on_log: Callable[[str], None],
        correct_fn: Callable[[str, Dict], Dict],
    ) -> Tuple[List[GeneratedFile], List[SandboxRunResult], bool]:
        """
        Execute the full build cycle with autonomous self-correction.

        Args:
            files: Generated source files
            project_type: 'node' or 'python'
            on_log: Callback to emit log messages
            correct_fn: Function(error_logs, buggy_file) → corrected_file (calls Claude)

        Returns:
            (final_files, all_run_results, build_success)
        """
        files_dict = {f.path: f for f in files}
        run_results: List[SandboxRunResult] = []
        build_success = False

        try:
            self.service.open(template="node" if project_type == "node" else "base")
            on_log("[SYS_LOG: RUNNING_QA_TESTS] Injecting code into isolated E2B sandbox...")
            self.service.write_files(list(files_dict.values()))

            on_log("[SYS_LOG: RUNNING_QA_TESTS] Installing dependencies...")
            install_result = self.service.run_install(project_type)
            run_results.append(install_result)

            if not install_result.success:
                on_log(f"[SYS_LOG: RUNNING_QA_TESTS] ⚠ Dependency install issues detected. Continuing...")

            for attempt in range(self.MAX_CORRECTION_LOOPS + 1):
                on_log(f"[SYS_LOG: RUNNING_QA_TESTS] Compiling code — attempt {attempt + 1}/{self.MAX_CORRECTION_LOOPS + 1}...")
                build_result = self.service.run_build(project_type)
                run_results.append(build_result)

                if build_result.success:
                    on_log("[SYS_LOG: RUNNING_QA_TESTS] ✅ Build PASSED — zero compilation errors detected.")
                    build_success = True
                    break

                if attempt >= self.MAX_CORRECTION_LOOPS:
                    on_log(f"[SYS_LOG: RUNNING_QA_TESTS] ❌ Max correction loops ({self.MAX_CORRECTION_LOOPS}) reached.")
                    break

                # ── Self-correction loop ──────────────
                error_logs = self.service.get_build_errors(build_result)
                on_log(f"[SYS_LOG: RUNNING_QA_TESTS] 🔧 Build error detected. Entering self-correction loop {attempt + 1}...")
                on_log(f"[SYS_LOG: RUNNING_QA_TESTS] Error: {error_logs[:200]}...")

                # Identify likely buggy file from error logs
                buggy_path = self._identify_buggy_file(error_logs, list(files_dict.keys()))
                if not buggy_path:
                    on_log("[SYS_LOG: RUNNING_QA_TESTS] Could not identify buggy file. Skipping loop.")
                    break

                buggy_file = files_dict[buggy_path]
                on_log(f"[SYS_LOG: RUNNING_QA_TESTS] 🔍 Fixing: {buggy_path}")

                corrected = correct_fn(error_logs, {"path": buggy_file.path, "content": buggy_file.content})
                corrected_file = GeneratedFile(
                    path=corrected["path"],
                    content=corrected["content"],
                    language=corrected.get("language", buggy_file.language),
                )
                files_dict[corrected_file.path] = corrected_file
                # Overwrite in sandbox
                self.service.write_files([corrected_file])
                self.correction_loops_used = attempt + 1

        finally:
            self.service.close()

        return list(files_dict.values()), run_results, build_success

    @staticmethod
    def _identify_buggy_file(error_logs: str, file_paths: List[str]) -> Optional[str]:
        """Heuristically find which file caused the build error."""
        for path in file_paths:
            # Normalize path for matching
            filename = path.split("/")[-1].replace(".tsx", "").replace(".ts", "").replace(".py", "")
            if filename in error_logs or path in error_logs:
                return path
        # Fallback: return first non-config file
        for path in file_paths:
            if not any(skip in path for skip in ["package.json", "tsconfig", ".env", "prisma"]):
                return path
        return None
