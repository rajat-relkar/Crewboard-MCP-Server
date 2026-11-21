"""Audit log: an append-only record of every tool call.

AuditMiddleware writes one row to data/audit.db for each tool call, whether it
succeeds, is refused, or fails. The log is kept in its own database, apart from
the tasks, and triggers reject UPDATE and DELETE, so rows can be added but never
changed or removed. Requests without a valid token are rejected with
401 Unauthorized before they reach any tool, so they don't appear here.
"""
import json
import logging
import sqlite3
import time
from typing import Any
from uuid import uuid4

import mcp_types as mt
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult

from mcp_server.database import data_dir

audit_db_path = data_dir / "audit.db"

logger = logging.getLogger(__name__)

# Arguments whose names contain one of these words are logged as "[REDACTED]".
SENSITIVE_WORDS = ("token", "secret", "password", "credential", "key")

# Longer text is cut short, so one oversized call can't bloat the log.
MAX_TEXT_LENGTH = 500


class PermissionDenied(ToolError):
    """The caller isn't allowed to do this. Recorded in the audit log as 'denied'."""


def init_audit_db() -> None:
    """Create the audit_log table and the triggers that make it append-only."""

    audit_db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(audit_db_path)

    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS audit_log(
                event_id TEXT PRIMARY KEY,
                occurred_at TEXT NOT NULL,
                caller TEXT,
                caller_id TEXT,
                tool TEXT NOT NULL,
                arguments TEXT NOT NULL,
                outcome TEXT NOT NULL CHECK (outcome IN ('success', 'denied', 'error')),
                error TEXT,
                duration_ms INTEGER NOT NULL
            );

            CREATE TRIGGER IF NOT EXISTS audit_log_no_update
            BEFORE UPDATE ON audit_log
            BEGIN
                SELECT RAISE(ABORT, 'audit_log is append-only');
            END;

            CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
            BEFORE DELETE ON audit_log
            BEGIN
                SELECT RAISE(ABORT, 'audit_log is append-only');
            END;
        """)
        conn.commit()

    finally:
        conn.close()


def _shorten(text: str) -> str:
    if len(text) <= MAX_TEXT_LENGTH:
        return text
    return f"{text[:MAX_TEXT_LENGTH]}… [{len(text) - MAX_TEXT_LENGTH} more characters]"


def _clean_arguments(arguments: dict[str, Any]) -> str:
    """Return the arguments as JSON, with sensitive values redacted and long text shortened."""

    cleaned = {}
    for name, value in arguments.items():
        if any(word in name.lower() for word in SENSITIVE_WORDS):
            cleaned[name] = "[REDACTED]"
        elif isinstance(value, str):
            cleaned[name] = _shorten(value)
        else:
            cleaned[name] = value

    return json.dumps(cleaned, default=str)


def _write_event(event: dict[str, Any]) -> None:

    conn = sqlite3.connect(audit_db_path)

    try:
        conn.execute("""
            INSERT INTO audit_log(
                event_id, occurred_at, caller, caller_id, tool, arguments, outcome, error, duration_ms
            )
            VALUES(
                :event_id, :occurred_at, :caller, :caller_id, :tool, :arguments, :outcome, :error, :duration_ms
            )
        """,
            event
        )
        conn.commit()
    finally:
        conn.close()


class AuditMiddleware(Middleware):
    """Record every tool call in the audit log: who called which tool, when, and how it ended."""

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        started = time.perf_counter()
        # Stays "error" if the call is cancelled, for example when the client disconnects.
        outcome, error = "error", "The call was cancelled before the tool finished"

        try:
            result = await call_next(context)
            outcome, error = "success", None
            return result
        except PermissionDenied as exc:
            outcome, error = "denied", str(exc)
            raise
        except Exception as exc:  # validation errors, unknown tasks, unexpected failures
            outcome, error = "error", f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self._record(context, outcome, error, started)

    def _record(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        outcome: str,
        error: str | None,
        started: float,
    ) -> None:
        token = get_access_token()
        claims = token.claims if token else {}

        event = {
            "event_id": str(uuid4()),
            "occurred_at": context.timestamp.isoformat(),
            "caller": claims.get("login"),
            # GitHub's numeric user ID. Unlike the username, it never changes.
            "caller_id": claims.get("sub"),
            "tool": context.message.name,
            "arguments": _clean_arguments(context.message.arguments or {}),
            "outcome": outcome,
            "error": _shorten(error) if error else None,
            "duration_ms": round((time.perf_counter() - started) * 1000),
        }

        # Written synchronously, so the event is saved even when the call is cancelled.
        # If the write fails, the failure is logged and the tool's result is returned as usual.
        try:
            _write_event(event)
        except Exception:
            logger.exception("Could not write the audit event for tool %r", event["tool"])
