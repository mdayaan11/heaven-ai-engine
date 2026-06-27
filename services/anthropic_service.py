"""
Heaven AI — Anthropic Claude 3.5 Sonnet Service
Wraps all LLM calls with retry logic, streaming support, and structured output parsing.
"""
from __future__ import annotations
import json
import re
from typing import Any, AsyncIterator, Dict, Optional
import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential
from models.schemas import BuildState, LogEntry, BuildPhase, LogLevel
import time


# ─────────────────────────────────────────────
# System Prompts per Phase
# ─────────────────────────────────────────────
SCOPING_SYSTEM_PROMPT = """You are an elite Product Manager and Technical Analyst at Heaven AI, 
a world-class software studio. Your job is to analyze a raw project idea from a non-technical client 
and produce a precise scoping analysis.

RULES:
- Generate exactly 2-3 targeted, high-impact clarifying questions that remove ALL technical ambiguity
- Calculate a realistic price in USD based on complexity (min $50, max $5000)
- Assign a complexity score 1-10 (1=landing page, 5=SaaS MVP, 10=full enterprise platform)
- Estimate delivery time in minutes of AI build time (not wall clock time)
- Write a crisp feature summary in plain English

ALWAYS respond in valid JSON matching this exact schema:
{
  "questions": [
    {"question_id": "q1", "question_text": "...", "options": ["Option A", "Option B", "Option C"], "required": true}
  ],
  "estimated_price_usd": 250.0,
  "complexity_score": 4,
  "estimated_build_time_minutes": 8,
  "feature_summary": "..."
}"""

ARCHITECTURE_SYSTEM_PROMPT = """You are a Principal Software Architect at Heaven AI.
Given a confirmed feature agreement, generate a complete technical blueprint.

RULES:
- Write full Prisma schema blocks (not pseudocode — actual valid Prisma syntax)
- Write full SQL CREATE TABLE statements
- Define every API endpoint with exact request/response JSON shapes
- NAMING SYNCHRONICITY: every column name in the DB schema MUST exactly match 
  the JSON field names in API request/response bodies
- Generate a complete folder structure tree
- List every environment variable the project will need
- Output a valid XML project manifest

ALWAYS respond in valid JSON matching the ArchitectureBlueprint schema."""

SYNTHESIS_SYSTEM_PROMPT = """You are a Senior Lead Full-Stack Developer at Heaven AI.
You write production-quality code with zero placeholders, zero TODOs, zero incomplete functions.

CRITICAL RULES:
1. Every function body must be fully implemented — no pass, no TODO, no placeholder comments
2. Every API route must have full error handling with proper HTTP status codes
3. Database column names in code MUST match the Prisma schema exactly
4. Never hardcode secrets — always use process.env.VARIABLE_NAME
5. Include proper TypeScript types for every variable, parameter, and return value
6. Every file must be syntactically valid and production-ready

Generate one file at a time in this JSON format:
{"path": "src/app/page.tsx", "content": "..full file content..", "language": "typescript"}"""

SELF_CORRECTION_SYSTEM_PROMPT = """You are a Senior QA Engineer and Debugger at Heaven AI.
You have received build error logs from a sandbox. Your job is to fix the code.

RULES:
1. Analyze the exact error — do NOT guess; read the stack trace carefully
2. Identify the exact file and line causing the error
3. Rewrite ONLY the file(s) that need fixing — do not change working files
4. Fix ALL errors in one pass — do not introduce new errors
5. Output the corrected file in the same JSON format as synthesis output

Build errors to fix:
"""

SECURITY_SCAN_SYSTEM_PROMPT = """You are a Security Engineer at Heaven AI.
Scan the provided codebase for security vulnerabilities.

CHECK FOR:
1. Hardcoded API keys, tokens, passwords, secrets
2. Missing authentication middleware on protected routes
3. SQL injection vulnerabilities (raw string queries)
4. Exposed sensitive data in API responses
5. Missing input validation

For each secret found:
- Remove it from the code
- Replace with process.env.VARIABLE_NAME
- Add the variable name to the .env.example list

Output format:
{
  "secrets_found": ["list of env var names that were extracted"],
  "vulnerabilities_fixed": ["description of fixes"],
  "corrected_files": [{"path": "...", "content": "...", "language": "..."}]
}"""

DEPLOYMENT_SYSTEM_PROMPT = """You are a DevOps Engineer at Heaven AI.
Generate deployment configuration files for the project.
Output a package.json vercel.json or render.yaml as needed."""


# ─────────────────────────────────────────────
# Service Class
# ─────────────────────────────────────────────
class AnthropicService:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.async_client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = "claude-3-5-sonnet-20241022"
        self.max_tokens = 8096

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Synchronous completion — used inside Celery workers."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def complete_json(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """
        Complete and parse JSON response.
        Strips markdown code fences if present.
        """
        raw = self.complete(
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=temperature,
        )
        # Strip markdown fences
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
        return json.loads(cleaned)

    async def stream_complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
    ) -> AsyncIterator[str]:
        """Async streaming completion — for real-time feedback."""
        async with self.async_client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    # ─── Phase-Specific Helpers ──────────────────
    def run_scoping(self, project_idea: str) -> Dict[str, Any]:
        prompt = f"""Analyze this project idea and produce a scoping result:

PROJECT IDEA: {project_idea}

Generate the JSON scoping analysis now."""
        return self.complete_json(SCOPING_SYSTEM_PROMPT, prompt)

    def run_architecture(self, feature_agreement_xml: str, answers: Dict[str, str]) -> Dict[str, Any]:
        prompt = f"""Generate the complete technical architecture blueprint for this confirmed project:

FEATURE AGREEMENT:
{feature_agreement_xml}

CLIENT ANSWERS:
{json.dumps(answers, indent=2)}

Generate the full ArchitectureBlueprint JSON now."""
        return self.complete_json(ARCHITECTURE_SYSTEM_PROMPT, prompt, temperature=0.05)

    def generate_file(self, file_path: str, blueprint_context: str, existing_files: list) -> Dict[str, Any]:
        existing_summary = "\n".join([f"- {f['path']}" for f in existing_files])
        prompt = f"""Generate the complete, production-ready code for this file:

FILE TO GENERATE: {file_path}

PROJECT BLUEPRINT:
{blueprint_context}

ALREADY GENERATED FILES (do not duplicate their exports/types):
{existing_summary}

Generate the complete file content now as JSON:
{{"path": "{file_path}", "content": "...", "language": "..."}}"""
        return self.complete_json(SYNTHESIS_SYSTEM_PROMPT, prompt, temperature=0.05)

    def self_correct(self, error_logs: str, buggy_file: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""Fix this file that failed to compile:

FILE: {buggy_file['path']}
CURRENT CONTENT:
{buggy_file['content']}

BUILD ERROR:
{error_logs}

Output the corrected file as JSON: {{"path": "...", "content": "...", "language": "..."}}"""
        return self.complete_json(
            SELF_CORRECTION_SYSTEM_PROMPT + error_logs, prompt, temperature=0.05
        )

    def security_scan(self, all_files: list) -> Dict[str, Any]:
        files_str = "\n\n".join(
            [f"=== {f['path']} ===\n{f['content']}" for f in all_files]
        )
        prompt = f"""Perform a full security scan on this codebase:

{files_str}

Output the security scan result JSON now."""
        return self.complete_json(SECURITY_SCAN_SYSTEM_PROMPT, prompt, temperature=0.05)

    def generate_feature_agreement(
        self,
        project_idea: str,
        scoping_result: Dict[str, Any],
        answers: Dict[str, str],
    ) -> Dict[str, Any]:
        prompt = f"""Generate a Feature Agreement for the client to confirm before building starts.

PROJECT IDEA: {project_idea}

SCOPING ANALYSIS: {json.dumps(scoping_result, indent=2)}

CLIENT ANSWERS: {json.dumps(answers, indent=2)}

Output JSON with fields:
- project_name (string)
- tech_stack (string)  
- features (list of strings)
- out_of_scope (list of strings)
- price_usd (float)
- delivery_estimate (string)
- manifest_xml (full XML manifest string)"""
        return self.complete_json(SCOPING_SYSTEM_PROMPT, prompt, temperature=0.1)
