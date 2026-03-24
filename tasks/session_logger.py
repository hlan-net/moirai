"""Redis-backed session logger for agent and chat activity.

Each session (scheduled agent run, on_new_article dispatch, or chat turn) is
stored as a JSON document in Redis with a 7-day TTL.  Two sorted sets act as
indexes so callers can page through sessions by userspace or globally.

Key layout
----------
session:log:<session_id>          JSON blob, TTL SESSION_TTL_SECONDS
session:index:<userspace>         sorted set  score=epoch_ms
session:index:all                 sorted set  score=epoch_ms
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS = 7 * 24 * 3600  # 7 days
_INDEX_MAX_SIZE = 500  # keep sorted sets from growing unbounded

SESSION_TYPE_SCHEDULED = "scheduled_agent"
SESSION_TYPE_ON_NEW_ARTICLE = "on_new_article"
SESSION_TYPE_CHAT = "chat"

STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_ERROR = "error"


class SessionLogger:
    """Thin wrapper around a Redis client for session log operations.

    Designed to be safe when the Redis client is ``None`` — every public
    method silently no-ops in that case so the rest of the application never
    needs to guard against a missing logger.
    """

    def __init__(self, redis_client=None) -> None:
        self._redis = redis_client

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _key(self, session_id: str) -> str:
        return f"session:log:{session_id}"

    def _index_key(self, userspace: str) -> str:
        return f"session:index:{userspace}"

    def _score(self) -> float:
        return time.time() * 1000  # millisecond epoch as float

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_session(
        self,
        *,
        session_type: str,
        userspace: str,
        agent_config_id: str | None = None,
        agent_name: str | None = None,
        trigger: str | None = None,
        resolved_llm: dict | None = None,
        articles_count: int = 0,
    ) -> str:
        """Create a new session record and return its session_id."""
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "session_id": session_id,
            "session_type": session_type,
            "userspace": userspace,
            "agent_config_id": agent_config_id,
            "agent_name": agent_name,
            "trigger": trigger,
            "started_at": now,
            "finished_at": None,
            "duration_ms": None,
            "status": STATUS_RUNNING,
            "error": None,
            "resolved_llm": resolved_llm or {},
            "llm_calls": 0,
            "tool_calls": 0,
            "articles_processed": articles_count,
        }
        self._persist(session_id, doc, userspace)
        return session_id

    def finish_session(
        self,
        session_id: str,
        *,
        status: str = STATUS_SUCCESS,
        error: str | None = None,
        llm_calls: int = 0,
        tool_calls: int = 0,
        articles_processed: int | None = None,
    ) -> None:
        """Mark a session as finished and update counters."""
        if not self._redis or not session_id:
            return
        try:
            raw = self._redis.get(self._key(session_id))
            if not raw:
                return
            doc = json.loads(raw)
            now = datetime.now(timezone.utc).isoformat()
            started = doc.get("started_at")
            duration_ms = None
            if started:
                try:
                    start_dt = datetime.fromisoformat(started)
                    end_dt = datetime.fromisoformat(now)
                    duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
                except ValueError:
                    pass
            doc.update(
                {
                    "finished_at": now,
                    "duration_ms": duration_ms,
                    "status": status,
                    "error": error,
                    "llm_calls": llm_calls,
                    "tool_calls": tool_calls,
                }
            )
            if articles_processed is not None:
                doc["articles_processed"] = articles_processed
            self._persist(session_id, doc, doc.get("userspace", ""))
        except Exception:
            logger.exception("SessionLogger.finish_session failed for %s", session_id)

    def get_session(self, session_id: str) -> dict | None:
        """Return the session document or ``None`` if not found."""
        if not self._redis or not session_id:
            return None
        try:
            raw = self._redis.get(self._key(session_id))
            return json.loads(raw) if raw else None
        except Exception:
            logger.exception("SessionLogger.get_session failed for %s", session_id)
            return None

    def list_sessions(
        self,
        userspace: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Return sessions newest-first for the given userspace (or all userspaces)."""
        if not self._redis:
            return []
        try:
            index_key = self._index_key(userspace) if userspace else "session:index:all"
            # ZREVRANGE returns members in descending score order (newest first)
            ids = self._redis.zrevrange(index_key, offset, offset + limit - 1)
            sessions = []
            for sid in ids:
                raw = self._redis.get(self._key(sid))
                if raw:
                    sessions.append(json.loads(raw))
            return sessions
        except Exception:
            logger.exception("SessionLogger.list_sessions failed")
            return []

    # ------------------------------------------------------------------
    # Context manager for convenient wrapping of a code block
    # ------------------------------------------------------------------

    @contextmanager
    def session(
        self,
        *,
        session_type: str,
        userspace: str,
        agent_config_id: str | None = None,
        agent_name: str | None = None,
        trigger: str | None = None,
        resolved_llm: dict | None = None,
        articles_count: int = 0,
    ) -> Generator[dict, None, None]:
        """Context manager that starts a session and finishes it on exit.

        Yields a mutable ``counters`` dict so the caller can increment
        ``llm_calls`` and ``tool_calls`` in-place::

            with logger.session(...) as s:
                s["llm_calls"] += 1
                s["tool_calls"] += 2
        """
        session_id = self.start_session(
            session_type=session_type,
            userspace=userspace,
            agent_config_id=agent_config_id,
            agent_name=agent_name,
            trigger=trigger,
            resolved_llm=resolved_llm,
            articles_count=articles_count,
        )
        counters = {
            "session_id": session_id,
            "llm_calls": 0,
            "tool_calls": 0,
            "articles_processed": articles_count,
        }
        status = STATUS_SUCCESS
        error_msg = None
        try:
            yield counters
        except Exception as exc:
            status = STATUS_ERROR
            error_msg = str(exc)
            raise
        finally:
            self.finish_session(
                session_id,
                status=status,
                error=error_msg,
                llm_calls=counters.get("llm_calls", 0),
                tool_calls=counters.get("tool_calls", 0),
                articles_processed=counters.get("articles_processed"),
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _persist(self, session_id: str, doc: dict, userspace: str) -> None:
        if not self._redis:
            return
        try:
            key = self._key(session_id)
            score = self._score()
            pipe = self._redis.pipeline(transaction=False)
            pipe.set(key, json.dumps(doc), ex=SESSION_TTL_SECONDS)
            # Per-userspace index
            if userspace:
                us_idx = self._index_key(userspace)
                pipe.zadd(us_idx, {session_id: score})
                pipe.zremrangebyrank(us_idx, 0, -((_INDEX_MAX_SIZE) + 1))
            # Global index
            pipe.zadd("session:index:all", {session_id: score})
            pipe.zremrangebyrank("session:index:all", 0, -(_INDEX_MAX_SIZE + 1))
            pipe.execute()
        except Exception:
            logger.exception("SessionLogger._persist failed for %s", session_id)
