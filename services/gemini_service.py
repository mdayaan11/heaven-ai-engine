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

GEMINI_URL = "[https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent](https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent)"

SCOPING_PROMPT = """You are an elite Product Manager. Analyze this project idea.
Respond ONLY in valid JSON — no markdown, no code blocks, no extra text:
{"questions":[{"question_id":"q1","question_text":"...","options":["A","B","C"],"required":true}],"estimated_price_usd":250.0,"complexity_score":5,"estimated_build_time_minutes":10,"feature_summary":"..."}"""

ARCHITECTURE_PROMPT = """You are a Software Architect. Generate a technical blueprint.
Keep all string values SHORT and simple.

CRITICAL: The 'request_body' and 'response_schema' fields inside 'api_endpoints' MUST be valid objects/dictionaries (e.g., {}). They must NEVER be an array or list [].

Respond ONLY in valid compact JSON — no markdown, no code blocks:
{"database_tables":[{"table_name":"users","prisma_schema":"model User { id Int }","sql_schema":"CREATE TABLE users (id INT)"}],"api_endpoints":[{"method":"POST","path":"/api/auth","description":"Login endpoint","request_body":{},"response_schema":{},"status_codes":[200],"auth_required":false}],"tech_stack_manifest":"Next.js 15 + TypeScript","folder_structure":"src/app/page.tsx","env_variables_needed":["DATABASE_URL"]}"""

SYNTHESIS_PROMPT = """You are a Lead Design Systems Architect. Your job is to output a premium layout profile.
When generating 'src/app/content.json', you must populate this exact JSON structure with rich, highly customized text matching the user's specific project request.

Respond ONLY in valid compact JSON — no markdown, no code blocks:
{
  "businessName": "Name of the business",
  "tagline": "A short, premium catchy tagline hook",
  "heroDescription": "Deep, creative description matching the user's aesthetic request",
  "themeMode": "dark", 
  "accentGradients": "from-amber-500 to-orange-600",
  "features": [
    {
      "title": "Feature or Product Title",
      "desc": "High-quality detail text"
    }
  ]
}"""

AGREEMENT_PROMPT = """You are a Product Manager. Generate a Feature Agreement.
Respond ONLY in valid compact JSON:
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
        # Note: Markdown backticks escaped to prevent UI rendering bugs
        text = re.sub(r"^\`\`\`(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
        text = re.sub(r"\s*\`\`\`\s*$", "", text.strip(), flags=re.MULTILINE)
        text = text.strip()
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if match:
            text = match.group(1)
        text = re.sub(r",\s*([\}\]])", r"\1", text)
        return text

    def _parse_json(self, system: str, user: str, default: Dict = None) -> Dict[str, Any]:
        try:
            raw = self._call(system, user)
            cleaned = self._fix_json(raw)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
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

    def _default_scoping(self, idea: str) -> Dict:
        return {
            "questions": [
                {"question_id": "q1", "question_text": "What is the primary goal?", "options": ["Information only", "E-commerce", "SaaS"], "required": True}
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
            "env_variables_needed": ["DATABASE_URL"],
        }

    def _default_agreement(self, idea: str) -> Dict:
        return {
            "project_name": idea[:40],
            "tech_stack": "Next.js 15 + TypeScript",
            "features": ["User authentication", "Core UI"],
            "out_of_scope": ["Mobile app"],
            "price_usd": 500.0,
            "delivery_estimate": "10 min build",
            "manifest_xml": "<manifest><project>v1</project></manifest>",
        }

    def run_scoping(self, idea: str) -> Dict:
        return self._parse_json(SCOPING_PROMPT, f"Project idea: {idea}", self._default_scoping(idea))

    def run_architecture(self, manifest: str, answers: Dict) -> Dict:
        data = self._parse_json(ARCHITECTURE_PROMPT, f"Project: {manifest}\nAnswers: {json.dumps(answers)}", self._default_architecture())
        
        # ULTIMATE BULLETPROOF FIX: Forces lists to become dictionaries before Pydantic ever sees them.
        if isinstance(data, dict) and isinstance(data.get("api_endpoints"), list):
            for endpoint in data["api_endpoints"]:
                if isinstance(endpoint, dict):
                    # Clean response_schema
                    if "response_schema" in endpoint:
                        if isinstance(endpoint["response_schema"], list):
                            endpoint["response_schema"] = {"items": endpoint["response_schema"]}
                        elif not isinstance(endpoint["response_schema"], dict):
                            endpoint["response_schema"] = {}
                    else:
                        endpoint["response_schema"] = {}
                        
                    # Clean request_body
                    if "request_body" in endpoint:
                        if isinstance(endpoint["request_body"], list):
                            endpoint["request_body"] = {"items": endpoint["request_body"]}
                        elif not isinstance(endpoint["request_body"], dict):
                            endpoint["request_body"] = {}
                    else:
                        endpoint["request_body"] = {}
                        
        return data

    def generate_file(self, path: str, context: str, existing: list) -> Dict:
        done = "\n".join(f"- {f['path']}" for f in existing[:10])
        
        if "content.json" in path:
            return self._parse_json(SYNTHESIS_PROMPT, f"Generate the design configuration details for: {context[:500]}", {"businessName": "Ayan Cafe", "tagline": "Premium Space", "heroDescription": "Built autonomously.", "themeMode": "dark", "accentGradients": "from-amber-500 to-orange-600", "features": []})
            
        return self._parse_json("You are a Senior Developer. Return valid code inside JSON: {\"path\":\"...\",\"content\":\"...\",\"language\":\"...\"}", f"Generate file code content for: {path}\nProject context: {context[:500]}\nFiles already written:\n{done}", {"path": path, "content": "// Secure module fallback", "language": "typescript"})

    def self_correct(self, error: str, buggy: Dict) -> Dict:
        return self._parse_json("Fix the build error. Return JSON only: {\"path\":\"...\",\"content\":\"...\",\"language\":\"...\"}", f"File: {buggy['path']}\nContent:\n{buggy.get('content','')[:1500]}\nError:\n{error[:500]}", buggy)

    def generate_feature_agreement(self, idea: str, scoping: Dict, answers: Dict) -> Dict:
        return self._parse_json(AGREEMENT_PROMPT, f"Project: {idea}\nScoping: {json.dumps(scoping)[:500]}\nAnswers: {json.dumps(answers)}", self._default_agreement(idea))

    def __del__(self):
        try:
            self.client.close()
        except Exception:
            pass
