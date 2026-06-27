"""
Heaven AI — Task Store using Redis
No Celery needed — uses FastAPI BackgroundTasks + Redis for state/logs.
"""
from __future__ import annotations
import json
import os
import time
from typing import Any, Dict, List, Optional
import redis as redis_client
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
LOG_EXPIRY = 86400  # 24 hours

# Redis connection — works with Upstash TLS (rediss://)
_redis = redis_client.from_url(
    REDIS_URL,
    decode_responses=True,
    ssl_cert_reqs=None,  # Required for Upstash
)


def push_log(task_id: str, log_entry: Dict[str, Any]) -> None:
    _redis.rpush(f"heaven:logs:{task_id}", json.dumps(log_entry))
    _redis.expire(f"heaven:logs:{task_id}", LOG_EXPIRY)


def get_logs(task_id: str, since_index: int = 0) -> List[Dict]:
    raw = _redis.lrange(f"heaven:logs:{task_id}", since_index, -1)
    return [json.loads(r) for r in raw]


def set_build_state(task_id: str, state_dict: Dict[str, Any]) -> None:
    _redis.set(f"heaven:state:{task_id}", json.dumps(state_dict), ex=LOG_EXPIRY)


def get_build_state(task_id: str) -> Optional[Dict[str, Any]]:
    raw = _redis.get(f"heaven:state:{task_id}")
    return json.loads(raw) if raw else None


def set_scoping_answers(task_id: str, answers: Dict[str, str]) -> None:
    _redis.set(f"heaven:answers:{task_id}", json.dumps(answers), ex=LOG_EXPIRY)


def get_scoping_answers(task_id: str) -> Optional[Dict[str, str]]:
    raw = _redis.get(f"heaven:answers:{task_id}")
    return json.loads(raw) if raw else None


def ping_redis() -> bool:
    try:
        _redis.ping()
        return True
    except Exception:
        return False
