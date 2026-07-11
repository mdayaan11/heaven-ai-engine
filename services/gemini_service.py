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

# ─────────────────────────────────────────────────────────────────────────────
# Prompts — each one tells Gemini EXACTLY what format to return
# ─────────────────────────────────────────────────────────────────────────────

SCOPING_PROMPT = """You are an elite Product Manager. Analyze this project idea and produce scoping questions.
Respond ONLY in valid compact JSON — no markdown, no code blocks, no extra text:
{"questions":[{"question_id":"q1","question_text":"...","options":["A","B","C"],"required":true}],"estimated_price_usd":500.0,"complexity_score":6,"estimated_build_time_minutes":12,"feature_summary":"..."}
Generate 3-5 highly relevant questions specific to the project type."""

AGREEMENT_PROMPT = """You are a Product Manager. Generate a Feature Agreement.

CRITICAL RULES for project_name:
- Extract a SHORT, BRANDABLE project name (2-4 words max)
- NEVER use the user's raw prompt as the name
- Examples: "build me a cafe website" → "Café Lumière" or "Urban Brew"
- Examples: "make a 3d portfolio" → "Studio 3D" or "Creative Space"
- Examples: "e-commerce for shoes" → "Sole Market" or "Step Style"

Respond ONLY in valid compact JSON — no markdown:
{"project_name":"SHORT BRAND NAME","tech_stack":"Next.js 15 + TypeScript + Tailwind CSS","features":["feature1","feature2"],"out_of_scope":["item1"],"price_usd":500.0,"delivery_estimate":"12 min","manifest_xml":"<manifest><v>1</v></manifest>"}"""

ARCHITECTURE_PROMPT = """You are a Software Architect. Generate a minimal technical blueprint.
Keep ALL string values SHORT (one line max). No SQL. No Prisma syntax in strings.
Respond ONLY in valid compact JSON — no markdown:
{"database_tables":[{"table_name":"users","prisma_schema":"model User { id Int @id @default(autoincrement()) email String @unique }","sql_schema":"users(id,email)"}],"api_endpoints":[{"method":"GET","path":"/api/health","description":"Health check","request_body":{},"response_schema":{},"status_codes":[200],"auth_required":false}],"tech_stack_manifest":"Next.js 15 + TypeScript + Tailwind CSS","folder_structure":"src/app/","env_variables_needed":["DATABASE_URL"]}"""

SYNTHESIS_PROMPT = """You are a world-class Senior Full-Stack Developer and UI/UX Designer.
Generate a COMPLETE, PRODUCTION-READY file. Rules:
- NO placeholders. NO TODOs. NO "// implement here". Write REAL working code.
- Add 'use client'; at the top if the component uses useState, useEffect, onClick, or any interactivity.
- Use Tailwind CSS classes for ALL styling. Make it VISUALLY STUNNING.
- Use real colors (gradients, dark themes). Real content. Real functionality.
- For components: Make them interactive with hover effects, transitions.
- Import only from: react, next/link, next/image, next/dynamic, lucide-react.

Respond ONLY in valid JSON — no markdown:
{"path":"src/app/page.tsx","content":"...COMPLETE FILE CONTENT...","language":"typescript"}"""

PAGE_QUALITY_PROMPT = """You are a world-class UI/UX Developer. Generate src/app/page.tsx.

YOU MUST generate a COMPLETE, BEAUTIFUL, INTERACTIVE page with ALL of these sections:
1. Fixed glassmorphism navbar with logo + navigation links
2. Massive hero section with gradient text, tagline, and CTA buttons
3. Statistics row (e.g. "12+ Years", "50k+ Customers", "4.9★ Rating")
4. Feature/service cards grid (3-6 cards) with icons from lucide-react
5. Testimonials/reviews section with star ratings
6. Contact or CTA section with a form or action
7. Footer with links and copyright

STYLING RULES:
- Start with: 'use client';
- Dark theme: bg-gradient-to-br from-[#0a0a0a] via-[#1a0f2e] to-[#0d0d0d]
- Cards: bg-white/[0.03] border border-white/[0.06] rounded-2xl
- Hover: hover:scale-[1.02] hover:border-purple-500/30 transition-all duration-300
- Gradients on text: bg-gradient-to-r from-amber-400 to-orange-500 bg-clip-text text-transparent
- Buttons: bg-gradient-to-r from-purple-500 to-pink-600 rounded-full
- Import icons ONLY from lucide-react
- Write ALL content inline — real text, real prices, real descriptions
- Make buttons and tabs interactive with useState

DO NOT:
- Use placeholder text, Lorem ipsum, "Coming Soon", or empty sections
- Import packages not in package.json (only use: react, lucide-react, next/link, next/dynamic)
- Use white or light backgrounds
- Generate less than 100 lines of code

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
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 8192},
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
        text = re.sub(r",\s*([\}\]])", r"\1", text)
        return text

    def _parse_json(self, system: str, user: str, default: Dict = None) -> Dict[str, Any]:
        raw = ""
        cleaned = ""
        try:
            raw = self._call(system, user)
            cleaned = self._fix_json(raw)
            return json.loads(cleaned)
        except json.JSONDecodeError:
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

    # ── Name extraction ────────────────────────────────────────────────────
    @staticmethod
    def _extract_project_name(idea: str) -> str:
        """Convert a raw user prompt into a short brand name.
        
        Examples:
          'build me a portfolio im aayan sk' → 'Aayan SK'
          'build me a 3d cafe website' → '3D Cafe'
          'create an e-commerce store called Urban Style' → 'Urban Style'
          'make me a portfolio my name is John Doe' → 'John Doe'
        """
        text = idea.strip()
        
        # 1. Check for explicit name: "called X", "named X", "name is X", "name: X"
        name_match = re.search(
            r"(?:called|named|name\s+is|name\s*:)\s+(.+?)(?:\s*$|\s+(?:with|using|for|please))",
            text, re.IGNORECASE
        )
        if name_match:
            return name_match.group(1).strip().title()[:40]
        
        # 2. Check for "im X" / "i am X" / "i'm X" — extract person name
        person_match = re.search(
            r"(?:^|\s)(?:im|i\s*am|i'm)\s+(.+?)(?:\s*$|\s+(?:and|with|using|please))",
            text, re.IGNORECASE
        )
        person_name = ""
        if person_match:
            person_name = person_match.group(1).strip()
            # Remove trailing filler
            person_name = re.sub(r"\b(and|with|please|pls|thanks)\b.*$", "", person_name, flags=re.IGNORECASE).strip(" .,")
        
        # 3. Strip command words from beginning
        cleaned = re.sub(
            r"^(build|make|create|design|generate|develop|code)\s+(me\s+)?(a\s+)?",
            "", text, flags=re.IGNORECASE
        ).strip()
        
        # 4. Detect project type for suffix
        type_words = {
            "portfolio": "Portfolio", "cafe": "Café", "coffee": "Café",
            "restaurant": "Kitchen", "shop": "Store", "store": "Store",
            "ecommerce": "Market", "e-commerce": "Market",
            "blog": "Blog", "agency": "Studio", "gym": "Fitness",
            "saas": "Platform", "dashboard": "Dashboard",
        }
        detected_type = ""
        for keyword, label in type_words.items():
            if keyword in cleaned.lower():
                detected_type = label
                break
        
        # 5. Strip ALL filler/type words
        cleaned = re.sub(
            r"\b(website|web\s*site|web\s*app|application|app|page|landing\s*page|"
            r"portfolio|cafe|coffee|restaurant|shop|store|ecommerce|e-commerce|"
            r"blog|agency|gym|saas|dashboard|3d|animated|animation|"
            r"for|with|using|please|pls|im|i\s*am|i'm|my|name|is|of|mine|the|"
            r"online|modern|beautiful|stylish|aesthetic|cool|awesome|best|top|"
            r"build|make|create|design|full|stack|responsive)\b",
            "", cleaned, flags=re.IGNORECASE
        ).strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -,.")
        
        # 6. Build final name
        if person_name and detected_type:
            # "im aayan sk" + portfolio → "Aayan SK"
            return person_name.title()[:30]
        if person_name:
            return person_name.title()[:30]
        if cleaned and len(cleaned) >= 2:
            words = cleaned.split()[:4]
            name = " ".join(w.capitalize() for w in words)
            if detected_type and detected_type.lower() not in name.lower():
                name = f"{name} {detected_type}"
            return name[:40]
        if detected_type:
            return detected_type
        
        # 7. Check for "3d" in original
        if "3d" in text.lower():
            return "3D " + (detected_type or "Studio")
        
        return "Heaven Project"

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
            "project_name": self._extract_project_name(idea),
            "tech_stack": "Next.js 15 + TypeScript + Tailwind CSS",
            "features": ["Beautiful UI", "Interactive components", "Responsive design", "Dark theme"],
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
        endpoints = raw.get("api_endpoints", [])
        if isinstance(endpoints, dict):
            endpoints = list(endpoints.values())
        normalized = []
        for ep in endpoints:
            if not isinstance(ep, dict):
                continue
            n = dict(ep)
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
import {{ Menu, X }} from 'lucide-react';
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
          <a href="#about" className="hover:text-white transition-colors">About</a>
          <a href="#contact" className="hover:text-white transition-colors">Contact</a>
        </div>
        <button onClick={{() => setOpen(!open)}} className="md:hidden text-white">
          {{open ? <X /> : <Menu />}}
        </button>
      </div>
    </nav>
  );
}}
"""
        elif path.endswith(".tsx"):
            name = path.split("/")[-1].replace(".tsx", "").replace("-", " ").title().replace(" ", "")
            fallback_content = f"""'use client';
export default function {name}() {{
  return (
    <section className="py-16 px-6">
      <div className="max-w-7xl mx-auto">
        <h2 className="text-3xl font-bold text-white mb-4">{name}</h2>
        <p className="text-gray-400">Content section</p>
      </div>
    </section>
  );
}}
"""
        elif path.endswith(".ts") and not path.endswith(".d.ts"):
            fallback_content = "// auto-generated\nexport {};"
        elif path.endswith(".css"):
            fallback_content = "/* auto-generated */"
        else:
            fallback_content = f"// auto-generated: {path}"
        return self._parse_json(
            prompt,
            f"Generate: {path}\nProject context:\n{context[:2000]}\nFiles already done:\n{done}",
            {"path": path, "content": fallback_content, "language": "typescript"}
        )

    def self_correct(self, error: str, buggy: Dict) -> Dict:
        return self._parse_json(
            "Fix the TypeScript/build error. Return ONLY valid JSON: {\"path\":\"...\",\"content\":\"...\",\"language\":\"...\"}",
            f"File: {buggy['path']}\nError:\n{error[:600]}\nBuggy content:\n{buggy.get('content','')[:1500]}",
            buggy
        )

    def generate_feature_agreement(self, idea: str, scoping: Dict, answers: Dict) -> Dict:
        result = self._parse_json(
            AGREEMENT_PROMPT,
            f"Project: {idea}\nScoping: {json.dumps(scoping)[:400]}\nAnswers: {json.dumps(answers)}",
            self._default_agreement(idea)
        )
        # Safety check: if Gemini used the raw prompt as project name, fix it
        raw_name = result.get("project_name", "")
        if raw_name.lower().startswith(("build", "make", "create", "design", "generate")) or len(raw_name) > 30:
            result["project_name"] = self._extract_project_name(idea)
        return result

    def __del__(self):
        try:
            self.client.close()
        except Exception:
            pass
