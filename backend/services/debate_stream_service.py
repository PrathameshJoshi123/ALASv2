"""
Debate Stream Service.

Provides real-time event streaming for the Pre-Trial Multi-Agent Moot Debate
between LangGraph agent nodes and FastAPI SSE endpoints using Redis Pub/Sub
with in-memory fallback.
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
_DEBATE_MEMORY_STORE: Dict[str, List[Dict[str, Any]]] = {}


def get_redis_client() -> Optional[redis.Redis]:
    """Get connected Redis client or None if connection fails."""
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.ping()
        return r
    except Exception as e:
        logger.warning(
            f"DebateStreamService: Redis not available ({e}), falling back to in-memory events."
        )
        return None


class DebateStreamService:
    """Service to publish and subscribe to pre-trial courtroom debate events."""

    @staticmethod
    def _channel_name(case_id: str) -> str:
        return f"debate_stream:{case_id}"

    @staticmethod
    def _history_key(case_id: str) -> str:
        return f"debate_events:{case_id}"

    @classmethod
    def publish_event(
        cls,
        case_id: str,
        event_type: str,
        speaker: str,
        message: str,
        round_number: int = 1,
        details: Optional[Dict[str, Any]] = None,
        is_complete: bool = False,
    ) -> Dict[str, Any]:
        """
        Publish a structured debate event (speech, Kanoon research citation, bench query, intervention).
        """
        event = {
            "case_id": case_id,
            "event_type": event_type,  # "speech", "kanoon_research", "bench_query", "intervention", "verdict"
            "speaker": speaker,        # "petitioner", "respondent", "judge", "law_clerk", "user"
            "round_number": round_number,
            "message": message,
            "details": details or {},
            "is_complete": is_complete,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 1. Update in-memory fallback
        if case_id not in _DEBATE_MEMORY_STORE:
            _DEBATE_MEMORY_STORE[case_id] = []
        _DEBATE_MEMORY_STORE[case_id].append(event)
        if len(_DEBATE_MEMORY_STORE[case_id]) > 300:
            _DEBATE_MEMORY_STORE[case_id] = _DEBATE_MEMORY_STORE[case_id][-300:]

        # 2. Broadcast via Redis
        r = get_redis_client()
        if r:
            try:
                serialized = json.dumps(event)
                key = cls._history_key(case_id)
                r.rpush(key, serialized)
                r.expire(key, 86400)
                r.publish(cls._channel_name(case_id), serialized)
            except Exception as e:
                logger.warning(f"DebateStreamService: Failed to broadcast to Redis: {e}")

        logger.info(f"[{speaker.upper()} (R{round_number}): {event_type}] {message[:120]}")
        return event

    @classmethod
    def get_events(cls, case_id: str) -> List[Dict[str, Any]]:
        """Retrieve historical debate events."""
        r = get_redis_client()
        if r:
            try:
                key = cls._history_key(case_id)
                raw_items = r.lrange(key, 0, -1)
                if raw_items:
                    return [json.loads(item) for item in raw_items]
            except Exception as e:
                logger.warning(f"DebateStreamService: Failed to read from Redis: {e}")

        return _DEBATE_MEMORY_STORE.get(case_id, [])

    @classmethod
    async def subscribe_events(
        cls,
        case_id: str,
        timeout: int = 120,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Async generator yielding real-time debate events via Redis Pub/Sub
        with fallback to in-memory polling.
        """
        r = get_redis_client()
        if r:
            pubsub = r.pubsub()
            pubsub.subscribe(cls._channel_name(case_id))
            elapsed = 0
            poll_interval = 0.5
            try:
                while elapsed < timeout:
                    message = pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=poll_interval,
                    )
                    if message and message.get("type") == "message":
                        data_str = message.get("data")
                        if data_str:
                            event = json.loads(data_str)
                            yield event
                            if event.get("is_complete"):
                                break
                    await asyncio.sleep(poll_interval)
                    elapsed += poll_interval
            finally:
                pubsub.unsubscribe(cls._channel_name(case_id))
                pubsub.close()
        else:
            # Memory polling fallback
            seen_count = 0
            elapsed = 0
            poll_interval = 0.8
            while elapsed < timeout:
                events = _DEBATE_MEMORY_STORE.get(case_id, [])
                if len(events) > seen_count:
                    for evt in events[seen_count:]:
                        yield evt
                        if evt.get("is_complete"):
                            return
                    seen_count = len(events)
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
