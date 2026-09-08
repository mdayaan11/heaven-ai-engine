"""
Heaven AI — Task Store with Redis + In-Memory Fallback
If Redis is unavailable, uses in-memory dict so builds still work.
"""
from __future__ import annotations
import json
import os
import time
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.environ.get("REDIS_URL", "")
LOG_EXPIRY = 86400  # 24 hours

# ─── In-memory fallback ─────────────────────────────────────────────────────
_memory_store: Dict[str, Any] = {}
_memory_logs: Dict[str, List[str]] = {}


# ─── Try to connect to Redis ────────────────────────────────────────────────
_redis = None
try:
    if REDIS_URL:
        import redis as redis_client
        _redis = redis_client.from_url(
            REDIS_URL,
            decode_responses=True,
            ssl_cert_reqs=None,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        _redis.ping()
        print("✅ Redis connected")
    else:
        print("⚠ No REDIS_URL — using in-memory store")
except Exception as e:
    print(f"⚠ Redis unavailable ({str(e)[:60]}) — using in-memory store")
    _redis = None


# ─── Public API (works with or without Redis) ───────────────────────────────

def push_log(task_id: str, log_entry: Dict[str, Any]) -> None:
    serialized = json.dumps(log_entry)
    if _redis:
        try:
            _redis.rpush(f"heaven:logs:{task_id}", serialized)
            _redis.expire(f"heaven:logs:{task_id}", LOG_EXPIRY)
            return
        except Exception:
            pass
    # Fallback
    key = f"heaven:logs:{task_id}"
    if key not in _memory_logs:
        _memory_logs[key] = []
    _memory_logs[key].append(serialized)


def get_logs(task_id: str, since_index: int = 0) -> List[Dict]:
    if _redis:
        try:
            raw = _redis.lrange(f"heaven:logs:{task_id}", since_index, -1)
            return [json.loads(r) for r in raw]
        except Exception:
            pass
    key = f"heaven:logs:{task_id}"
    raw = _memory_logs.get(key, [])[since_index:]
    return [json.loads(r) for r in raw]


def set_build_state(task_id: str, state_dict: Dict[str, Any]) -> None:
    serialized = json.dumps(state_dict)
    if _redis:
        try:
            _redis.set(f"heaven:state:{task_id}", serialized, ex=LOG_EXPIRY)
            return
        except Exception:
            pass
    _memory_store[f"heaven:state:{task_id}"] = serialized


def get_build_state(task_id: str) -> Optional[Dict[str, Any]]:
    if _redis:
        try:
            raw = _redis.get(f"heaven:state:{task_id}")
            return json.loads(raw) if raw else None
        except Exception:
            pass
    raw = _memory_store.get(f"heaven:state:{task_id}")
    return json.loads(raw) if raw else None


def set_scoping_answers(task_id: str, answers: Dict[str, str]) -> None:
    serialized = json.dumps(answers)
    if _redis:
        try:
            _redis.set(f"heaven:answers:{task_id}", serialized, ex=LOG_EXPIRY)
            return
        except Exception:
            pass
    _memory_store[f"heaven:answers:{task_id}"] = serialized


def get_scoping_answers(task_id: str) -> Optional[Dict[str, str]]:
    if _redis:
        try:
            raw = _redis.get(f"heaven:answers:{task_id}")
            return json.loads(raw) if raw else None
        except Exception:
            pass
    raw = _memory_store.get(f"heaven:answers:{task_id}")
    return json.loads(raw) if raw else None


def ping_redis() -> bool:
    if _redis:
        try:
            _redis.ping()
            return True
        except Exception:
            return False
    return True  # In-memory always "works"
