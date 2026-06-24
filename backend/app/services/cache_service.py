import copy
import hashlib
import json
import time
from threading import Lock
from typing import Any


_CACHE: dict[str, dict[str, dict[str, Any]]] = {
    "planner": {},
    "naver_search": {},
    "llm_response": {},
}
_CACHE_LOCK = Lock()


def _prune_namespace(namespace: str, now: float) -> None:
    bucket = _CACHE.get(namespace, {})
    expired_keys = [key for key, entry in bucket.items() if entry["expires_at"] <= now]
    for key in expired_keys:
        bucket.pop(key, None)


def build_cache_key(namespace: str, payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{namespace}:{serialized}".encode("utf-8")).hexdigest()
    return digest


def get_cache(namespace: str, key: str) -> Any | None:
    now = time.time()
    with _CACHE_LOCK:
        _prune_namespace(namespace, now)
        entry = _CACHE.get(namespace, {}).get(key)
        if not entry:
            return None
        return copy.deepcopy(entry["value"])


def set_cache(namespace: str, key: str, value: Any, ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        return

    now = time.time()
    with _CACHE_LOCK:
        _prune_namespace(namespace, now)
        bucket = _CACHE.setdefault(namespace, {})
        bucket[key] = {
            "value": copy.deepcopy(value),
            "expires_at": now + ttl_seconds,
        }
