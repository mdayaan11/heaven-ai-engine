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

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

SCOPING_PROMPT = """You are an elite Product Manager. Analyze this project idea.
Respond ONLY in valid JSON — no markdown, no code blocks, no extra text:
{"questions":[{"question_id":"q1","question_text":"...","options":["A","B","C"],"required":true}],"estimated_price_usd":250.0,"complexity_score":5,"estimated_build_time_minutes":10,"feature_summary":"..."}"""

ARCHITECTURE_PROMPT = """You are a Software Architect. Generate a technical blueprint.
Keep all string values SHORT and simple — no multi-line strings, no SQL, no Prisma schemas.
Respond ONLY in valid compact JSON — no markdown, no code blocks:
{"database_tables":[{"table_name":"users","prisma_schema":"model User { id Int }","sql_schema":"CREATE TABLE users (id INT)"}],"api_endpoints":[{"method":"POST","path":"/api/auth","description":"Login endpoint","request_body":{},"response_schema":{},"status_codes":[200],"auth_required":false}],"tech_stack_manifest":"Next.js 15 + TypeScript","folder_structure":"src/app/page.tsx","env_variables_needed":["DATABASE_URL"]}"""

SYNTHESIS_PROMPT = """You are a Senior Full-Stack Developer. Write complete production code.
Respond ONLY in valid JSON — no markdown, no code blocks:
{"path":"src/app/page.tsx","content":"...complete file content...","language":"typescript"}"""

AGREEMENT_PROMPT = """You are a Product Manager. Generate a Feature Agreement.
Respond ONLY in valid compact JSON — no markdown, no code blocks:
{"project_name":"...","tech_stack":"Next.js 15 + TypeScript","features":["feature1","feature2"],"out_of_scope":["item1"],"price_usd":250.0,"delivery_estimate":"10 min","manifest_xml":"<manifest>v1</manifest>"}"""


class GeminiService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.Client(timeout=90.0)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
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

    def _fix_json(self, text: str) -> str:
        """Try to repair common JSON issues."""
        # Remove markdown code blocks
        text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
        text = re.sub(r"\s*```\s*$", "", text.strip(), flags=re.MULTILINE)
        text = text.strip()
        # Extract first JSON object or array
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if match:
            text = match.group(1)
        # Remove trailing commas before } or ]
        text = re.sub(r",\s*([\}\]])", r"\1", text)
        # Fix single quotes (not in strings)
        return text

    def _parse_json(self, system: str, user: str, default: Dict = None) -> Dict[str, Any]:
        try:
            raw = self._call(system, user)
            cleaned = self._fix_json(raw)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Try progressively more aggressive fixes
            try:
                raw2 = self._call(
                    "Fix this broken JSON and return ONLY valid JSON, nothing else:",
                    f"Error: {str(e)[:100]}\nJSON: {cleaned[:2000]}"
                )
                return json.loads(self._fix_json(raw2))
            except Exception:
                if default is not None:
                    return default
                raise
        except Exception:
            if default is not None:
                return default
            raise

    # ── Default fallbacks ──────────────────────────────────────────────────
    def _default_scoping(self, idea: str) -> Dict:
        return {
            "questions": [
                {"question_id": "q1", "question_text": "What is the primary goal?", "options": ["Information only", "E-commerce", "SaaS platform"], "required": True},
                {"question_id": "q2", "question_text": "Target audience?", "options": ["Consumer (B2C)", "Business (B2B)", "Internal tool"], "required": True},
                {"question_id": "q3", "question_text": "Authentication needed?", "options": ["Yes — email/password", "Yes — social login", "No auth needed"], "required": True},
            ],
            "estimated_price_usd": 500.0,
            "complexity_score": 5,
            "estimated_build_time_minutes": 10,
            "feature_summary": idea[:200],
        }

    def _default_architecture(self) -> Dict:
        return {
            "database_tables": [{"table_name": "users", "prisma_schema": "model User { id Int @id }", "sql_schema": "CREATE TABLE users (id INT PRIMARY KEY)"}],
            "api_endpoints": [{"method": "GET", "path": "/api/health", "description": "Health check", "request_body": {}, "response_schema": {}, "status_codes": [200], "auth_required": False}],
            "tech_stack_manifest": "Next.js 15 + TypeScript + Tailwind",
            "folder_structure": "src/app/",
            "env_variables_needed": ["DATABASE_URL", "NEXTAUTH_SECRET"],
        }

    def _default_agreement(self, idea: str) -> Dict:
        return {
            "project_name": idea[:40],
            "tech_stack": "Next.js 15 + TypeScript + Prisma",
            "features": ["User authentication", "Core UI", "API endpoints", "Database"],
            "out_of_scope": ["Mobile app", "Advanced analytics"],
            "price_usd": 500.0,
            "delivery_estimate": "10 min build",
            "manifest_xml": "<manifest><project>v1</project></manifest>",
        }

    # ── Public API ──────────────────────────────────────────────────────────
    def run_scoping(self, idea: str) -> Dict:
        return self._parse_json(SCOPING_PROMPT, f"Project idea: {idea}", self._default_scoping(idea))

    def run_architecture(self, manifest: str, answers: Dict) -> Dict:
        return self._parse_json(ARCHITECTURE_PROMPT, f"Project: {manifest}\nAnswers: {json.dumps(answers)}", self._default_architecture())

    def generate_file(self, path: str, context: str, existing: list) -> Dict:
        done = "\n".join(f"- {f['path']}" for f in existing[:10])
        return self._parse_json(SYNTHESIS_PROMPT, f"Generate: {path}\nProject: {context[:500]}\nDone: {done}", {"path": path, "content": "// TODO: implement", "language": "typescript"})

    def self_correct(self, error: str, buggy: Dict) -> Dict:
        return self._parse_json("Fix the build error. Return JSON only: {\"path\":\"...\",\"content\":\"...\",\"language\":\"...\"}", f"File: {buggy['path']}\nContent:\n{buggy.get('content','')[:1500]}\nError:\n{error[:500]}", buggy)

    def generate_feature_agreement(self, idea: str, scoping: Dict, answers: Dict) -> Dict:
        return self._parse_json(AGREEMENT_PROMPT, f"Project: {idea}\nScoping: {json.dumps(scoping)[:500]}\nAnswers: {json.dumps(answers)}", self._default_agreement(idea))

    def __del__(self):
        try:
            self.client.close()
        except Exception:
            pass
