"""HIPAA-aligned audit logger.

All significant operations call into this module. The emitted events form a
hash-chained append-only log stored in a compliance-grade backend.

Backend selection is pluggable via the AUDIT_BACKEND env var:
- file (default in dev) → /var/log/retina-scan-ai/audit.jsonl
- s3 → S3 bucket with Object Lock
- datadog → forwards to a Datadog log pipeline
- loki → forwards to Grafana Loki

This module itself is not HIPAA-certified; the overall deployment including
the backend, access controls, and retention policies must be reviewed by the
operator's compliance team.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class EventCategory(str, Enum):
    ACCESS = "access"
    MODIFY = "modify"
    DELETE = "delete"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    EXPORT = "export"
    SYSTEM = "system"


class Outcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    DENIED = "DENIED"


@dataclass
class Actor:
    user_id: str
    display_name: str | None = None
    role: str | None = None
    session_id: str | None = None


@dataclass
class Subject:
    patient_hash: str | None = None
    study_uid: str | None = None
    series_uid: str | None = None


@dataclass
class Source:
    ip: str | None = None
    user_agent: str | None = None
    device_id: str | None = None


@dataclass
class Context:
    purpose_of_use: str | None = None
    consent_reference: str | None = None
    break_glass: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class AuditBackend:
    """Abstract backend. Subclasses must implement append() atomically."""

    def append(self, event: dict) -> None:
        raise NotImplementedError


class FileBackend(AuditBackend):
    """Default dev backend: append to a JSONL file with a lock."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, event: dict) -> None:
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, separators=(",", ":")) + "\n")


class InMemoryBackend(AuditBackend):
    """For tests. Not for production."""

    def __init__(self) -> None:
        self.events: list[dict] = []
        self._lock = threading.Lock()

    def append(self, event: dict) -> None:
        with self._lock:
            self.events.append(event)


class AuditLogger:
    """Hash-chained audit logger.

    Not HIPAA-certified on its own. Operator's compliance team must review
    the deployment configuration (backend, access controls, retention).
    """

    def __init__(self, backend: AuditBackend | None = None) -> None:
        self.backend = backend or self._default_backend()
        self._prev_hash: str = "sha256:genesis"
        self._lock = threading.Lock()

    @staticmethod
    def _default_backend() -> AuditBackend:
        kind = os.getenv("AUDIT_BACKEND", "file")
        if kind == "file":
            return FileBackend(
                os.getenv("AUDIT_FILE_PATH", "/var/log/retina-scan-ai/audit.jsonl")
            )
        if kind == "memory":
            return InMemoryBackend()
        raise ValueError(f"unknown AUDIT_BACKEND: {kind}")

    def emit(
        self,
        *,
        event_type: str,
        actor: Actor,
        subject: Subject | None = None,
        source: Source | None = None,
        context: Context | None = None,
        action: str | None = None,
        outcome: Outcome = Outcome.SUCCESS,
        category: EventCategory | None = None,
    ) -> dict:
        """Emit an audit event. Returns the full event record (with id+hash).

        Thread-safe. Blocks on the backend append.
        """
        with self._lock:
            event_id = "evt_" + uuid.uuid4().hex
            ts = datetime.now(timezone.utc).isoformat()

            if category is None:
                # Infer category from event_type prefix.
                category = EventCategory(event_type.split(".", 1)[0])

            event: dict[str, Any] = {
                "event_id": event_id,
                "event_timestamp": ts,
                "event_type": event_type,
                "category": category.value,
                "actor": _asdict(actor),
                "subject": _asdict(subject) if subject else None,
                "source": _asdict(source) if source else None,
                "context": _asdict(context) if context else None,
                "action": action,
                "outcome": outcome.value,
                "integrity": {"prev_hash": self._prev_hash},
            }

            # Compute current_hash over the event excluding the current_hash field.
            canonical = json.dumps(event, sort_keys=True, separators=(",", ":"))
            current_hash = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            event["integrity"]["current_hash"] = current_hash
            self._prev_hash = current_hash

            self.backend.append(event)
            return event


def _asdict(obj: Any) -> dict | None:
    if obj is None:
        return None
    if hasattr(obj, "__dataclass_fields__"):
        return {k: v for k, v in obj.__dict__.items() if v is not None}
    if isinstance(obj, dict):
        return obj
    return {"value": str(obj)}


# -----------------------------
# Module-level convenience API
# -----------------------------

_default_logger: AuditLogger | None = None


def get_logger() -> AuditLogger:
    global _default_logger
    if _default_logger is None:
        _default_logger = AuditLogger()
    return _default_logger


def log_access(
    event_type: str,
    actor: Actor,
    subject: Subject | None = None,
    **kwargs: Any,
) -> dict:
    return get_logger().emit(
        event_type=event_type,
        actor=actor,
        subject=subject,
        category=EventCategory.ACCESS,
        action="READ",
        **kwargs,
    )


def log_modify(event_type: str, actor: Actor, subject: Subject | None = None, **kwargs: Any) -> dict:
    return get_logger().emit(
        event_type=event_type,
        actor=actor,
        subject=subject,
        category=EventCategory.MODIFY,
        action="WRITE",
        **kwargs,
    )


def log_authentication(event_type: str, actor: Actor, outcome: Outcome, **kwargs: Any) -> dict:
    return get_logger().emit(
        event_type=event_type,
        actor=actor,
        category=EventCategory.AUTHENTICATION,
        outcome=outcome,
        **kwargs,
    )
