#!/bin/bash
# Heaven AI Engine — Quick Start Script
echo "🚀 Starting Heaven AI Engine..."

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Install from https://python.org"
    exit 1
fi

# 2. Create venv if not exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# 3. Activate venv
source .venv/bin/activate

# 4. Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt -q

# 5. Check .env
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚠  Created .env from .env.example — FILL IN YOUR API KEYS before proceeding!"
    echo "   Required: ANTHROPIC_API_KEY, E2B_API_KEY, GITHUB_TOKEN, GITHUB_USERNAME, VERCEL_TOKEN"
    exit 1
fi

# 6. Create __init__ files
touch agents/__init__.py services/__init__.py tasks/__init__.py api/__init__.py models/__init__.py

# 7. Start Redis (requires Redis installed: brew install redis)
echo "🔴 Starting Redis..."
redis-server --daemonize yes --logfile /tmp/heaven-redis.log

# 8. Start Celery worker in background
echo "⚙  Starting Celery worker..."
celery -A tasks.build_tasks.celery_app worker --loglevel=info --detach \
    --logfile=/tmp/heaven-celery.log --pidfile=/tmp/heaven-celery.pid

# 9. Start FastAPI server
echo "✅ Heaven AI Engine starting on http://localhost:8000"
echo "   📊 API Docs: http://localhost:8000/docs"
echo "   🖥  Engine Console: open frontend/engine_console.html in browser"
python main.py
