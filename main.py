"""
Heaven AI Engine — FastAPI Application Entry Point (Gemini Edition)
"""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from dotenv import load_dotenv

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    required = ["GEMINI_API_KEY", "GITHUB_TOKEN", "GITHUB_USERNAME", "REDIS_URL"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"⚠  Missing env vars: {', '.join(missing)}")
    else:
        print("✅ All environment variables present.")
    print("🚀 Heaven AI Engine (Gemini Edition) is running.")
    yield
    print("🛑 Shutting down.")


app = FastAPI(
    title="Heaven AI Autonomous Engine",
    description="Multi-agent software synthesis — Scope → Architect → Build → Deploy",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "https://heavenaii.netlify.app,http://localhost:3000,http://localhost:8080"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

from api.routes import router
app.include_router(router)


@app.get("/")
async def root():
    return {
        "service": "Heaven AI Autonomous Engine",
        "model": "Google Gemini 2.0 Flash",
        "version": "2.0.0",
        "status": "operational",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        reload=False,
        log_level="info",
    )
