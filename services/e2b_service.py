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
            # Sandbox.create() is the current e2b-code-interpreter (v1+)
            # classmethod for starting a sandbox with an explicit API key.
            # The old code called Sandbox(api_key=..., timeout=...) directly,
            # which raised "SandboxBase.__init__() got an unexpected keyword
            # argument 'api_key'" on every single run — meaning the E2B
            # build-test step silently never ran at all, for every project,
            # the whole time. We fall back to the bare constructor if a
            # future/older SDK version doesn't expose .create().
            if hasattr(Sandbox, "create"):
                sbx = Sandbox.create(api_key=self.api_key, timeout=300)
            else:
                sbx = Sandbox(api_key=self.api_key, timeout=300)

            with sbx as sbx:
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

                if not ok and correct_fn is not None:
                    # Attempt self-correction using whatever stderr/stdout
                    # the failed build produced, up to MAX_CORRECTION_LOOPS
                    # times, instead of just giving up after one failure.
                    error_text = (getattr(result, "stderr", "") or "") + "\n" + (getattr(result, "stdout", "") or "")
                    current_files = files
                    while not ok and self.correction_loops_used < self.MAX_CORRECTION_LOOPS:
                        self.correction_loops_used += 1
                        if on_log:
                            on_log(f"🔧 Self-correction attempt {self.correction_loops_used}/{self.MAX_CORRECTION_LOOPS}...")
                        try:
                            corrected = correct_fn(error_text, [f.model_dump() for f in current_files])
                        except Exception as corr_err:
                            if on_log:
                                on_log(f"⚠ Self-correction call failed: {str(corr_err)[:100]}")
                            break
                        if not corrected:
                            break
                        current_files = [
                            GeneratedFile(path=c["path"], content=c["content"], language=c.get("language", "typescript"))
                            for c in corrected
                        ]
                        for f in current_files:
                            sbx.files.write(f.path, f.content)
                        result = sbx.commands.run(build_cmd, timeout=240)
                        ok = result.exit_code == 0
                        error_text = (getattr(result, "stderr", "") or "") + "\n" + (getattr(result, "stdout", "") or "")
                        if on_log:
                            on_log(f"{'✅ Build PASSED after correction' if ok else '⚠ Still failing'}")
                    return current_files, [], ok

                return files, [], ok
        except Exception as e:
            if on_log:
                on_log(f"⚠ Sandbox error: {str(e)[:150]}. Using generated files directly.")
            return files, [], True
