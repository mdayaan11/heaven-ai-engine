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

SCOPING_PROMPT = """You are an elite Product Manager. Analyze this project idea and produce scoping questions.
Respond ONLY in valid compact JSON — no markdown, no code blocks, no extra text:
{"questions":[{"question_id":"q1","question_text":"...","options":["A","B","C"],"required":true}],"estimated_price_usd":500.0,"complexity_score":6,"estimated_build_time_minutes":12,"feature_summary":"..."}
Generate 3-5 highly relevant questions specific to the project type."""

ARCHITECTURE_PROMPT = """You are a Software Architect. Generate a minimal technical blueprint.
Keep ALL string values SHORT (one line max). No SQL. No Prisma syntax in strings.
Respond ONLY in valid compact JSON — no markdown:
{"database_tables":[{"table_name":"users","prisma_schema":"model User { id Int @id @default(autoincrement()) email String @unique }","sql_schema":"users(id,email)"}],"api_endpoints":[{"method":"GET","path":"/api/health","description":"Health check","request_body":{},"response_schema":{},"status_codes":[200],"auth_required":false}],"tech_stack_manifest":"Next.js 15 + TypeScript + Tailwind CSS","folder_structure":"src/app/","env_variables_needed":["DATABASE_URL"]}"""

SYNTHESIS_PROMPT = """You are a world-class Senior Full-Stack Developer and UI/UX Designer.
Generate a COMPLETE, PRODUCTION-READY file. Rules:
- NO placeholders. NO TODOs. NO "// implement here". Write REAL working code.
- Use Tailwind CSS classes for ALL styling. Make it VISUALLY STUNNING.
- Use real colors (gradients, dark themes). Real content. Real functionality.
- For page.tsx files: Create a beautiful, modern UI with hero sections, cards, animations.
- For 3D projects: Use dynamic imports with ssr:false for three.js components.
- For components: Make them interactive with hover effects, transitions.
- Import only packages that are in the project's package.json.

Respond ONLY in valid JSON — no markdown:
{"path":"src/app/page.tsx","content":"...COMPLETE FILE CONTENT...","language":"typescript"}"""

AGREEMENT_PROMPT = """You are a Product Manager. Generate a Feature Agreement.
Respond ONLY in valid compact JSON — no markdown:
{"project_name":"...","tech_stack":"Next.js 15 + TypeScript + Tailwind CSS","features":["feature1","feature2"],"out_of_scope":["item1"],"price_usd":500.0,"delivery_estimate":"12 min","manifest_xml":"<manifest><v>1</v></manifest>"}"""

PAGE_QUALITY_PROMPT = """You are a world-class UI/UX Developer. Generate src/app/page.tsx for this project.

REQUIREMENTS:
1. Beautiful dark theme with gradients (bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900)
2. Real content specific to the project (not placeholder text)
3. Hero section with project name + tagline
4. Feature showcase cards with icons (use lucide-react)
5. Smooth hover effects (hover:scale-105, transition-all duration-300)
6. Professional typography (font-bold, tracking-tight, text-white)
7. Call-to-action buttons with gradient backgrounds
8. For 3D projects: wrap THREE.js components in dynamic() with ssr:false

DO NOT use: placeholder text, grey boxes, Lorem ipsum, "Coming Soon", white backgrounds.
DO NOT import packages not in package.json.

Respond ONLY in valid JSON:
{"path":"src/app/page.tsx","content":"COMPLETE_CODE","language":"typescript"}"""


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
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192},
            },
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    def _fix_json(self, text: str) -> str:
        text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
        text = re.sub(r"\s*```\s*$", "", text.strip(), flags=re.MULTILINE)
        text = text.strip()
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if match:
            text = match.group(1)
        # Fix trailing commas
        text = re.sub(r",\s*([\}\]])", r"\1", text)
        return text

    def _parse_json(self, system: str, user: str, default: Dict = None) -> Dict[str, Any]:
        raw = ""
        cleaned = ""
        try:
            raw = self._call(system, user)
            cleaned = self._fix_json(raw)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Retry asking Gemini to fix its own JSON
            try:
                fix_prompt = f"Return ONLY valid JSON, no markdown. Fix this broken JSON:\n{cleaned[:3000]}"
                raw2 = self._call("You fix broken JSON. Return ONLY the fixed JSON object, nothing else.", fix_prompt)
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
                {"question_id": "q1", "question_text": "What is the primary goal?", "options": ["Showcase/Portfolio", "E-commerce", "SaaS App", "Information site"], "required": True},
                {"question_id": "q2", "question_text": "Color theme preference?", "options": ["Dark (modern/sleek)", "Light (clean/minimal)", "Colorful/Vibrant"], "required": True},
                {"question_id": "q3", "question_text": "Key feature priority?", "options": ["Visual design", "User auth", "Payment system", "Content management"], "required": True},
            ],
            "estimated_price_usd": 500.0,
            "complexity_score": 5,
            "estimated_build_time_minutes": 10,
            "feature_summary": idea[:200],
        }

    def _default_architecture(self) -> Dict:
        return {
            "database_tables": [{"table_name": "users", "prisma_schema": "model User { id Int @id }", "sql_schema": "users(id,email)"}],
            "api_endpoints": [{"method": "GET", "path": "/api/health", "description": "Health check", "request_body": {}, "response_schema": {}, "status_codes": [200], "auth_required": False}],
            "tech_stack_manifest": "Next.js 15 + TypeScript + Tailwind CSS",
            "folder_structure": "src/app/",
            "env_variables_needed": ["DATABASE_URL", "NEXTAUTH_SECRET"],
        }

    def _default_agreement(self, idea: str) -> Dict:
        return {
            "project_name": idea[:40],
            "tech_stack": "Next.js 15 + TypeScript + Tailwind CSS",
            "features": ["Beautiful UI", "User authentication", "Core functionality", "Responsive design"],
            "out_of_scope": ["Mobile app", "Advanced analytics"],
            "price_usd": 500.0,
            "delivery_estimate": "12 min build",
            "manifest_xml": "<manifest><project>v1</project></manifest>",
        }

    # ── Public API ──────────────────────────────────────────────────────────
    def run_scoping(self, idea: str) -> Dict:
        return self._parse_json(SCOPING_PROMPT, f"Project idea: {idea}", self._default_scoping(idea))

    def run_architecture(self, manifest: str, answers: Dict) -> Dict:
        raw = self._parse_json(
            ARCHITECTURE_PROMPT,
            f"Project: {manifest[:500]}\nAnswers: {json.dumps(answers)}",
            self._default_architecture()
        )
        # Normalize api_endpoints field names to avoid Pydantic conflicts
        endpoints = raw.get("api_endpoints", [])
        if isinstance(endpoints, dict):
            endpoints = list(endpoints.values())
        normalized = []
        for ep in endpoints:
            if not isinstance(ep, dict):
                continue
            n = dict(ep)
            # Rename alternative field names Gemini sometimes uses
            for alt in ("api_path", "endpoint", "route", "url"):
                if alt in n and "path" not in n:
                    n["path"] = n.pop(alt)
            for alt in ("api_description", "desc", "summary"):
                if alt in n and "description" not in n:
                    n["description"] = n.pop(alt)
            normalized.append(n)
        raw["api_endpoints"] = normalized
        return raw

    def generate_file(self, path: str, context: str, existing: list) -> Dict:
        done = "\n".join(f"- {f['path']}" for f in existing[:10])
        # Extract project name from context
        proj_name = "My App"
        for line in context.split("\n"):
            if line.strip().startswith("PROJECT:"):
                proj_name = line.split(":", 1)[1].strip()
                break
        # Use enhanced prompt for main page
        prompt = PAGE_QUALITY_PROMPT if path in ("src/app/page.tsx", "app/page.tsx") else SYNTHESIS_PROMPT
        # Smart fallback based on file type — NEVER a blank page
        if path in ("src/app/page.tsx", "app/page.tsx"):
            from agents.scaffold_templates import fallback_page_tsx
            fallback_content = fallback_page_tsx(proj_name)
        elif path.endswith("Navbar.tsx") or path.endswith("navbar.tsx"):
            fallback_content = f"""'use client';
import {{ Coffee, Menu, X }} from 'lucide-react';
import {{ useState }} from 'react';

export default function Navbar() {{
  const [open, setOpen] = useState(false);
  return (
    <nav className="fixed top-0 w-full z-50 backdrop-blur-xl bg-black/30 border-b border-white/10">
      <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
        <h1 className="text-xl font-bold bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">
          {proj_name}
        </h1>
        <div className="hidden md:flex gap-6 text-sm text-gray-300">
          <a href="#" className="hover:text-white transition-colors">Home</a>
          <a href="#" className="hover:text-white transition-colors">About</a>
          <a href="#" className="hover:text-white transition-colors">Contact</a>
        </div>
      </div>
    </nav>
  );
}}
"""
        elif path.endswith(".tsx"):
            name = path.split("/")[-1].replace(".tsx", "").replace("-", " ").title().replace(" ", "")
            fallback_content = f"export default function {name}() {{ return <div className=\"p-8 text-white\">Section: {name}</div>; }}"
        elif path.endswith(".ts") and not path.endswith(".d.ts"):
            fallback_content = "// auto-generated\nexport {};"
        elif path.endswith(".css"):
            fallback_content = "/* auto-generated */"
        elif path.endswith(".prisma"):
            fallback_content = 'datasource db {\\n  provider = "postgresql"\\n  url = env("DATABASE_URL")\\n}\\ngenerator client {\\n  provider = "prisma-client-js"\\n}'
        else:
            fallback_content = f"// auto-generated: {path}"
        return self._parse_json(
            prompt,
            f"Generate: {path}\nProject context:\n{context[:1500]}\nFiles already done:\n{done}",
            {"path": path, "content": fallback_content, "language": "typescript"}
        )

    def self_correct(self, error: str, buggy: Dict) -> Dict:
        return self._parse_json(
            "Fix the TypeScript/build error. Return ONLY valid JSON: {\"path\":\"...\",\"content\":\"...\",\"language\":\"...\"}",
            f"File: {buggy['path']}\nError:\n{error[:600]}\nBuggy content:\n{buggy.get('content','')[:1500]}",
            buggy
        )

    def generate_feature_agreement(self, idea: str, scoping: Dict, answers: Dict) -> Dict:
        return self._parse_json(
            AGREEMENT_PROMPT,
            f"Project: {idea}\nScoping: {json.dumps(scoping)[:400]}\nAnswers: {json.dumps(answers)}",
            self._default_agreement(idea)
        )

    def __del__(self):
        try:
            self.client.close()
        except Exception:
            pass
