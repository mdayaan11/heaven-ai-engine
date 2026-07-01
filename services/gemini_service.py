text = re.sub(r"\s*```\s*$", "", text.strip(), flags=re.MULTILINE)
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
        
        # INTERCEPTOR: Auto-fix Pydantic validation errors if Gemini still stubbornly returns lists
        if isinstance(data, dict) and "api_endpoints" in data:
            for endpoint in data["api_endpoints"]:
                if isinstance(endpoint.get("response_schema"), list):
                    endpoint["response_schema"] = {"data": endpoint["response_schema"]}
                if isinstance(endpoint.get("request_body"), list):
                    endpoint["request_body"] = {"data": endpoint["request_body"]}
                    
        return data

    def generate_file(self, path: str, context: str, existing: list) -> Dict:
        done = "\n".join(f"- {f['path']}" for f in existing[:10])
        
        # Intercept content.json to stop frontend breaking
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
