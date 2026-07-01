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
        text = re.sub(r"^
