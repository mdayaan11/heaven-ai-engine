"""
Heaven AI — Gemini Service via direct REST API (no SDK needed)
Uses httpx only — zero extra dependencies.
"""
from __future__ import annotations
import json
import re
from typing import Any, Dict
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

SCOPING_PROMPT = """You are an elite Product Manager. Analyze a raw project idea and produce scoping analysis.
Respond ONLY in valid JSON — no markdown:
{
  "questions": [
    {"question_id": "q1", "question_text": "...", "options": ["A","B","C"], "required": true}
  ],
  "estimated_price_usd": 250.0,
  "complexity_score": 5,
  "estimated_build_time_minutes": 10,
  "feature_summary": "..."
}"""

ARCHITECTURE_PROMPT = """You are a Principal Software Architect. Generate a complete technical blueprint.
Respond ONLY in valid JSON — no markdown:
{
  "database_tables": [{"table_name":"users","prisma_schema":"model User {...}","sql_schema":"CREATE TABLE users (...)"}],
  "api_endpoints": [{"method":"POST","path":"/api/auth","description":"...","request_body":{},"response_schema":{},"status_codes":[201],"auth_required":false}],
  "tech_stack_manifest": "<manifest>Next.js 15</manifest>",
  "folder_structure": "src/app/...",
  "env_variables_needed": ["DATABASE_URL","NEXTAUTH_SECRET"]
}"""

SYNTHESIS_PROMPT = """You are a Senior Full-Stack Developer. Write complete production code. NO placeholders. NO TODOs.
Respond ONLY in valid JSON — no markdown:
{"path": "src/app/page.tsx", "content": "...full file...", "language": "typescript"}"""

AGREEMENT_PROMPT = """You are a Product Manager. Generate a Feature Agreement.
Respond ONLY in valid JSON — no markdown:
{
  "project_name": "...",
  "tech_stack": "Next.js 15 + TypeScript + Prisma",
  "features": ["..."],
  "out_of_scope": ["..."],
  "price_usd": 250.0,
  "delivery_estimate": "10 min build",
  "manifest_xml": "<manifest>...</manifest>"
}"""


class GeminiService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.Client(timeout=60.0)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=8))
    def _call(self, system: str, user: str) -> str:
        resp = self.client.post(
            GEMINI_URL,
            params={"key": self.api_key},
            json={
                "contents": [{"parts": [{"text": f"{system}\n\n---\n\n{user}"}], "role": "user"}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192},
            },
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    def _parse_json(self, system: str, user: str) -> Dict[str, Any]:
        raw = self._call(system, user)
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
        if match:
            cleaned = match.group(1)
        return json.loads(cleaned)

    def run_scoping(self, idea: str) -> Dict:
        return self._parse_json(SCOPING_PROMPT, f"Project idea: {idea}")

    def run_architecture(self, manifest: str, answers: Dict) -> Dict:
        return self._parse_json(ARCHITECTURE_PROMPT, f"Feature agreement:\n{manifest}\n\nAnswers:\n{json.dumps(answers)}")

    def generate_file(self, path: str, context: str, existing: list) -> Dict:
        done = "\n".join(f"- {f['path']}" for f in existing)
        return self._parse_json(SYNTHESIS_PROMPT, f"Generate: {path}\n\nContext:\n{context}\n\nAlready done:\n{done}")

    def self_correct(self, error: str, buggy: Dict) -> Dict:
        prompt = """Fix the build error. Output JSON only: {"path":"...","content":"...","language":"..."}"""
        return self._parse_json(prompt, f"File: {buggy['path']}\nContent:\n{buggy['content'][:2000]}\nError:\n{error[:800]}")

    def generate_feature_agreement(self, idea: str, scoping: Dict, answers: Dict) -> Dict:
        return self._parse_json(AGREEMENT_PROMPT, f"Project: {idea}\nScoping: {json.dumps(scoping)}\nAnswers: {json.dumps(answers)}")

    def __del__(self):
        try:
            self.client.close()
        except Exception:
            pass
