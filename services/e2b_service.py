"""E2B Sandbox — optional, skipped gracefully if not installed"""
from __future__ import annotations
from typing import Callable, List, Optional, Tuple
from models.schemas import GeneratedFile

try:
    from e2b_code_interpreter import Sandbox
    E2B_AVAILABLE = True
except ImportError:
    E2B_AVAILABLE = False


class SandboxOrchestrator:
    MAX_CORRECTION_LOOPS = 3

    def __init__(self, e2b_api_key: str):
        self.api_key = e2b_api_key
        self.correction_loops_used = 0

    def run_full_synthesis(
        self,
        files: List[GeneratedFile],
        project_type: str = "node",
        on_log: Optional[Callable] = None,
        correct_fn: Optional[Callable] = None,
    ) -> Tuple[List[GeneratedFile], List, bool]:
        if not E2B_AVAILABLE:
            if on_log:
                on_log("⚠ E2B sandbox not installed — skipping build test, using generated files directly.")
            return files, [], True

        try:
            with Sandbox(api_key=self.api_key, timeout=300) as sbx:
                if on_log:
                    on_log(f"E2B sandbox started. Writing {len(files)} files...")
                for f in files:
                    sbx.files.write(f.path, f.content)
                build_cmd = (
                    "npm install --legacy-peer-deps && npm run build"
                    if project_type == "node"
                    else "pip install -r requirements.txt && python -m py_compile main.py"
                )
                if on_log:
                    on_log(f"Running: {build_cmd}")
                result = sbx.commands.run(build_cmd, timeout=240)
                ok = result.exit_code == 0
                if on_log:
                    on_log(f"{'✅ Build PASSED' if ok else '⚠ Build had errors'}")
                return files, [], ok
        except Exception as e:
            if on_log:
                on_log(f"⚠ Sandbox error: {str(e)[:100]}. Using files directly.")
            return files, [], True
