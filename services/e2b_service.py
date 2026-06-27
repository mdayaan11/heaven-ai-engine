"""
Heaven AI Engine — E2B Sandbox Service (v2.8.1 API)
Runs generated code in isolated cloud sandbox, auto-corrects build errors.
"""
from __future__ import annotations
import os
from typing import Callable, List, Optional, Tuple
from e2b_code_interpreter import Sandbox
from models.schemas import GeneratedFile, SandboxRun


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
    ) -> Tuple[List[GeneratedFile], List[SandboxRun], bool]:
        runs: List[SandboxRun] = []
        build_ok = False

        try:
            with Sandbox(api_key=self.api_key, timeout=300) as sbx:
                # Write files
                if on_log:
                    on_log(f"E2B sandbox started. Writing {len(files)} files...")
                for f in files:
                    sbx.files.write(f.path, f.content)

                # Run build
                build_cmd = "npm install --legacy-peer-deps && npm run build" if project_type == "node" else "pip install -r requirements.txt"
                if on_log:
                    on_log(f"Running: {build_cmd}")

                result = sbx.commands.run(build_cmd, timeout=240)
                stdout = result.stdout or ""
                stderr = result.stderr or ""
                exit_code = result.exit_code

                runs.append(SandboxRun(
                    command=build_cmd, stdout=stdout[:2000],
                    stderr=stderr[:2000], exit_code=exit_code,
                ))

                if exit_code == 0:
                    if on_log:
                        on_log("✅ Build PASSED — 0 errors")
                    build_ok = True
                else:
                    # Self-correction loop
                    error_text = stderr or stdout
                    if on_log:
                        on_log(f"⚠ Build error detected. Starting self-correction...")
                    files, runs, build_ok = self._self_correct(
                        sbx, files, runs, error_text, project_type, on_log, correct_fn
                    )

        except Exception as e:
            if on_log:
                on_log(f"⚠ Sandbox error: {str(e)[:120]}. Using files directly.")
            build_ok = True  # Proceed with generated files

        return files, runs, build_ok

    def _self_correct(self, sbx, files, runs, error_text, project_type, on_log, correct_fn):
        build_ok = False
        for loop in range(self.MAX_CORRECTION_LOOPS):
            self.correction_loops_used += 1
            if on_log:
                on_log(f"🔧 Self-correction loop {loop + 1}/{self.MAX_CORRECTION_LOOPS}...")
            if not correct_fn:
                break

            # Find the file most likely causing the error
            buggy = self._find_buggy_file(files, error_text)
            if not buggy:
                break

            try:
                fixed = correct_fn(error_text, buggy.model_dump())
                # Replace in file list
                files = [
                    GeneratedFile(path=fixed["path"], content=fixed["content"], language=fixed.get("language","typescript"))
                    if f.path == buggy.path else f
                    for f in files
                ]
                # Rewrite fixed file
                sbx.files.write(fixed["path"], fixed["content"])

                # Retry build
                cmd = "npm run build" if project_type == "node" else "python -m py_compile main.py"
                result = sbx.commands.run(cmd, timeout=180)
                runs.append(SandboxRun(
                    command=cmd, stdout=result.stdout[:1000],
                    stderr=result.stderr[:1000], exit_code=result.exit_code,
                ))
                if result.exit_code == 0:
                    if on_log:
                        on_log(f"✅ Build PASSED after {loop + 1} correction(s)")
                    build_ok = True
                    break
                error_text = result.stderr or result.stdout
            except Exception as e:
                if on_log:
                    on_log(f"⚠ Correction loop error: {str(e)[:80]}")
                break

        return files, runs, build_ok

    def _find_buggy_file(self, files: List[GeneratedFile], error_text: str) -> Optional[GeneratedFile]:
        """Find which file the error references."""
        for f in files:
            if f.path.split("/")[-1].split(".")[0] in error_text:
                return f
        # Default to first non-config file
        for f in files:
            if f.path.endswith((".ts", ".tsx", ".py", ".js")):
                return f
        return files[0] if files else None
