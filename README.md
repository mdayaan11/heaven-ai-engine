# Heaven AI Engine

AI-powered autonomous software synthesis engine.

## Stack
- FastAPI + Python
- Google Gemini 2.0 Flash
- E2B Sandbox (code testing)
- GitHub API (repo creation)
- Upstash Redis (log streaming)

## Deploy on Render
1. Connect this repo to render.com
2. Set environment variables (see .env.example)
3. Build: `pip install -r requirements.txt`
4. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
