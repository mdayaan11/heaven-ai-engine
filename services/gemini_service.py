"""
Heaven AI Engine — Google Gemini 2.5 Pro Service
Replaces Anthropic Claude. Free tier: 1500 requests/day.
"""
from __future__ import annotations
import json
import re
import time
from typing import Any, Dict, Optional
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

# ─────────────────────────────────────────────
# System Prompts
# ─────────────────────────────────────────────
SCOPING_PROMPT = """You are an elite Product Manager at Heaven AI, a world-class software studio.
Analyze a raw project idea from a non-technical client and produce a precise scoping analysis.

RULES:
- Generate exactly 2-3 targeted clarifying questions that remove ALL technical ambiguity
- Calculate a realistic price in USD (min $50, max $5000) based on complexity
- Assign complexity score 1-10 (1=landing page, 5=SaaS MVP, 10=enterprise platform)
- Estimate build time in minutes (AI processing time)
- Write a crisp feature summary in plain English

ALWAYS respond in valid JSON ONLY — no markdown, no explanation, just the JSON:
{
  "questions": [
    {"question_id": "q1", "question_text": "...", "options": ["A", "B", "C"], "required": true}
  ],
  "estimated_price_usd": 250.0,
  "complexity_score": 4,
  "estimated_build_time_minutes": 8,
  "feature_summary": "..."
}"""

ARCHITECTURE_PROMPT = """You are a Principal Software Architect at Heaven AI.
Generate a complete technical blueprint for the confirmed project.

RULES:
- Write full Prisma schema blocks (valid Prisma syntax only)
- Write full SQL CREATE TABLE statements
- Define every API endpoint with exact JSON request/response shapes
- CRITICAL: column names in DB schema MUST exactly match JSON field names in API contracts
- Generate complete folder structure
- List all required environment variables
- Output a valid XML project manifest

Respond ONLY in valid JSON — no markdown fences:
{
  "database_tables": [{"table_name": "...", "prisma_schema": "...", "sql_schema": "..."}],
  "api_endpoints": [{"method": "POST", "path": "/api/...", "description": "...", "request_body": {}, "response_schema": {}, "status_codes": [201], "auth_required": true}],
  "tech_stack_manifest": "<project_manifest>...</project_manifest>",
  "folder_structure": "...",
  "env_variables_needed": ["DATABASE_URL", "NEXTAUTH_SECRET"]
}"""

SYNTHESIS_PROMPT = """You are a Senior Full-Stack Developer at Heaven AI.
Write production-quality code. ZERO placeholders. ZERO TODOs. ZERO incomplete functions.

RULES:
1. Every function body must be FULLY implemented
2. Every API route must have complete error handling
3. Database column names in code MUST match the Prisma schema EXACTLY
4. Never hardcode secrets — always use process.env.VARIABLE_NAME
5. Include proper TypeScript types everywhere
6. Every file must be syntactically valid and production-ready

Respond ONLY with this JSON (no markdown):
{"path": "src/app/page.tsx", "content": "...full file content...", "language": "typescript"}"""

CORRECTION_PROMPT = """You are a Senior QA Engineer at Heaven AI.
Fix the build error in the provided file.

RULES:
1. Read the exact error — do NOT guess
2. Fix ALL errors in one pass
3. Do not introduce new errors
4. Output the corrected file in JSON format (no markdown)

{"path": "...", "content": "...corrected full file...", "language": "..."}"""

AGREEMENT_PROMPT = """You are a Product Manager at Heaven AI.
Generate a Feature Agreement document for client confirmation.
Respond ONLY in valid JSON:
{
  "project_name": "...",
  "tech_stack": "Next.js 15 + TypeScript + Prisma + PostgreSQL",
  "features": ["...", "..."],
  "out_of_scope": ["...", "..."],
  "price_usd": 250.0,
  "delivery_estimate": "12 minutes build time",
  "manifest_xml": "<project_manifest>...</project_manifest>"
}"""


class GeminiService:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=8192,
            ),
        )
        self.model_creative = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config=genai.GenerationConfig(
                temperature=0.3,
                max_output_tokens=8192,
            ),
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def complete(self, system_prompt: str, user_message: str, creative: bool = False) -> str:
        model = self.model_creative if creative else self.model
        full_prompt = f"{system_prompt}\n\n---\n\n{user_message}"
        response = model.generate_content(full_prompt)
        return response.text

    def complete_json(self, system_prompt: str, user_message: str) -> Dict[str, Any]:
        raw = self.complete(system_prompt, user_message)
        # Strip markdown fences if present
        cleaned = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r'\s*```$', '', cleaned.strip(), flags=re.MULTILINE)
        # Find JSON object or array
        match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', cleaned)
        if match:
            cleaned = match.group(1)
        return json.loads(cleaned)

    def run_scoping(self, project_idea: str) -> Dict[str, Any]:
        return self.complete_json(
            SCOPING_PROMPT,
            f"Analyze this project idea:\n\nPROJECT IDEA: {project_idea}\n\nGenerate scoping JSON now."
        )

    def run_architecture(self, manifest_xml: str, answers: Dict[str, str]) -> Dict[str, Any]:
        return self.complete_json(
            ARCHITECTURE_PROMPT,
            f"Generate architecture blueprint.\n\nFEATURE AGREEMENT:\n{manifest_xml}\n\nCLIENT ANSWERS:\n{json.dumps(answers, indent=2)}"
        )

    def generate_file(self, file_path: str, blueprint_context: str, existing_files: list) -> Dict[str, Any]:
        existing = "\n".join([f"- {f['path']}" for f in existing_files])
        return self.complete_json(
            SYNTHESIS_PROMPT,
            f"Generate complete production code for: {file_path}\n\nBLUEPRINT:\n{blueprint_context}\n\nALREADY GENERATED:\n{existing}\n\nOutput JSON now."
        )

    def self_correct(self, error_logs: str, buggy_file: Dict) -> Dict[str, Any]:
        return self.complete_json(
            CORRECTION_PROMPT,
            f"Fix this file:\n\nFILE: {buggy_file['path']}\n\nCURRENT CONTENT:\n{buggy_file['content'][:3000]}\n\nBUILD ERROR:\n{error_logs[:1000]}"
        )

    def generate_feature_agreement(self, project_idea: str, scoping: Dict, answers: Dict) -> Dict[str, Any]:
        return self.complete_json(
            AGREEMENT_PROMPT,
            f"Project: {project_idea}\nScoping: {json.dumps(scoping)}\nAnswers: {json.dumps(answers)}"
        )

    def security_scan(self, files: list) -> Dict[str, Any]:
        files_preview = "\n\n".join([f"=== {f['path']} ===\n{f['content'][:500]}" for f in files[:6]])
        return self.complete_json(
            """You are a Security Engineer. Scan for hardcoded secrets and missing auth.
Output JSON only: {"secrets_found": [], "vulnerabilities_fixed": [], "corrected_files": []}""",
            f"Scan this codebase:\n{files_preview}"
        )
