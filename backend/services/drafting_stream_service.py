"""
Drafting Stream Service.

Provides real-time milestone and progress event streaming between Celery tasks
and the FastAPI SSE / REST endpoints using Redis Pub/Sub with in-memory fallback.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import redis
from backend.config import settings

logger = logging.getLogger(__name__)

# In-memory fallback if Redis is unavailable
_MEMORY_EVENT_STORE: Dict[str, List[Dict[str, Any]]] = {}

def get_redis_client() -> Optional[redis.Redis]:
    """Get connected Redis client or None if connection fails."""
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.ping()
        return r
    except Exception as e:
        logger.warning(f"DraftingStreamService: Redis not available ({e}), falling back to in-memory events.")
        return None


class DraftingStreamService:
    """Service to publish and subscribe to contract drafting progress events."""

    @staticmethod
    def _channel_name(document_id: str) -> str:
        return f"draft_stream:{document_id}"

    @staticmethod
    def _history_key(document_id: str) -> str:
        return f"draft_events:{document_id}"

    @classmethod
    def publish_event(
        cls,
        document_id: str,
        milestone: str,
        message: str,
        progress: int = 0,
        stage: int = 1,
        total_stages: int = 6,
        details: Optional[Dict[str, Any]] = None,
        is_complete: bool = False,
        is_error: bool = False,
    ) -> Dict[str, Any]:
        """
        Publish a structured event for a contract drafting process.
        Persists to Redis list (and memory fallback) and broadcasts to Redis Pub/Sub.
        """
        event = {
            "document_id": document_id,
            "milestone": milestone,
            "stage": stage,
            "total_stages": total_stages,
            "progress_percentage": min(max(progress, 0), 100),
            "message": message,
            "details": details or {},
            "is_complete": is_complete,
            "is_error": is_error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 1. Update in-memory fallback
        if document_id not in _MEMORY_EVENT_STORE:
            _MEMORY_EVENT_STORE[document_id] = []
        _MEMORY_EVENT_STORE[document_id].append(event)
        # Cap memory events to last 200 items per doc
        if len(_MEMORY_EVENT_STORE[document_id]) > 200:
            _MEMORY_EVENT_STORE[document_id] = _MEMORY_EVENT_STORE[document_id][-200:]

        # 2. Publish to Redis if available
        r = get_redis_client()
        if r:
            try:
                serialized = json.dumps(event)
                key = cls._history_key(document_id)
                r.rpush(key, serialized)
                r.expire(key, 86400)  # 24 hour TTL
                r.publish(cls._channel_name(document_id), serialized)
            except Exception as e:
                logger.warning(f"DraftingStreamService: Failed to broadcast to Redis: {e}")

        logger.info(f"[{milestone} ({progress}%)] {message}")
        return event

    @classmethod
    def get_events(cls, document_id: str) -> List[Dict[str, Any]]:
        """Retrieve all recorded events for a given document."""
        r = get_redis_client()
        if r:
            try:
                key = cls._history_key(document_id)
                raw_items = r.lrange(key, 0, -1)
                if raw_items:
                    return [json.loads(item) for item in raw_items]
            except Exception as e:
                logger.warning(f"DraftingStreamService: Failed to read from Redis list: {e}")

        return _MEMORY_EVENT_STORE.get(document_id, [])

    @classmethod
    async def subscribe_stream(
        cls,
        document_id: str,
        heartbeat_interval: float = 12.0,
    ) -> AsyncGenerator[str, None]:
        """
        Async generator yielding SSE data frames (`data: {...}\n\n`).
        Flushes all existing historical events first, then streams live events via Redis Pub/Sub.
        """
        # Step A: Flush existing events to catch up
        existing = cls.get_events(document_id)
        last_timestamp = None
        for evt in existing:
            last_timestamp = evt.get("timestamp")
            yield f"data: {json.dumps(evt)}\n\n"
            if evt.get("is_complete") or evt.get("is_error"):
                return

        # Step B: Connect to Redis PubSub or poll memory fallback
        r = get_redis_client()
        if not r:
            # Fallback polling loop if no Redis
            cursor = len(existing)
            idle_count = 0
            while idle_count < 60:  # Timeout after 2 minutes of idle
                await asyncio.sleep(1.0)
                current = _MEMORY_EVENT_STORE.get(document_id, [])
                if len(current) > cursor:
                    for evt in current[cursor:]:
                        yield f"data: {json.dumps(evt)}\n\n"
                        if evt.get("is_complete") or evt.get("is_error"):
                            return
                    cursor = len(current)
                    idle_count = 0
                else:
                    idle_count += 1
                    yield f": ping\n\n"
            return

        pubsub = r.pubsub()
        channel = cls._channel_name(document_id)
        pubsub.subscribe(channel)

        try:
            loop = asyncio.get_running_loop()
            while True:
                # Run synchronous pubsub get_message in executor with a short timeout
                message = await loop.run_in_executor(
                    None,
                    lambda: pubsub.get_message(timeout=heartbeat_interval),
                )
                if message is None:
                    # Heartbeat comment to keep HTTP connection alive
                    yield ": ping\n\n"
                    continue

                if message["type"] == "message":
                    raw_data = message["data"]
                    try:
                        evt_data = json.loads(raw_data)
                        # Skip if already yielded in historical flush
                        if last_timestamp and evt_data.get("timestamp") == last_timestamp:
                            continue
                        yield f"data: {raw_data}\n\n"
                        if evt_data.get("is_complete") or evt_data.get("is_error"):
                            break
                    except Exception as parse_err:
                        logger.warning(f"Failed to parse SSE payload: {parse_err}")
                        yield f"data: {raw_data}\n\n"

        except asyncio.CancelledError:
            logger.info(f"SSE stream client disconnected for document: {document_id}")
        finally:
            try:
                pubsub.unsubscribe(channel)
                pubsub.close()
            except Exception:
                pass
